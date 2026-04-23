"""Streamlit-стенд для тестирования алгоритмов нормализации данных.

Пошаговый UX:
1. Загрузка Excel-файла.
2. Выбор листа. Система сама сканирует все колонки и предлагает
   те, для которых есть алгоритм. Пользователь может снять/поставить
   галочки для любой колонки.
3. Для каждой выбранной колонки автодетект показывает тип; его можно
   скорректировать вручную, если автодетект не уверен.
4. Запуск алгоритмов — каждая колонка обрабатывается своим алгоритмом.
5. Интерактивное подтверждение кандидатов по каждой колонке (галочки).
6. Применение нормализации и скачивание:
   - нормализованный Excel,
   - JSON-справочник маппингов (по всем колонкам).
"""
from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from normalizers import LABELS, REGISTRY, get_normalizer
from normalizers.base import NormalizationCandidate
from utils.anomalies import scan_anomalies
from utils.detect import scan_dataframe


st.set_page_config(
    page_title="Enigma · Тестовый стенд нормализации",
    page_icon="🧪",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Управление состоянием сессии
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "uploaded_name": None,
        "sheets_data": {},          # {sheet_name: DataFrame}
        "sheet": None,
        "scans": [],                # list[ColumnScan] — результат сканирования листа
        "col_selected": {},         # {column: bool} — включать в нормализацию
        "col_type_overrides": {},   # {column: user_override_type | None}
        "results": {},              # {column: list[NormalizationCandidate]}
        "selections": {},           # {column: {idx: bool}}
        "canonicals": {},           # {column: {idx: str}}
        "applied": False,
        "normalized_df": None,
        "mapping_payload": None,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


_init_state()


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _read_excel(file_bytes: bytes) -> dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
    return {name: pd.read_excel(xls, sheet_name=name, dtype=object) for name in xls.sheet_names}


def _reset_after_upload():
    for key in (
        "sheet", "scans", "col_selected", "col_type_overrides",
        "results", "selections", "canonicals", "normalized_df", "mapping_payload",
    ):
        if isinstance(st.session_state.get(key), dict):
            st.session_state[key] = {}
        elif isinstance(st.session_state.get(key), list):
            st.session_state[key] = []
        else:
            st.session_state[key] = None
    st.session_state.applied = False


def _scan_sheet(df: pd.DataFrame) -> None:
    """Сканирует все колонки листа и заполняет col_selected по рекомендации."""
    scans = scan_dataframe(df)
    st.session_state.scans = scans
    # Выставляем дефолты только для новых колонок, сохраняя предыдущий выбор пользователя
    current_cols = {s.column for s in scans}
    # Убираем состояние для колонок, которых уже нет
    for stale in list(st.session_state.col_selected):
        if stale not in current_cols:
            st.session_state.col_selected.pop(stale, None)
    for stale in list(st.session_state.col_type_overrides):
        if stale not in current_cols:
            st.session_state.col_type_overrides.pop(stale, None)
    for s in scans:
        st.session_state.col_selected.setdefault(s.column, s.recommended)
        st.session_state.col_type_overrides.setdefault(s.column, None)


def _get_scan(col: str):
    for s in st.session_state.scans:
        if s.column == col:
            return s
    return None


def _effective_type(col: str) -> str | None:
    """Возвращает итоговый тип для колонки: override или автодетект."""
    override = st.session_state.col_type_overrides.get(col)
    if override:
        return override
    s = _get_scan(col)
    return s.detected_type if s else None


def _selected_columns() -> list[str]:
    """Возвращает список колонок с включенной галочкой, в порядке листа."""
    return [s.column for s in st.session_state.scans if st.session_state.col_selected.get(s.column, False)]


def _run_for_column(df: pd.DataFrame, col: str, data_type: str) -> list[NormalizationCandidate]:
    normalizer = get_normalizer(data_type)
    values = [str(v) for v in df[col].dropna().tolist()]
    return normalizer.build_candidates(values)


# ---------------------------------------------------------------------------
# Шапка
# ---------------------------------------------------------------------------
st.title("🧪 Enigma · Тестовый стенд нормализации")
st.caption(
    "Проверка отдельных алгоритмов нормализации перед этапом анонимизации. "
    "Система сама распознаёт тип данных в каждой колонке и запускает нужный алгоритм."
)

# ---------------------------------------------------------------------------
# Шаг 1. Загрузка файла
# ---------------------------------------------------------------------------
st.header("1. Загрузка Excel-файла")

uploaded = st.file_uploader(
    "Выберите .xlsx файл",
    type=["xlsx", "xls"],
    accept_multiple_files=False,
)

if uploaded is not None:
    if st.session_state.uploaded_name != uploaded.name:
        _reset_after_upload()
        st.session_state.uploaded_name = uploaded.name
        st.session_state.sheets_data = _read_excel(uploaded.getvalue())
    st.success(
        f"Файл загружен: **{uploaded.name}** · листов: {len(st.session_state.sheets_data)}"
    )

if not st.session_state.sheets_data:
    st.info("Загрузите Excel-файл, чтобы продолжить.")
    st.stop()


# ---------------------------------------------------------------------------
# Переключатель режима (в сайдбаре). Поиск аномалий вынесен в отдельный
# режим, чтобы не тормозить основной пайплайн на больших файлах —
# скан запускается явно по кнопке.
# ---------------------------------------------------------------------------
mode = st.sidebar.radio(
    "Режим",
    options=["🧪 Нормализация", "🔍 Поиск аномалий"],
    key="app_mode",
)

if mode == "🔍 Поиск аномалий":
    st.subheader("Проверка данных на аномалии")
    st.caption(
        "Сканирование листа на пустые строки, дубликаты, нетипичные значения в "
        "числовых/текстовых колонках и т.п. Работает отдельно от нормализации, "
        "чтобы не замедлять основной воркфлоу."
    )

    a_sheet = st.selectbox(
        "Лист для проверки",
        options=list(st.session_state.sheets_data.keys()),
        key="anomaly_sheet",
    )
    a_df = st.session_state.sheets_data[a_sheet]
    n_rows = len(a_df)
    st.caption(f"Строк на листе: **{n_rows:,}**".replace(",", " "))

    col_a, col_b = st.columns([3, 2])
    with col_a:
        use_sample = st.checkbox(
            "Ограничить сэмплом (для больших файлов)",
            value=n_rows > 50_000,
            key="anomaly_use_sample",
        )
    with col_b:
        sample_size = st.number_input(
            "Размер сэмпла", min_value=1_000, max_value=500_000,
            value=50_000, step=5_000, key="anomaly_sample_size",
            disabled=not use_sample,
        )

    run = st.button("Запустить поиск аномалий", type="primary", key="anomaly_run")
    cache_key = f"anomaly_cache::{st.session_state.uploaded_name}::{a_sheet}"

    if run:
        with st.spinner("Ищу аномалии…"):
            st.session_state[cache_key] = scan_anomalies(
                a_df,
                sample_size=int(sample_size) if use_sample else None,
            )

    groups = st.session_state.get(cache_key)
    if groups is None:
        st.info("Нажмите «Запустить поиск аномалий», чтобы проверить этот лист.")
    elif not groups:
        st.success("Аномалий не найдено — файл выглядит чистым.")
    else:
        total = sum(g.count for g in groups)
        sev_icon = {"high": "🔴", "medium": "🟡", "low": "⚪"}
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Всего находок", total)
        m2.metric("🔴 Критичные", sum(g.count for g in groups if g.severity == "high"))
        m3.metric("🟡 Средние", sum(g.count for g in groups if g.severity == "medium"))
        m4.metric("⚪ Незначительные", sum(g.count for g in groups if g.severity == "low"))

        report_rows: list[dict] = []
        for g in sorted(groups, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x.severity]):
            with st.expander(
                f"{sev_icon[g.severity]} {g.title} — {g.count}",
                expanded=g.severity == "high",
            ):
                st.caption(g.description)
                rows = [
                    {
                        "Строка (Excel)": e.row if e.row else "—",
                        "Колонка": e.column or "—",
                        "Значение": "" if e.value is None else str(e.value),
                    }
                    for e in g.examples
                ]
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                if g.count > len(g.examples):
                    st.caption(f"… и ещё {g.count - len(g.examples)} (показаны первые {len(g.examples)})")
                for e in g.examples:
                    report_rows.append({
                        "Тип": g.title,
                        "Важность": g.severity,
                        "Строка": e.row,
                        "Колонка": e.column,
                        "Значение": "" if e.value is None else str(e.value),
                    })

        if report_rows:
            csv = pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ Скачать отчёт (CSV)",
                data=csv,
                file_name=f"anomalies_{a_sheet}.csv",
                mime="text/csv",
                key="anomaly_report_dl",
            )

    st.stop()


# ---------------------------------------------------------------------------
# Шаг 2. Выбор листа + автоматическое распознавание колонок
# ---------------------------------------------------------------------------
st.header("2. Автоматическое распознавание колонок")

sheet = st.selectbox(
    "Лист",
    options=list(st.session_state.sheets_data.keys()),
    key="sheet_select",
)
if sheet != st.session_state.sheet:
    # Сменился лист — сбрасываем всё, что связано с колонками
    st.session_state.sheet = sheet
    st.session_state.scans = []
    st.session_state.col_selected = {}
    st.session_state.col_type_overrides = {}
    st.session_state.results = {}
    st.session_state.selections = {}
    st.session_state.canonicals = {}
    st.session_state.applied = False
    st.session_state.normalized_df = None
    st.session_state.mapping_payload = None

df = st.session_state.sheets_data[sheet]

# Сканирование листа (или пересканирование по кнопке)
if not st.session_state.scans:
    with st.spinner("Анализирую колонки листа…"):
        _scan_sheet(df)

scans = st.session_state.scans
recommended_cnt = sum(1 for s in scans if s.recommended)

hint_col, rescan_col = st.columns([5, 1])
with hint_col:
    st.caption(
        f"Найдено колонок всего: **{len(scans)}** · рекомендовано к нормализации: "
        f"**{recommended_cnt}**. Галочки выставлены автоматически — можно снять лишние "
        "или включить те, что система пропустила."
    )
with rescan_col:
    if st.button("↻ Пересканировать", help="Сбросить правки и выставить галочки по автодетекту"):
        st.session_state.col_selected = {}
        st.session_state.col_type_overrides = {}
        _scan_sheet(df)
        st.rerun()

# Таблица сканирования с чекбоксами
scan_rows = []
for s in scans:
    type_label = LABELS.get(s.detected_type, "—") if s.detected_type else "— не распознано"
    if s.detected_type:
        if s.confidence >= 0.75:
            badge = "✔ высокая"
        elif s.confidence >= 0.5:
            badge = "~ средняя"
        else:
            badge = "? низкая"
    else:
        badge = "—"
    scan_rows.append({
        "Включить": st.session_state.col_selected.get(s.column, s.recommended),
        "Колонка": s.column,
        "Распознанный тип": type_label,
        "Уверенность": f"{s.confidence:.0%}" if s.detected_type else "—",
        "Оценка": badge,
        "Непустых значений": s.non_empty,
    })

scan_df = pd.DataFrame(scan_rows)
edited_scan = st.data_editor(
    scan_df,
    use_container_width=True,
    hide_index=True,
    disabled=["Колонка", "Распознанный тип", "Уверенность", "Оценка", "Непустых значений"],
    column_config={
        "Включить": st.column_config.CheckboxColumn("Включить", width="small"),
        "Колонка": st.column_config.TextColumn("Колонка", width="medium"),
        "Распознанный тип": st.column_config.TextColumn("Распознанный тип", width="medium"),
        "Уверенность": st.column_config.TextColumn("Уверенность", width="small"),
        "Оценка": st.column_config.TextColumn("Оценка", width="small"),
        "Непустых значений": st.column_config.NumberColumn("Непустых", width="small"),
    },
    key="scan_editor",
)
# Синхронизируем изменения галочек обратно в session_state
for _, row in edited_scan.iterrows():
    st.session_state.col_selected[str(row["Колонка"])] = bool(row["Включить"])

columns = _selected_columns()

if not columns:
    st.info("Отметьте галочкой хотя бы одну колонку выше.")
    st.stop()

# Превью выбранных колонок
st.caption("Превью первых 10 строк по выбранным колонкам:")
st.dataframe(df[columns].head(10), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Шаг 3. Корректировка типа алгоритма (если автодетект не уверен)
# ---------------------------------------------------------------------------
st.header("3. Тип алгоритма для каждой колонки")
st.caption(
    "По умолчанию используется распознанный тип. Если автодетект ошибся или не уверен — "
    "выберите тип вручную в выпадающем списке."
)

type_options_with_auto = ["(авто)"] + list(REGISTRY.keys())

for col in columns:
    scan = _get_scan(col)
    detected = scan.detected_type if scan else None
    score = scan.confidence if scan else 0.0

    label_left, label_mid, label_right = st.columns([2, 2, 3])
    with label_left:
        st.markdown(f"**Колонка:** `{col}`")
    with label_mid:
        if detected:
            badge = "✅" if score >= 0.75 else ("🟡" if score >= 0.5 else "❓")
            st.markdown(
                f"{badge} Определено: **{LABELS[detected]}** "
                f"<span style='color:#888'>({score:.0%})</span>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown("❓ Тип не распознан — выберите вручную")

    with label_right:
        current_override = st.session_state.col_type_overrides.get(col)
        default_index = 0
        if current_override:
            default_index = 1 + list(REGISTRY.keys()).index(current_override)

        def _fmt(opt: str) -> str:
            if opt == "(авто)":
                if detected:
                    return f"(авто: {LABELS[detected]})"
                return "(не определено)"
            return LABELS[opt]

        choice = st.selectbox(
            "Тип алгоритма",
            options=type_options_with_auto,
            index=default_index,
            format_func=_fmt,
            key=f"type_override_{col}",
            label_visibility="collapsed",
        )
        st.session_state.col_type_overrides[col] = None if choice == "(авто)" else choice


# Проверяем, что у всех колонок есть тип
missing_type_cols = [c for c in columns if not _effective_type(c)]
if missing_type_cols:
    st.warning(
        "Не определён тип для колонок: "
        + ", ".join(f"`{c}`" for c in missing_type_cols)
        + ". Выберите вручную в списке справа — без этого запуск невозможен."
    )


# ---------------------------------------------------------------------------
# Шаг 4. Запуск алгоритмов
# ---------------------------------------------------------------------------
st.header("4. Запуск алгоритмов")

run_disabled = bool(missing_type_cols)
run_clicked = st.button(
    f"▶ Запустить нормализацию для {len(columns)} колонок",
    type="primary",
    disabled=run_disabled,
)

if run_clicked:
    st.session_state.results = {}
    st.session_state.selections = {}
    st.session_state.canonicals = {}
    st.session_state.applied = False

    progress = st.progress(0.0)
    for i, col in enumerate(columns, start=1):
        data_type = _effective_type(col)
        with st.spinner(f"[{i}/{len(columns)}] Алгоритм «{LABELS[data_type]}» для колонки «{col}»…"):
            cands = _run_for_column(df, col, data_type)
        st.session_state.results[col] = cands
        st.session_state.selections[col] = {j: (len(c.variants) > 1) for j, c in enumerate(cands)}
        st.session_state.canonicals[col] = {j: c.canonical for j, c in enumerate(cands)}
        progress.progress(i / len(columns))
    progress.empty()
    st.success(f"Обработано колонок: {len(columns)}.")


# ---------------------------------------------------------------------------
# Шаг 5. Кандидаты по каждой колонке (таб для каждой)
# ---------------------------------------------------------------------------
if st.session_state.results:
    st.header("5. Кандидаты на объединение")
    st.caption(
        "Для каждой колонки показан отдельный список кандидатов. "
        "Отметьте галочками группы, которые нужно действительно объединить. "
        "Каноническое значение можно отредактировать."
    )

    processed_cols = [c for c in columns if c in st.session_state.results]
    tab_labels = [
        f"{c} · {LABELS[_effective_type(c)]}"
        for c in processed_cols
    ]
    tabs = st.tabs(tab_labels)

    for tab, col in zip(tabs, processed_cols):
        with tab:
            candidates: list[NormalizationCandidate] = st.session_state.results[col]
            if not candidates:
                st.warning("Алгоритм не нашёл ни одного кандидата — колонка пуста или значения некорректны.")
                continue

            multi = sum(1 for c in candidates if len(c.variants) > 1)
            st.caption(
                f"Всего групп: **{len(candidates)}** · с несколькими вариантами: **{multi}**."
            )

            filter_mode = st.radio(
                "Показывать:",
                options=["Только группы с вариантами", "Все группы"],
                horizontal=True,
                index=0,
                key=f"filter_{col}",
            )

            bulk_a, bulk_b, _ = st.columns([1, 1, 4])
            with bulk_a:
                if st.button("✓ Отметить все", key=f"check_all_{col}"):
                    for i in range(len(candidates)):
                        st.session_state.selections[col][i] = True
                    st.rerun()
            with bulk_b:
                if st.button("✗ Снять все", key=f"uncheck_all_{col}"):
                    for i in range(len(candidates)):
                        st.session_state.selections[col][i] = False
                    st.rerun()

            rows = []
            for i, c in enumerate(candidates):
                if filter_mode == "Только группы с вариантами" and len(c.variants) <= 1:
                    continue
                rows.append({
                    "id": i,
                    "Применить": st.session_state.selections[col].get(i, False),
                    "Каноническое значение": st.session_state.canonicals[col].get(i, c.canonical),
                    "Варианты (исходные)": " | ".join(c.variants),
                    "Вариантов": len(c.variants),
                    "Встречается": c.count,
                    "Уверенность": round(c.confidence, 2),
                })

            if not rows:
                st.info("В этом режиме нет групп для отображения. Переключитесь на «Все группы».")
                continue

            editor_df = pd.DataFrame(rows)
            edited = st.data_editor(
                editor_df,
                use_container_width=True,
                hide_index=True,
                disabled=["id", "Варианты (исходные)", "Вариантов", "Встречается", "Уверенность"],
                column_config={
                    "id": st.column_config.NumberColumn("ID", width="small"),
                    "Применить": st.column_config.CheckboxColumn("Применить", width="small"),
                    "Каноническое значение": st.column_config.TextColumn(
                        "Каноническое значение", width="medium"
                    ),
                    "Варианты (исходные)": st.column_config.TextColumn(
                        "Варианты (исходные)", width="large"
                    ),
                },
                key=f"editor_{col}",
            )
            for _, row in edited.iterrows():
                idx = int(row["id"])
                st.session_state.selections[col][idx] = bool(row["Применить"])
                st.session_state.canonicals[col][idx] = str(row["Каноническое значение"])


# ---------------------------------------------------------------------------
# Шаг 6. Применение + экспорт
# ---------------------------------------------------------------------------
if st.session_state.results:
    st.header("6. Применение и экспорт")

    apply_clicked = st.button("🛠 Выполнить нормализацию по всем колонкам", type="primary")

    if apply_clicked:
        normalized_df = df.copy()
        per_column_payload: dict[str, dict] = {}
        total_changed = 0

        for col, candidates in st.session_state.results.items():
            selections = st.session_state.selections.get(col, {})
            canonicals = st.session_state.canonicals.get(col, {})

            mapping: dict[str, str] = {}
            applied_groups = []
            for i, c in enumerate(candidates):
                if not selections.get(i, False):
                    continue
                canonical = (canonicals.get(i, c.canonical) or "").strip()
                if not canonical:
                    continue
                for v in c.variants:
                    mapping[v] = canonical
                applied_groups.append({
                    "canonical": canonical,
                    "variants": c.variants,
                    "count": c.count,
                    "confidence": round(c.confidence, 3),
                    "meta": c.meta,
                })

            col_series = normalized_df[col].astype(object)
            new_series = col_series.map(
                lambda x: mapping.get(str(x), x) if pd.notna(x) else x
            )
            changed = int((col_series.astype(str) != new_series.astype(str)).sum())
            total_changed += changed
            normalized_df[col] = new_series

            scan = _get_scan(col)
            per_column_payload[col] = {
                "data_type": _effective_type(col),
                "data_type_label": LABELS[_effective_type(col)],
                "auto_detected": scan.detected_type if scan else None,
                "auto_detected_scores": scan.scores if scan else {},
                "auto_recommended": scan.recommended if scan else False,
                "total_candidates": len(candidates),
                "applied_groups": len(applied_groups),
                "values_changed": changed,
                "mapping": mapping,
                "groups": applied_groups,
            }

        st.session_state.normalized_df = normalized_df
        st.session_state.mapping_payload = {
            "meta": {
                "source_file": st.session_state.uploaded_name,
                "sheet": st.session_state.sheet,
                "columns": list(st.session_state.results.keys()),
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "total_values_changed": total_changed,
            },
            "columns": per_column_payload,
        }
        st.session_state.applied = True

    if st.session_state.applied and st.session_state.normalized_df is not None:
        payload = st.session_state.mapping_payload
        st.success(
            f"Нормализация выполнена. Заменено значений всего: "
            f"**{payload['meta']['total_values_changed']}** "
            f"по **{len(payload['columns'])}** колонкам."
        )

        st.subheader("Сравнение «до/после» (первые 15 строк по выбранным колонкам)")
        before = df[list(payload["columns"].keys())].head(15).reset_index(drop=True)
        after = st.session_state.normalized_df[list(payload["columns"].keys())].head(15).reset_index(drop=True)
        before.columns = [f"{c} (до)" for c in before.columns]
        after.columns = [f"{c} (после)" for c in after.columns]
        # Перемежаем пары колонок
        ordered_cols: list[str] = []
        for c in payload["columns"].keys():
            ordered_cols.append(f"{c} (до)")
            ordered_cols.append(f"{c} (после)")
        combined = pd.concat([before, after], axis=1)[ordered_cols]
        st.dataframe(combined, use_container_width=True, hide_index=True)

        # Скачивание Excel (все листы + обновлённый целевой лист)
        xlsx_buffer = io.BytesIO()
        with pd.ExcelWriter(xlsx_buffer, engine="xlsxwriter") as writer:
            for name, sdf in st.session_state.sheets_data.items():
                if name == st.session_state.sheet:
                    st.session_state.normalized_df.to_excel(writer, sheet_name=name, index=False)
                else:
                    sdf.to_excel(writer, sheet_name=name, index=False)

        base_name = (
            Path(st.session_state.uploaded_name).stem
            if st.session_state.uploaded_name else "normalized"
        )
        col_dl_1, col_dl_2 = st.columns(2)
        with col_dl_1:
            st.download_button(
                "⬇ Скачать нормализованный Excel",
                data=xlsx_buffer.getvalue(),
                file_name=f"{base_name}__normalized.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col_dl_2:
            mapping_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button(
                "⬇ Скачать JSON-справочник маппингов",
                data=mapping_bytes,
                file_name=f"{base_name}__mapping.json",
                mime="application/json",
                use_container_width=True,
            )


# ---------------------------------------------------------------------------
# Сайдбар — краткая справка
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("О стенде")
    st.markdown(
        """
**Назначение.** Проверка отдельных алгоритмов нормализации перед этапом
анонимизации в проекте *Enigma*.

**Как это работает:**
1. Загружаете Excel.
2. Выбираете лист. Система **сама находит колонки** для нормализации и определяет тип по содержимому.
3. При необходимости корректируете галочки или тип алгоритма вручную.
4. Запускаете — каждая колонка обрабатывается своим алгоритмом.
5. Подтверждаете кандидатов галочками.
6. Скачиваете Excel и JSON-справочник.

**Поддерживаемые типы — отдельные алгоритмы:**
- **ФИО** — `natasha` + `pymorphy3`, объединение полной и инициальной форм.
- **ИНН** — regex + контрольная сумма ФНС (10 / 12 знаков).
- **Адреса** — разворот сокращений + fuzzy-кластеризация.
- **Телефоны** — `phonenumbers`, E.164, поддержка добавочных.
- **Организации** — извлечение ОПФ + fuzzy по имени без ОПФ.
- **Email** — алиасы доменов, правила Gmail/Яндекс/Outlook.

**Автодетект.** Порог уверенности 60%. Если ни один тип не прошёл порог,
система берёт лучший (от 40%) или предлагает выбрать вручную.
        """
    )
    st.caption("Данные хранятся только в текущей сессии и не сохраняются.")
