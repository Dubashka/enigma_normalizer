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
    page_title="Normalizer",
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
        "sheets": [],               # выбранные пользователем листы для нормализации
        "active_sheet": None,       # текущий лист, на который смотрит UI (внутри вкладки)
        # Состояние, ключи верхнего уровня — имя листа. Это позволяет
        # обрабатывать несколько листов в одном файле без смешения данных.
        "scans_by_sheet": {},            # {sheet: list[ColumnScan]}
        "col_selected_by_sheet": {},     # {sheet: {column: bool}}
        "col_type_overrides_by_sheet": {},  # {sheet: {column: type|None}}
        "results_by_sheet": {},          # {sheet: {column: list[NormalizationCandidate]}}
        "selections_by_sheet": {},       # {sheet: {column: {idx: bool}}}
        "canonicals_by_sheet": {},       # {sheet: {column: {idx: str}}}
        "applied": False,
        "normalized_by_sheet": {},       # {sheet: DataFrame}
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
        "sheets", "active_sheet", "scans_by_sheet", "col_selected_by_sheet",
        "col_type_overrides_by_sheet", "results_by_sheet", "selections_by_sheet",
        "canonicals_by_sheet", "normalized_by_sheet", "mapping_payload",
    ):
        if isinstance(st.session_state.get(key), dict):
            st.session_state[key] = {}
        elif isinstance(st.session_state.get(key), list):
            st.session_state[key] = []
        else:
            st.session_state[key] = None
    st.session_state.applied = False


def _ensure_sheet_state(sheet: str):
    """Гарантирует наличие контейнеров состояния для листа."""
    for container in (
        "scans_by_sheet", "col_selected_by_sheet", "col_type_overrides_by_sheet",
        "results_by_sheet", "selections_by_sheet", "canonicals_by_sheet",
    ):
        st.session_state[container].setdefault(sheet, [] if container == "scans_by_sheet" else {})


def _scan_sheet(sheet: str, df: pd.DataFrame) -> None:
    """Сканирует все колонки листа и заполняет col_selected по рекомендации."""
    _ensure_sheet_state(sheet)
    scans = scan_dataframe(df)
    st.session_state.scans_by_sheet[sheet] = scans
    current_cols = {s.column for s in scans}
    cs = st.session_state.col_selected_by_sheet[sheet]
    to = st.session_state.col_type_overrides_by_sheet[sheet]
    for stale in list(cs):
        if stale not in current_cols:
            cs.pop(stale, None)
    for stale in list(to):
        if stale not in current_cols:
            to.pop(stale, None)
    for s in scans:
        cs.setdefault(s.column, s.recommended)
        to.setdefault(s.column, None)


def _get_scan(sheet: str, col: str):
    for s in st.session_state.scans_by_sheet.get(sheet, []):
        if s.column == col:
            return s
    return None


def _effective_type(sheet: str, col: str) -> str | None:
    """Итоговый тип для колонки листа: override или автодетект."""
    override = st.session_state.col_type_overrides_by_sheet.get(sheet, {}).get(col)
    if override:
        return override
    s = _get_scan(sheet, col)
    return s.detected_type if s else None


def _selected_columns(sheet: str) -> list[str]:
    sel = st.session_state.col_selected_by_sheet.get(sheet, {})
    return [s.column for s in st.session_state.scans_by_sheet.get(sheet, []) if sel.get(s.column, False)]


def _run_for_column(df: pd.DataFrame, col: str, data_type: str) -> list[NormalizationCandidate]:
    normalizer = get_normalizer(data_type)
    values = [str(v) for v in df[col].dropna().tolist()]
    return normalizer.build_candidates(values)


# ---------------------------------------------------------------------------
# Шапка
# ---------------------------------------------------------------------------
st.title("🧪 Normalizer")
st.caption(
    "Проверка отдельных алгоритмов нормализации перед этапом анонимизации. "
    "Система сама распознаёт тип данных в каждой колонке и запускает нужный алгоритм."
)

# ---------------------------------------------------------------------------
# Переключатель режима (в сайдбаре) — показывается сразу, ещё до
# загрузки файла, чтобы пользователь видел доступные режимы.
# ---------------------------------------------------------------------------
mode = st.sidebar.radio(
    "Режим",
    options=["🧪 Нормализация", "🔍 Поиск аномалий", "📄 Документы (TXT/DOCX)"],
    key="app_mode",
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
# ---------------------------------------------------------------------------
# Режим: Нормализация текстовых документов (TXT / DOCX)
# ---------------------------------------------------------------------------
if mode == "📄 Документы (TXT/DOCX)":
    import json as _json
    from normalizers import normalize_document, normalize_docx, extract_text_from_txt, DOCUMENT_TYPE_LABELS
    from normalizers.document import normalize_docx

    st.header("📄 Нормализация текстовых документов")
    st.caption(
        "Загрузите TXT или DOCX-файл. Система найдёт ФИО, адреса, телефоны, "
        "ИНН, email и названия организаций, нормализует их и вернёт "
        "исправленный документ + JSON-маппинг."
    )

    doc_file = st.file_uploader(
        "Выберите файл (.txt или .docx)",
        type=["txt", "docx"],
        accept_multiple_files=False,
        key="doc_uploader",
    )

    if doc_file is None:
        st.info("Загрузите файл, чтобы продолжить.")
        st.stop()

    # Выбор типов сущностей
    st.subheader("Настройка поиска")
    all_doc_types = list(DOCUMENT_TYPE_LABELS.keys())
    selected_types = st.multiselect(
        "Типы сущностей для поиска",
        options=all_doc_types,
        default=all_doc_types,
        format_func=lambda x: DOCUMENT_TYPE_LABELS[x],
        key="doc_entity_types",
    )

    if not selected_types:
        st.warning("Выберите хотя бы один тип сущностей.")
        st.stop()

    file_bytes = doc_file.read()
    file_ext = Path(doc_file.name).suffix.lower()

    # Предпросмотр исходного текста
    with st.expander("📖 Предпросмотр исходного документа", expanded=False):
        if file_ext == ".txt":
            preview_text = extract_text_from_txt(file_bytes)
        else:
            try:
                preview_text, _ = extract_text_from_docx(file_bytes)
            except Exception as e:
                preview_text = f"Ошибка чтения: {e}"
        st.text_area("Исходный текст", value=preview_text, height=250, disabled=True, key="doc_preview")

    run_doc = st.button("▶ Запустить нормализацию документа", type="primary", key="doc_run")

    if run_doc:
        with st.spinner("Анализирую документ…"):
            try:
                if file_ext == ".txt":
                    original_text = extract_text_from_txt(file_bytes)
                    result = normalize_document(original_text, selected_types)
                    normalized_bytes = result.normalized_text.encode("utf-8")
                    mapping_dict = result.mapping
                    entities = result.entities
                    stats = result.stats
                    download_ext = ".txt"
                    download_mime = "text/plain"
                else:
                    normalized_bytes, mapping_dict = normalize_docx(file_bytes, selected_types)
                    # Для статистики пересчитываем по маппингу
                    stats = {k: 0 for k in DOCUMENT_TYPE_LABELS}
                    for item in mapping_dict.get("by_type", {}).values():
                        pass
                    stats = mapping_dict.get("meta", {}).get("stats_by_type", stats)
                    entities = []
                    for etype, items in mapping_dict.get("by_type", {}).items():
                        for it in items:
                            from normalizers.document import EntityMatch
                            entities.append(EntityMatch(
                                entity_type=etype,
                                original=it["original"],
                                canonical=it["canonical"],
                                start=it.get("position", 0),
                                end=it.get("position", 0) + len(it["original"]),
                                confidence=it.get("confidence", 1.0),
                            ))
                    download_ext = ".docx"
                    download_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

                st.session_state["doc_result_bytes"] = normalized_bytes
                st.session_state["doc_result_mapping"] = mapping_dict
                st.session_state["doc_result_stats"] = stats
                st.session_state["doc_result_entities"] = entities
                st.session_state["doc_result_ext"] = download_ext
                st.session_state["doc_result_mime"] = download_mime
                st.session_state["doc_result_name"] = doc_file.name

            except Exception as e:
                st.error(f"Ошибка при нормализации: {e}")
                st.stop()

    # Показываем результаты если они есть
    if st.session_state.get("doc_result_bytes") is not None:
        stats = st.session_state["doc_result_stats"]
        mapping_dict = st.session_state["doc_result_mapping"]
        entities = st.session_state["doc_result_entities"]
        normalized_bytes = st.session_state["doc_result_bytes"]
        download_ext = st.session_state["doc_result_ext"]
        download_mime = st.session_state["doc_result_mime"]
        base_doc_name = Path(st.session_state["doc_result_name"]).stem

        total_found = sum(stats.values())
        st.success(f"✅ Нормализация завершена. Найдено сущностей: **{total_found}**")

        # Метрики по типам
        cols_m = st.columns(len(DOCUMENT_TYPE_LABELS))
        for col_m, (etype, label) in zip(cols_m, DOCUMENT_TYPE_LABELS.items()):
            col_m.metric(label, stats.get(etype, 0))

        # Таблица найденных сущностей
        if entities:
            st.subheader("Найденные сущности")
            entity_rows = [
                {
                    "Тип": DOCUMENT_TYPE_LABELS.get(e.entity_type, e.entity_type),
                    "Оригинал": e.original,
                    "Каноническое значение": e.canonical,
                    "Уверенность": f"{e.confidence:.0%}",
                    "Позиция": e.start,
                }
                for e in sorted(entities, key=lambda x: x.start)
            ]
            st.dataframe(
                pd.DataFrame(entity_rows),
                use_container_width=True,
                hide_index=True,
            )

        # Предпросмотр нормализованного текста (только для TXT)
        if download_ext == ".txt":
            with st.expander("📝 Нормализованный текст", expanded=True):
                st.text_area(
                    "Результат",
                    value=normalized_bytes.decode("utf-8"),
                    height=300,
                    disabled=True,
                    key="doc_result_preview",
                )

        # Скачивание
        st.subheader("Скачать результаты")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                f"⬇ Скачать нормализованный документ ({download_ext})",
                data=normalized_bytes,
                file_name=f"{base_doc_name}__normalized{download_ext}",
                mime=download_mime,
                use_container_width=True,
                key="doc_dl_file",
            )
        with dl_col2:
            mapping_bytes = _json.dumps(mapping_dict, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button(
                "⬇ Скачать JSON-маппинг",
                data=mapping_bytes,
                file_name=f"{base_doc_name}__mapping.json",
                mime="application/json",
                use_container_width=True,
                key="doc_dl_mapping",
            )

    st.stop()

if not st.session_state.sheets_data:
    st.info("Загрузите Excel-файл, чтобы продолжить.")
    st.stop()

if mode == "🔍 Поиск аномалий":
    st.subheader("Проверка данных на аномалии")
    st.caption(
        "Сканирование листов на пустые строки, дубликаты, нетипичные значения в "
        "числовых/текстовых колонках и т.п. Работает отдельно от нормализации, "
        "чтобы не замедлять основной воркфлоу."
    )

    all_sheets = list(st.session_state.sheets_data.keys())
    a_sheets = st.multiselect(
        "Листы для проверки (можно выбрать несколько)",
        options=all_sheets,
        default=all_sheets,
        key="anomaly_sheets",
    )
    if not a_sheets:
        st.info("Выберите хотя бы один лист.")
        st.stop()

    total_rows = sum(len(st.session_state.sheets_data[s]) for s in a_sheets)
    st.caption(f"Выбрано листов: **{len(a_sheets)}** · строк всего: **{total_rows:,}**".replace(",", " "))

    col_a, col_b = st.columns([3, 2])
    with col_a:
        use_sample = st.checkbox(
            "Ограничить сэмплом (для больших файлов)",
            value=total_rows > 50_000,
            key="anomaly_use_sample",
        )
    with col_b:
        sample_size = st.number_input(
            "Размер сэмпла (на лист)", min_value=1_000, max_value=500_000,
            value=50_000, step=5_000, key="anomaly_sample_size",
            disabled=not use_sample,
        )

    run = st.button("Запустить поиск аномалий", type="primary", key="anomaly_run")

    if run:
        results: dict[str, list] = {}
        progress = st.progress(0.0)
        for i, sh in enumerate(a_sheets, start=1):
            with st.spinner(f"[{i}/{len(a_sheets)}] Лист «{sh}»…"):
                results[sh] = scan_anomalies(
                    st.session_state.sheets_data[sh],
                    sample_size=int(sample_size) if use_sample else None,
                )
            progress.progress(i / len(a_sheets))
        progress.empty()
        st.session_state[f"anomaly_results::{st.session_state.uploaded_name}"] = results

    all_results = st.session_state.get(f"anomaly_results::{st.session_state.uploaded_name}")
    all_results = {s: all_results[s] for s in a_sheets if all_results and s in all_results} if all_results else None

    if not all_results:
        st.info("Нажмите «Запустить поиск аномалий», чтобы проверить выбранные листы.")
        st.stop()

    # Сводка по всем листам
    sev_icon = {"high": "🔴", "medium": "🟡", "low": "⚪"}
    total = sum(g.count for gs in all_results.values() for g in gs)
    by_sev = {sev: sum(g.count for gs in all_results.values() for g in gs if g.severity == sev)
              for sev in ("high", "medium", "low")}
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Всего находок", total)
    m2.metric("🔴 Критичные", by_sev["high"])
    m3.metric("🟡 Средние", by_sev["medium"])
    m4.metric("⚪ Незначительные", by_sev["low"])

    report_rows: list[dict] = []
    # Отдельная вкладка под каждый лист
    tabs = st.tabs([f"{s} ({sum(g.count for g in all_results[s])})" for s in a_sheets])
    for tab, sh in zip(tabs, a_sheets):
        with tab:
            groups = all_results[sh]
            if not groups:
                st.success("Аномалий не найдено — лист выглядит чистым.")
                continue
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
                            "Лист": sh,
                            "Тип": g.title,
                            "Важность": g.severity,
                            "Строка": e.row,
                            "Колонка": e.column,
                            "Значение": "" if e.value is None else str(e.value),
                        })

    if report_rows:
        csv = pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Скачать отчёт (CSV, по всем листам)",
            data=csv,
            file_name="anomalies_report.csv",
            mime="text/csv",
            key="anomaly_report_dl",
        )

    st.stop()


# ---------------------------------------------------------------------------
# Режим: Нормализация (несколько листов)
# ---------------------------------------------------------------------------
# Шаг 2. Выбор листов + автоматическое распознавание колонок
# ---------------------------------------------------------------------------
st.header("2. Выбор листов и автоматическое распознавание колонок")

all_sheets = list(st.session_state.sheets_data.keys())
selected_sheets = st.multiselect(
    "Листы для нормализации (можно выбрать несколько — нормализация пройдёт по всем)",
    options=all_sheets,
    default=st.session_state.sheets or all_sheets[:1],
    key="norm_sheets",
)

# Синхронизируем выбор листов в состояние и чистим устаревшие записи.
st.session_state.sheets = selected_sheets
for container_key in (
    "scans_by_sheet", "col_selected_by_sheet", "col_type_overrides_by_sheet",
    "results_by_sheet", "selections_by_sheet", "canonicals_by_sheet",
    "normalized_by_sheet",
):
    container = st.session_state.get(container_key) or {}
    for stale in list(container):
        if stale not in selected_sheets:
            container.pop(stale, None)
    st.session_state[container_key] = container

if not selected_sheets:
    st.info("Выберите хотя бы один лист выше, чтобы продолжить.")
    st.stop()

# Гарантируем, что для каждого выбранного листа есть свежий скан.
for sh in selected_sheets:
    _ensure_sheet_state(sh)
    if not st.session_state.scans_by_sheet.get(sh):
        with st.spinner(f"Анализирую колонки листа «{sh}»…"):
            _scan_sheet(sh, st.session_state.sheets_data[sh])

# Кнопка пересканирования всех выбранных листов.
rescan_col1, rescan_col2 = st.columns([5, 1])
with rescan_col1:
    st.caption(
        f"Выбрано листов: **{len(selected_sheets)}**. Галочки и типы выставлены автоматически "
        "по результатам автодетекта — можно подправить в вкладке каждого листа ниже."
    )
with rescan_col2:
    if st.button("↻ Пересканировать все", help="Сбросить правки и выставить галочки по автодетекту"):
        for sh in selected_sheets:
            st.session_state.col_selected_by_sheet[sh] = {}
            st.session_state.col_type_overrides_by_sheet[sh] = {}
            _scan_sheet(sh, st.session_state.sheets_data[sh])
        st.rerun()


# ---------------------------------------------------------------------------
# Шаг 3. По-листовая настройка: колонки + тип алгоритма (вкладки на лист)
# ---------------------------------------------------------------------------
st.header("3. Настройка по листам")
st.caption(
    "Каждая вкладка — один лист. В ней можно включить/выключить колонки и при "
    "необходимости переопределить тип алгоритма."
)

type_options_with_auto = ["(авто)"] + list(REGISTRY.keys())
sheet_tabs = st.tabs([f"📋 {sh}" for sh in selected_sheets])

for tab, sh in zip(sheet_tabs, selected_sheets):
    with tab:
        df_sh = st.session_state.sheets_data[sh]
        scans = st.session_state.scans_by_sheet.get(sh, [])
        recommended_cnt = sum(1 for s in scans if s.recommended)
        st.caption(
            f"Найдено колонок: **{len(scans)}** · рекомендовано: **{recommended_cnt}** · "
            f"строк в листе: **{len(df_sh):,}**".replace(",", " ")
        )

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
                "Включить": st.session_state.col_selected_by_sheet[sh].get(s.column, s.recommended),
                "Колонка": s.column,
                "Распознанный тип": type_label,
                "Уверенность": f"{s.confidence:.0%}" if s.detected_type else "—",
                "Оценка": badge,
                "Непустых значений": s.non_empty,
            })

        if not scan_rows:
            st.warning("В листе не обнаружено колонок.")
            continue

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
            key=f"scan_editor::{sh}",
        )
        # Синхронизируем изменения галочек обратно в session_state
        for _, row in edited_scan.iterrows():
            st.session_state.col_selected_by_sheet[sh][str(row["Колонка"])] = bool(row["Включить"])

        cols_sh = _selected_columns(sh)
        if not cols_sh:
            st.info("Отметьте хотя бы одну колонку выше.")
            continue

        st.caption("Превью первых 10 строк по выбранным колонкам:")
        st.dataframe(df_sh[cols_sh].head(10), use_container_width=True, hide_index=True)

        st.markdown("**Тип алгоритма для каждой колонки.** При необходимости переопределите автодетект.")
        for col in cols_sh:
            scan = _get_scan(sh, col)
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
                current_override = st.session_state.col_type_overrides_by_sheet[sh].get(col)
                default_index = 0
                if current_override:
                    default_index = 1 + list(REGISTRY.keys()).index(current_override)

                def _fmt(opt: str, _detected=detected) -> str:
                    if opt == "(авто)":
                        if _detected:
                            return f"(авто: {LABELS[_detected]})"
                        return "(не определено)"
                    return LABELS[opt]

                choice = st.selectbox(
                    "Тип алгоритма",
                    options=type_options_with_auto,
                    index=default_index,
                    format_func=_fmt,
                    key=f"type_override::{sh}::{col}",
                    label_visibility="collapsed",
                )
                st.session_state.col_type_overrides_by_sheet[sh][col] = None if choice == "(авто)" else choice


# Сводка по всем листам: что выбрано, где нет типа.
per_sheet_cols: dict[str, list[str]] = {sh: _selected_columns(sh) for sh in selected_sheets}
total_cols = sum(len(v) for v in per_sheet_cols.values())
missing: list[tuple[str, str]] = []
for sh, cols_sh in per_sheet_cols.items():
    for c in cols_sh:
        if not _effective_type(sh, c):
            missing.append((sh, c))

if total_cols == 0:
    st.info("Не выбрано ни одной колонки ни на одном листе.")
    st.stop()

if missing:
    st.warning(
        "Не определён тип для колонок: "
        + ", ".join(f"`{sh} → {c}`" for sh, c in missing)
        + ". Переопределите тип вручную — без этого запуск невозможен."
    )


# ---------------------------------------------------------------------------
# Шаг 4. Запуск алгоритмов по всем выбранным листам
# ---------------------------------------------------------------------------
st.header("4. Запуск алгоритмов")

run_disabled = bool(missing)
run_clicked = st.button(
    f"▶ Запустить нормализацию для {total_cols} колонок на {len(selected_sheets)} листах",
    type="primary",
    disabled=run_disabled,
)

if run_clicked:
    # Полный сброс старых результатов по всем выбранным листам.
    for sh in selected_sheets:
        st.session_state.results_by_sheet[sh] = {}
        st.session_state.selections_by_sheet[sh] = {}
        st.session_state.canonicals_by_sheet[sh] = {}
    st.session_state.normalized_by_sheet = {}
    st.session_state.mapping_payload = None
    st.session_state.applied = False

    total_tasks = total_cols
    done = 0
    progress = st.progress(0.0)
    for sh in selected_sheets:
        df_sh = st.session_state.sheets_data[sh]
        for col in per_sheet_cols[sh]:
            data_type = _effective_type(sh, col)
            with st.spinner(
                f"[{done + 1}/{total_tasks}] «{sh}» · «{col}» · алгоритм «{LABELS[data_type]}»…"
            ):
                cands = _run_for_column(df_sh, col, data_type)
            st.session_state.results_by_sheet[sh][col] = cands
            st.session_state.selections_by_sheet[sh][col] = {
                j: (len(c.variants) > 1) for j, c in enumerate(cands)
            }
            st.session_state.canonicals_by_sheet[sh][col] = {
                j: c.canonical for j, c in enumerate(cands)
            }
            done += 1
            progress.progress(done / max(total_tasks, 1))
    progress.empty()
    st.success(f"Обработано колонок: {done} на {len(selected_sheets)} листах.")


# ---------------------------------------------------------------------------
# Шаг 5. Кандидаты по каждой колонке каждого листа (вкладки)
# ---------------------------------------------------------------------------
has_any_results = any(st.session_state.results_by_sheet.get(sh) for sh in selected_sheets)

if has_any_results:
    st.header("5. Кандидаты на объединение")
    st.caption(
        "Вкладки разбиты по листам. Внутри каждой — по одной вкладке на колонку. "
        "Отметьте группы, которые действительно нужно объединить."
    )

    # Оставляем только листы, где есть результаты.
    sheets_with_res = [sh for sh in selected_sheets if st.session_state.results_by_sheet.get(sh)]
    res_sheet_tabs = st.tabs([f"📋 {sh}" for sh in sheets_with_res])

    for res_tab, sh in zip(res_sheet_tabs, sheets_with_res):
        with res_tab:
            results = st.session_state.results_by_sheet.get(sh, {})
            processed_cols = [c for c in per_sheet_cols.get(sh, []) if c in results]
            if not processed_cols:
                st.info("Для этого листа нет обработанных колонок.")
                continue

            col_tab_labels = [
                f"{c} · {LABELS[_effective_type(sh, c)]}" for c in processed_cols
            ]
            col_tabs = st.tabs(col_tab_labels)

            for col_tab, col in zip(col_tabs, processed_cols):
                with col_tab:
                    candidates: list[NormalizationCandidate] = results[col]
                    if not candidates:
                        st.warning(
                            "Алгоритм не нашёл ни одного кандидата — колонка пуста или "
                            "значения некорректны."
                        )
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
                        key=f"filter::{sh}::{col}",
                    )

                    bulk_a, bulk_b, _ = st.columns([1, 1, 4])
                    with bulk_a:
                        if st.button("✓ Отметить все", key=f"check_all::{sh}::{col}"):
                            for i in range(len(candidates)):
                                st.session_state.selections_by_sheet[sh][col][i] = True
                            st.rerun()
                    with bulk_b:
                        if st.button("✗ Снять все", key=f"uncheck_all::{sh}::{col}"):
                            for i in range(len(candidates)):
                                st.session_state.selections_by_sheet[sh][col][i] = False
                            st.rerun()

                    rows = []
                    for i, c in enumerate(candidates):
                        if filter_mode == "Только группы с вариантами" and len(c.variants) <= 1:
                            continue
                        rows.append({
                            "id": i,
                            "Применить": st.session_state.selections_by_sheet[sh][col].get(i, False),
                            "Каноническое значение": st.session_state.canonicals_by_sheet[sh][col].get(i, c.canonical),
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
                        key=f"editor::{sh}::{col}",
                    )
                    for _, row in edited.iterrows():
                        idx = int(row["id"])
                        st.session_state.selections_by_sheet[sh][col][idx] = bool(row["Применить"])
                        st.session_state.canonicals_by_sheet[sh][col][idx] = str(row["Каноническое значение"])


# ---------------------------------------------------------------------------
# Шаг 6. Применение и экспорт (по всем выбранным листам сразу)
# ---------------------------------------------------------------------------
if has_any_results:
    st.header("6. Применение и экспорт")

    apply_clicked = st.button(
        "🛠 Выполнить нормализацию по всем выбранным листам",
        type="primary",
    )

    if apply_clicked:
        sheets_payload: dict[str, dict] = {}
        grand_total_changed = 0

        for sh in selected_sheets:
            results = st.session_state.results_by_sheet.get(sh, {})
            if not results:
                continue
            df_sh = st.session_state.sheets_data[sh]
            normalized_df = df_sh.copy()
            per_column_payload: dict[str, dict] = {}
            sheet_changed = 0

            for col, candidates in results.items():
                selections = st.session_state.selections_by_sheet.get(sh, {}).get(col, {})
                canonicals = st.session_state.canonicals_by_sheet.get(sh, {}).get(col, {})

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
                sheet_changed += changed
                normalized_df[col] = new_series

                scan = _get_scan(sh, col)
                per_column_payload[col] = {
                    "data_type": _effective_type(sh, col),
                    "data_type_label": LABELS[_effective_type(sh, col)],
                    "auto_detected": scan.detected_type if scan else None,
                    "auto_detected_scores": scan.scores if scan else {},
                    "auto_recommended": scan.recommended if scan else False,
                    "total_candidates": len(candidates),
                    "applied_groups": len(applied_groups),
                    "values_changed": changed,
                    "mapping": mapping,
                    "groups": applied_groups,
                }

            st.session_state.normalized_by_sheet[sh] = normalized_df
            grand_total_changed += sheet_changed
            sheets_payload[sh] = {
                "columns": list(results.keys()),
                "values_changed": sheet_changed,
                "per_column": per_column_payload,
            }

        st.session_state.mapping_payload = {
            "meta": {
                "source_file": st.session_state.uploaded_name,
                "sheets": list(sheets_payload.keys()),
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "total_values_changed": grand_total_changed,
            },
            "sheets": sheets_payload,
        }
        st.session_state.applied = True

    if st.session_state.applied and st.session_state.normalized_by_sheet:
        payload = st.session_state.mapping_payload
        total_cols_applied = sum(len(p["columns"]) for p in payload["sheets"].values())
        st.success(
            f"Нормализация выполнена. Заменено значений всего: "
            f"**{payload['meta']['total_values_changed']}** "
            f"по **{total_cols_applied}** колонкам на **{len(payload['sheets'])}** листах."
        )

        # Сравнение «до/после» — отдельная вкладка под каждый лист.
        st.subheader("Сравнение «до/после» (первые 15 строк)")
        comp_tabs = st.tabs([f"📋 {sh}" for sh in payload["sheets"].keys()])
        for comp_tab, sh in zip(comp_tabs, payload["sheets"].keys()):
            with comp_tab:
                cols_list = payload["sheets"][sh]["columns"]
                if not cols_list:
                    st.info("Для этого листа не применялось ни одной колонки.")
                    continue
                df_sh = st.session_state.sheets_data[sh]
                norm_df = st.session_state.normalized_by_sheet[sh]
                before = df_sh[cols_list].head(15).reset_index(drop=True)
                after = norm_df[cols_list].head(15).reset_index(drop=True)
                before.columns = [f"{c} (до)" for c in before.columns]
                after.columns = [f"{c} (после)" for c in after.columns]
                ordered_cols = []
                for c in cols_list:
                    ordered_cols.append(f"{c} (до)")
                    ordered_cols.append(f"{c} (после)")
                combined = pd.concat([before, after], axis=1)[ordered_cols]
                st.dataframe(combined, use_container_width=True, hide_index=True)

        # Скачивание Excel (все листы источника; выбранные — нормализованные).
        xlsx_buffer = io.BytesIO()
        with pd.ExcelWriter(xlsx_buffer, engine="xlsxwriter") as writer:
            for name, sdf in st.session_state.sheets_data.items():
                if name in st.session_state.normalized_by_sheet:
                    st.session_state.normalized_by_sheet[name].to_excel(
                        writer, sheet_name=name, index=False
                    )
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
2. Выбираете один или несколько листов. Система **сама находит колонки** для
   нормализации и определяет тип по содержимому.
3. При необходимости корректируете галочки или тип алгоритма вручную.
4. Запускаете — алгоритмы отрабатывают по всем выбранным листам сразу.
5. Подтверждаете кандидатов галочками.
6. Скачиваете Excel и JSON-справочник.

**Поддерживаемые типы — отдельные алгоритмы:**
- **ФИО** — `natasha` + `pymorphy3`, объединение полной и инициальной форм.
- **ИНН** — regex + контрольная сумма ФНС (10 / 12 знаков).
- **Адреса** — разворот сокращений + fuzzy-кластеризация.
- **Телефоны** — `phonenumbers`, E.164, поддержка добавочных.
- **Организации** — извлечение ОПФ + fuzzy по имени без ОПФ.
- **Email** — алиасы доменов, правила Gmail/Яндекс/Outlook.
- **Текстовые значения** — универсальный нормализатор произвольных
  текстовых колонок (склады, номенклатурные группы и пр.).

**Автодетект.** Порог уверенности 60%. Если ни один тип не прошёл порог,
система берёт лучший (от 40%) или предлагает выбрать вручную.
        """
    )
    st.caption("Данные хранятся только в текущей сессии и не сохраняются.")
