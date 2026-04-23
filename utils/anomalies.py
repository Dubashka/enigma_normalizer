"""Поиск аномалий в данных Excel-листа.

Отдельный от основного пайплайна модуль: запускается по кнопке, чтобы
не тормозить обычный воркфлоу на больших файлах.

Что ищем:
- Полностью пустые строки (все ячейки пустые/NaN).
- Пустые ячейки в колонках, где почти все остальные значения заполнены
  (колонка считается «обязательной» эвристически, если >=95% заполнена).
- Дубликаты строк.
- Аномалии типа в колонке: если колонка преимущественно числовая —
  отдельно показываются нечисловые значения; если преимущественно
  текстовая — числовые «чужаки» игнорируем (часто это артефакт), но
  сигналим про значения, сильно выбивающиеся по длине/символам.
- Смешанные типы (колонка без явного доминирующего типа — это тоже сигнал).
- Ведущие/хвостовые пробелы в строковых значениях.

Результат возвращается списком AnomalyGroup с примерами (колонка, строка
в Excel-нумерации, значение) — чтобы пользователь мог пойти и поправить.

Для больших файлов поддерживается sample_size: анализируем только первые
N строк, но счётчики пустых строк считаем по полному DataFrame.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd


# Порог, при котором колонка считается «в основном числовой/текстовой»
_DOMINANT_RATIO = 0.9
# Минимум непустых значений, чтобы вообще делать выводы о типе
_MIN_NON_EMPTY = 5
# Порог заполненности для «обязательных» колонок
_REQUIRED_RATIO = 0.95
# Максимум примеров на одну группу аномалий
_MAX_EXAMPLES = 20

_NUMERIC_RE = re.compile(r"^\s*[-+]?\d+([.,]\d+)?\s*$")


@dataclass
class AnomalyExample:
    row: int  # номер строки как в Excel (с учётом заголовка, 1-based)
    column: str | None
    value: object


@dataclass
class AnomalyGroup:
    key: str          # машинный ключ
    title: str        # человекочитаемое название
    severity: str     # "high" | "medium" | "low"
    description: str
    count: int = 0
    examples: list[AnomalyExample] = field(default_factory=list)


def _is_empty(v: object) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    if isinstance(v, str) and not v.strip():
        return True
    return False


def _looks_numeric(v: object) -> bool:
    if isinstance(v, (int, float)) and not (isinstance(v, float) and pd.isna(v)):
        return True
    if isinstance(v, str):
        return bool(_NUMERIC_RE.match(v))
    return False


def _excel_row(idx: int) -> int:
    """DataFrame index -> Excel-строка (1 — это заголовок)."""
    return int(idx) + 2


def _add_example(group: AnomalyGroup, row: int, col: str | None, value: object):
    group.count += 1
    if len(group.examples) < _MAX_EXAMPLES:
        group.examples.append(AnomalyExample(row=row, column=col, value=value))


def scan_anomalies(df: pd.DataFrame, sample_size: int | None = None) -> list[AnomalyGroup]:
    """Основной вход. Возвращает список непустых групп аномалий."""
    if df is None or df.empty:
        return []

    total_rows = len(df)
    work = df if (sample_size is None or total_rows <= sample_size) else df.head(sample_size)

    groups: dict[str, AnomalyGroup] = {
        "empty_row": AnomalyGroup(
            key="empty_row",
            title="Полностью пустые строки",
            severity="high",
            description="Строки, в которых все ячейки пустые. Обычно их нужно удалить.",
        ),
        "missing_in_required": AnomalyGroup(
            key="missing_in_required",
            title="Пропуски в преимущественно заполненных колонках",
            severity="high",
            description=(
                "Ячейки без значения в колонках, где ≥95% строк заполнено. "
                "Скорее всего это пропущенные данные."
            ),
        ),
        "duplicate_row": AnomalyGroup(
            key="duplicate_row",
            title="Дубликаты строк",
            severity="medium",
            description="Строки, которые полностью повторяют другую строку.",
        ),
        "numeric_outlier": AnomalyGroup(
            key="numeric_outlier",
            title="Буквенные значения в числовой колонке",
            severity="high",
            description=(
                "В колонке, где ≥90% значений — числа, встретились нечисловые. "
                "Проверьте: возможно, опечатка или артефакт конвертации."
            ),
        ),
        "text_outlier": AnomalyGroup(
            key="text_outlier",
            title="Числовые значения в текстовой колонке",
            severity="medium",
            description=(
                "В колонке, где ≥90% значений — текст, встретились чисто числовые. "
                "Возможно, перепутаны колонки или неверный формат."
            ),
        ),
        "mixed_types": AnomalyGroup(
            key="mixed_types",
            title="Колонки со смешанными типами",
            severity="low",
            description=(
                "В колонке нет явного доминирующего типа (числа/текст поделены "
                "примерно поровну). Возможно, стоит разделить на две колонки."
            ),
        ),
        "whitespace": AnomalyGroup(
            key="whitespace",
            title="Лишние пробелы в значениях",
            severity="low",
            description="Значения с ведущими/хвостовыми пробелами или двойными пробелами внутри.",
        ),
    }

    # --- Полностью пустые строки (по всему df, не по сэмплу) ---
    mask_empty = df.map(_is_empty).all(axis=1) if hasattr(df, "map") else df.applymap(_is_empty).all(axis=1)
    for idx in df.index[mask_empty]:
        _add_example(groups["empty_row"], _excel_row(idx), None, None)

    # --- Дубликаты строк (по всему df) ---
    dup_mask = df.duplicated(keep="first")
    for idx in df.index[dup_mask]:
        _add_example(groups["duplicate_row"], _excel_row(idx), None, None)

    # --- По колонкам: анализируем на work (сэмпле) ---
    for col in work.columns:
        series = work[col]
        non_empty_mask = ~series.map(_is_empty)
        non_empty = series[non_empty_mask]
        n_non_empty = len(non_empty)
        n_total = len(series)

        # Пропуски в обязательных колонках
        if n_total >= _MIN_NON_EMPTY:
            fill_ratio = n_non_empty / n_total if n_total else 0
            if fill_ratio >= _REQUIRED_RATIO and fill_ratio < 1:
                for idx in series.index[~non_empty_mask]:
                    _add_example(groups["missing_in_required"], _excel_row(idx), str(col), None)

        if n_non_empty < _MIN_NON_EMPTY:
            continue

        numeric_flags = non_empty.map(_looks_numeric)
        n_num = int(numeric_flags.sum())
        num_ratio = n_num / n_non_empty

        if num_ratio >= _DOMINANT_RATIO and n_num < n_non_empty:
            # Числовая колонка, ловим нечисловых
            for idx, v in non_empty[~numeric_flags].items():
                _add_example(groups["numeric_outlier"], _excel_row(idx), str(col), v)
        elif (1 - num_ratio) >= _DOMINANT_RATIO and n_num > 0:
            # Текстовая колонка, ловим числовых
            for idx, v in non_empty[numeric_flags].items():
                _add_example(groups["text_outlier"], _excel_row(idx), str(col), v)
        elif 0.3 <= num_ratio <= 0.7:
            # Смешанные типы — логируем саму колонку разово
            _add_example(
                groups["mixed_types"], 0, str(col),
                f"{int(num_ratio * 100)}% чисел / {int((1 - num_ratio) * 100)}% текста",
            )

        # Пробелы — только по строковым значениям
        str_mask = non_empty.map(lambda v: isinstance(v, str))
        for idx, v in non_empty[str_mask].items():
            if v != v.strip() or "  " in v:
                _add_example(groups["whitespace"], _excel_row(idx), str(col), v)

    return [g for g in groups.values() if g.count > 0]


def summarize(groups: list[AnomalyGroup]) -> dict:
    """Сводка для быстрого отображения."""
    return {
        "total_issues": sum(g.count for g in groups),
        "by_severity": {
            sev: sum(g.count for g in groups if g.severity == sev)
            for sev in ("high", "medium", "low")
        },
        "groups": len(groups),
    }
