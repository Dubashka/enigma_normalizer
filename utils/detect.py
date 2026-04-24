"""Автоматическое определение типа данных по содержимому колонки.

Алгоритм: на выборке значений (до 200 штук) считается доля попаданий в каждый
из типов. Побеждает тот, у которого доля выше порога и при этом приоритет выше.
Если ни один тип не набрал порог, возвращается None (пользователь увидит
подсказку «тип не распознан» и сможет выбрать вручную).

Порядок проверки важен: сначала строгие форматы (email, телефон, ИНН),
потом более размытые (адрес, организация, ФИО).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable

import pandas as pd
import phonenumbers


# ---------------------------------------------------------------------------
# Регулярки для детекта
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^\s*[^\s<>@]+@[^\s<>@]+\.[A-Za-z]{2,}\s*$")
_EMAIL_CONTAINS_RE = re.compile(r"[^\s<>@]+@[^\s<>@]+\.[A-Za-z]{2,}")

_PHONE_CHARS_RE = re.compile(r"^[\s+\-()\d.]{7,}$")
_DIGIT_RE = re.compile(r"\D+")

_INN_RE = re.compile(r"^\s*(?:ИНН[:\s]*)?[\d\-\s]{10,14}\s*$", re.IGNORECASE)

_PATRONYMIC_RE = re.compile(
    r"\b\w+(?:вич|ьич|вна|ична|инична)\b",
    re.IGNORECASE,
)
_CYR_WORD_RE = re.compile(r"^[А-ЯЁа-яё][А-ЯЁа-яё\-]+$")
_INITIAL_TOKEN_RE = re.compile(r"^[А-ЯЁA-Z]\.?$")

_OPF_RE = re.compile(
    r"\b(ООО|ОАО|ЗАО|ПАО|НАО|АО|ИП|ГК|НКО|ФГУП|МУП|ГБОУ|ГБУ|МБУ|ФГБУ|"
    r"общество\s+с\s+ограниченной|акционерное\s+общество|"
    r"индивидуальный\s+предприниматель)\b",
    re.IGNORECASE,
)
_ORG_KEYWORDS_RE = re.compile(
    r"\b(сбербанк|банк|завод|фабрика|компания|корпорация|группа|"
    r"холдинг|агентство|бюро|студия)\b",
    re.IGNORECASE,
)

_ADDR_MARKERS_RE = re.compile(
    r"(?:\bгород\b|\bг\.|\bулица\b|\bул\.|\bдом\b|\bквартира\b|\bкв\.|"
    r"\bпроспект\b|\bпр-?т\b|\bпереулок\b|\bпер\.|\bшоссе\b|"
    r"\bнабережная\b|\bнаб\.|\bбульвар\b|\bб-?р\b|"
    r"\bмикрорайон\b|\bмкр\b|\bобласть\b|\bобл\.|"
    r"\bреспублика\b|\bресп\.|\bсело\b|"
    r"\bпосёлок\b|\bпоселок\b|\bпос\.|\bроссия\b|\bрф\b)",
    re.IGNORECASE,
)
_INDEX_RE = re.compile(r"\b\d{6}\b")


# ---------------------------------------------------------------------------
# Детекторы для одного значения
# ---------------------------------------------------------------------------

def _is_email(v: str) -> bool:
    return bool(_EMAIL_RE.match(v)) or bool(_EMAIL_CONTAINS_RE.search(v))


def _is_phone(v: str) -> bool:
    digits = _DIGIT_RE.sub("", v)
    if not (10 <= len(digits) <= 15):
        return False
    if not _PHONE_CHARS_RE.match(v.strip()):
        return False
    try:
        parsed = phonenumbers.parse(v, "RU")
    except phonenumbers.NumberParseException:
        return False
    return phonenumbers.is_possible_number(parsed)


def _is_inn(v: str) -> bool:
    s = v.strip()
    if "@" in s:
        return False
    if not _INN_RE.match(s):
        return False
    digits = _DIGIT_RE.sub("", s)
    return len(digits) in (10, 12)


def _is_fio(v: str) -> bool:
    s = v.strip()
    if not s or len(s) > 80:
        return False
    if re.search(r"[\d@]", s):
        return False
    # Явный маркер — отчество
    if _PATRONYMIC_RE.search(s):
        return True
    # Инициальная форма без пробелов: "Петрова М.С." / "Иванов И.И."
    # Разделим склеенные инициалы "М.С." -> "М. С." для токенизации
    s_split = re.sub(r"([А-ЯЁA-Z])\.([А-ЯЁA-Z])\.", r"\1. \2.", s)
    tokens = s_split.split()
    if not (2 <= len(tokens) <= 4):
        return False
    cyr_words = sum(1 for t in tokens if _CYR_WORD_RE.match(t.rstrip(".")))
    initials = sum(1 for t in tokens if _INITIAL_TOKEN_RE.match(t))
    # Фамилия + один-два инициала
    if cyr_words >= 1 and initials >= 1 and cyr_words + initials == len(tokens):
        return True
    # Три кириллических слова подряд — вероятное полное ФИО
    if cyr_words == len(tokens) == 3:
        return True
    return False


def _is_address(v: str) -> bool:
    s = v.strip()
    if len(s) < 5:
        return False
    if _ADDR_MARKERS_RE.search(s):
        return True
    if _INDEX_RE.search(s) and "," in s:
        return True
    return False


def _is_organization(v: str) -> bool:
    s = v.strip()
    if len(s) < 2 or len(s) > 200:
        return False
    if "@" in s:
        return False
    if _OPF_RE.search(s):
        return True
    if re.search(r"[\"«][^\"«»]{2,}[\"»]", s):
        return True
    if _ORG_KEYWORDS_RE.search(s):
        return True
    return False


# Порядок важен: приоритет = позиция в списке.
# Чем строже/уникальнее паттерн — тем раньше.
_DETECTORS: list[tuple[str, Callable[[str], bool]]] = [
    ("email", _is_email),
    ("phone", _is_phone),
    ("inn", _is_inn),
    ("address", _is_address),
    ("organization", _is_organization),
    ("fio", _is_fio),
]


def detect_type(
    values: Iterable,
    threshold: float = 0.6,
    sample_size: int = 200,
) -> tuple[str | None, dict]:
    """Определяет тип данных по выборке значений.

    Args:
        values: итерабельный источник значений (например, колонка DataFrame).
        threshold: минимальная доля совпадений для уверенного вывода.
        sample_size: сколько значений брать в выборку.

    Returns:
        (detected_type | None, scores-dict)
    """
    sample: list[str] = []
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if not s or s.lower() in ("nan", "none", "null", "-"):
            continue
        sample.append(s)
        if len(sample) >= sample_size:
            break

    if not sample:
        return None, {}

    total = len(sample)
    scores: dict[str, float] = {}
    for type_key, detector in _DETECTORS:
        hits = sum(1 for v in sample if detector(v))
        scores[type_key] = hits / total

    # Порядок приоритета: возвращаем первый тип, прошедший порог.
    for type_key, _ in _DETECTORS:
        if scores.get(type_key, 0) >= threshold:
            return type_key, scores

    # Никто не дотянул: если лучший >= 0.4 — выдадим его как догадку.
    best = max(scores.items(), key=lambda kv: kv[1])
    if best[1] >= 0.4:
        return best[0], scores
    return None, scores


# ---------------------------------------------------------------------------
# Сканирование всего листа: находим колонки, пригодные для нормализации
# ---------------------------------------------------------------------------

@dataclass
class ColumnScan:
    """Результат сканирования одной колонки."""

    column: str
    detected_type: str | None  # ключ из REGISTRY или None
    confidence: float           # доля совпадений для выбранного типа (0..1)
    scores: dict                # полный словарь оценок
    non_empty: int              # сколько непустых значений участвовало
    recommended: bool           # включать в нормализацию по умолчанию?


def scan_dataframe(
    df: pd.DataFrame,
    threshold: float = 0.6,
    recommend_threshold: float = 0.6,
    min_values: int = 2,
    sample_size: int = 100,
) -> list[ColumnScan]:
    """Прогоняет автодетект по каждой колонке DataFrame.

    Колонка рекомендуется к нормализации, если:
      * тип распознан (detected_type != None);
      * доля совпадений для этого типа >= recommend_threshold;
      * в колонке есть минимум min_values непустых значений.

    Args:
        df: исходный DataFrame листа.
        threshold: порог уверенного детекта (передаётся в detect_type).
        recommend_threshold: отдельный, обычно более строгий порог для
            автоматического включения колонки в набор для нормализации.
        min_values: минимум непустых значений, иначе колонка пропускается.
        sample_size: размер выборки для детекта.

    Returns:
        Список ColumnScan в порядке колонок DataFrame.
    """
    results: list[ColumnScan] = []
    for col in df.columns:
        series = df[col].dropna()
        # Для автодетекта берём только head(sample_size*3) — больше не нужно для
        # оценки, а на многомиллионных колонках dropna+tolist — дорого.
        preview = series.head(max(sample_size * 3, min_values * 10))
        values = [str(v).strip() for v in preview.tolist()]
        values = [v for v in values if v and v.lower() not in ("nan", "none", "null", "-")]
        # Непустые по всей колонке (для показа в UI) берём дешево: len(series).
        non_empty = int(len(series))

        if non_empty < min_values:
            results.append(ColumnScan(
                column=str(col),
                detected_type=None,
                confidence=0.0,
                scores={},
                non_empty=non_empty,
                recommended=False,
            ))
            continue

        detected, scores = detect_type(values, threshold=threshold, sample_size=sample_size)
        confidence = scores.get(detected, 0.0) if detected else 0.0
        recommended = (
            detected is not None
            and confidence >= recommend_threshold
        )
        results.append(ColumnScan(
            column=str(col),
            detected_type=detected,
            confidence=confidence,
            scores=scores,
            non_empty=non_empty,
            recommended=recommended,
        ))
    return results
