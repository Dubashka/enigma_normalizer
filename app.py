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
from utils.text_extract import (
    SUPPORTED_EXTENSIONS as TEXT_DOC_EXTS,
    extract_document,
    rebuild_document,
)
from utils.text_scan import (
    apply_replacements as apply_text_replacements,
    group_by_type,
    scan_text_document,
)


st.set_page_config(
    page_title="Enigma Normalizer",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Глобальные стили — Reksoft Corporate Design System
# ---------------------------------------------------------------------------

def _inject_css():
    st.markdown(
        """
        <style>
        /* ---- Reksoft Design Tokens ---- */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --primary:        #CF0522;  /* Reksoft Red */
            --primary-hover:  #a8041c;
            --success:        #2F9E3F;
            --warning:        #C007A7;
            --text:           #000000;
            --text-muted:     #8C8C8C;
            --surface:        #F5F4F4;
            --bg:             #FFFFFF;
            --header-bg:      #000000;
            --border:         1px solid #E0E0E0;
            --border-color:   #E0E0E0;
            --radius:         4px;
            --font:           'Stapel', 'Inter', sans-serif;
        }

        html, body, [class*="css"] {
            font-family: var(--font) !important;
        }

        /* ---- Шапка приложения — чёрная полоса ---- */
        .app-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: var(--header-bg);
            padding: 0.85rem 1.5rem;
            margin-bottom: 1.5rem;
            margin-left: -1rem;
            margin-right: -1rem;
        }
        .app-header .app-title {
            font-size: 1rem;
            font-weight: 500;
            color: var(--text-muted);
            letter-spacing: 0.02em;
            margin: 0;
        }
        .app-header .app-logo {
            font-size: 0.9rem;
            font-weight: 700;
            color: #FFFFFF;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        /* ---- Степпер прогресса ---- */
        .step-progress {
            display: flex;
            align-items: center;
            gap: 0;
            padding: 1rem 0 1.5rem;
            overflow-x: auto;
        }
        .step-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.3rem;
            min-width: 80px;
            flex: 1;
            position: relative;
            text-align: center;
        }
        .step-item:not(:last-child)::after {
            content: '';
            position: absolute;
            top: 14px;
            left: calc(50% + 14px);
            width: calc(100% - 28px);
            height: 1px;
            background: var(--text-muted);
            z-index: 0;
        }
        .step-item.active:not(:last-child)::after,
        .step-item.done:not(:last-child)::after {
            background: var(--primary);
        }
        .step-circle {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            font-weight: 700;
            border: 1px solid var(--text-muted);
            background: var(--bg);
            color: var(--text-muted);
            position: relative;
            z-index: 1;
        }
        .step-item.done .step-circle {
            background: var(--text-muted);
            border-color: var(--text-muted);
            color: #fff;
        }
        .step-item.active .step-circle {
            background: var(--primary);
            border-color: var(--primary);
            color: #fff;
        }
        .step-label {
            font-size: 0.7rem;
            color: var(--text-muted);
            line-height: 1.2;
        }
        .step-item.active .step-label {
            color: var(--primary);
            font-weight: 600;
        }
        .step-item.done .step-label {
            color: var(--text-muted);
        }

        /* ---- Заголовки шагов ---- */
        .step-header {
            display: flex;
            align-items: center;
            gap: 0.6rem;
            padding: 0.75rem 1rem;
            background: var(--bg);
            border: var(--border);
            border-left: 3px solid var(--primary);
            border-radius: var(--radius);
            margin: 1.25rem 0 0.75rem;
        }
        .step-header .step-num {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: var(--primary);
            color: #fff;
            font-size: 0.75rem;
            font-weight: 700;
            flex-shrink: 0;
        }
        .step-header .step-title {
            font-size: 1rem;
            font-weight: 600;
            color: var(--text);
            margin: 0;
        }
        .step-header .step-hint {
            font-size: 0.78rem;
            color: var(--text-muted);
            margin: 0;
            margin-left: auto;
        }

        /* ---- Карточки метрик ---- */
        .metric-row {
            display: flex;
            gap: 1rem;
            margin: 0.75rem 0;
            flex-wrap: wrap;
        }
        .metric-card {
            flex: 1;
            min-width: 120px;
            padding: 0.9rem 1rem;
            background: var(--bg);
            border: var(--border);
            border-radius: var(--radius);
            text-align: center;
        }
        .metric-card .mc-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text);
            line-height: 1.1;
        }
        .metric-card .mc-label {
            font-size: 0.78rem;
            color: var(--text-muted);
            margin-top: 0.2rem;
        }
        .metric-card.high .mc-value  { color: var(--primary); }
        .metric-card.medium .mc-value { color: var(--warning); }
        .metric-card.low .mc-value    { color: var(--text-muted); }
        .metric-card.total { border-left: 3px solid var(--primary); }

        /* ---- Бейджи ---- */
        .badge {
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            padding: 0.15rem 0.5rem;
            border-radius: var(--radius);
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.02em;
        }
        .badge-high    { background: #fde8ec; color: var(--primary); border: 1px solid var(--primary); }
        .badge-medium  { background: #fce8f9; color: var(--warning); border: 1px solid var(--warning); }
        .badge-low     { background: var(--surface); color: var(--text-muted); border: 1px solid var(--border-color); }
        .badge-success { background: #e6f4e8; color: var(--success); border: 1px solid var(--success); }
        .badge-primary { background: #fde8ec; color: var(--primary); border: 1px solid var(--primary); }

        /* ---- Пустое состояние ---- */
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            padding: 2.5rem 1rem;
            color: var(--text-muted);
        }
        .empty-state .es-icon  { font-size: 2.5rem; margin-bottom: 0.75rem; opacity: 0.5; }
        .empty-state .es-title { font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: 0.35rem; }
        .empty-state .es-desc  { font-size: 0.85rem; max-width: 40ch; line-height: 1.5; }

        /* ---- Sidebar ---- */
        [data-testid="stSidebar"] {
            background: var(--surface) !important;
            border-right: var(--border);
        }
        .sidebar-section {
            background: var(--bg);
            border: var(--border);
            border-radius: var(--radius);
            padding: 0.75rem 0.9rem;
            margin-bottom: 0.75rem;
            font-size: 0.82rem;
            color: var(--text);
            line-height: 1.6;
        }
        .sidebar-section h4 {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            color: var(--text-muted);
            margin: 0 0 0.5rem;
        }
        .sidebar-section ul { padding-left: 1.1em; margin: 0; }
        .sidebar-section li { margin-bottom: 0.2rem; }

        /* ---- Режим-радио кнопки в сайдбаре ---- */
        [data-testid="stSidebar"] [data-testid="stRadio"] label {
            font-size: 0.9rem !important;
        }

        /* ---- Таблицы ---- */
        [data-testid="stDataFrame"] table td,
        [data-testid="stDataFrame"] table th {
            font-variant-numeric: tabular-nums;
        }

        /* ---- Скрыть якорные ссылки ---- */
        h1 a, h2 a, h3 a { display: none !important; }

        /* ---- Кнопки скачивания ---- */
        [data-testid="stDownloadButton"] button {
            border: 1px solid var(--primary) !important;
            color: var(--primary) !important;
            background: var(--bg) !important;
            font-weight: 600 !important;
            border-radius: var(--radius) !important;
        }
        [data-testid="stDownloadButton"] button:hover {
            background: var(--primary) !important;
            color: #fff !important;
        }

        /* ---- Кнопка «primary» ---- */
        [data-testid="stButton"] button[kind="primary"] {
            background: var(--primary) !important;
            border-color: var(--primary) !important;
            color: #fff !important;
            border-radius: var(--radius) !important;
        }
        [data-testid="stButton"] button[kind="primary"]:hover {
            background: var(--primary-hover) !important;
            border-color: var(--primary-hover) !important;
        }

        /* ---- Обычные кнопки (secondary) ---- */
        [data-testid="stButton"] button[kind="secondary"] {
            background: var(--bg) !important;
            border: 1px solid var(--primary) !important;
            color: var(--primary) !important;
            border-radius: var(--radius) !important;
            font-weight: 500 !important;
        }
        [data-testid="stButton"] button[kind="secondary"]:hover {
            background: var(--primary) !important;
            color: #fff !important;
        }

        /* ---- Expanders ---- */
        [data-testid="stExpander"] details summary {
            font-weight: 600;
            color: var(--text);
        }
        [data-testid="stExpander"] details {
            border: var(--border) !important;
            border-radius: var(--radius) !important;
        }

        /* ---- Заголовки st.header ---- */
        [data-testid="stHeadingWithActionElements"] h2 {
            font-size: 1.15rem !important;
            font-weight: 700 !important;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.35rem;
            margin-top: 1.5rem !important;
        }

        /* ---- Основной контейнер ---- */
        .main .block-container {
            padding-top: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


_inject_css()


# ---------------------------------------------------------------------------
# UI-хелперы
# ---------------------------------------------------------------------------

def _app_header():
    """Шапка в стиле Рексофт: чёрный фон, название слева (серым), логотип справа (белым)."""
    st.markdown(
        '<div class="app-header">'
        '<p class="app-title">Enigma Normalizer</p>'
        '<span class="app-logo">Reksoft</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def _step_header(num: int, title: str, hint: str = "") -> None:
    """Рендерит стилизованный заголовок шага с номером."""
    hint_html = f'<span class="step-hint">{hint}</span>' if hint else ""
    st.markdown(
        f'<div class="step-header">'
        f'<span class="step-num">{num}</span>'
        f'<span class="step-title">{title}</span>'
        f'{hint_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _progress_stepper(current_step: int, steps: list[str]) -> None:
    """Рендерит визуальный степпер над контентом."""
    items = []
    for i, label in enumerate(steps, start=1):
        if i < current_step:
            cls = "done"
            circle = "✓"
        elif i == current_step:
            cls = "active"
            circle = str(i)
        else:
            cls = ""
            circle = str(i)
        items.append(
            f'<div class="step-item {cls}">'
            f'<div class="step-circle">{circle}</div>'
            f'<div class="step-label">{label}</div>'
            f'</div>'
        )
    html = '<div class="step-progress">' + "".join(items) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _badge(text: str, kind: str = "primary") -> str:
    """Возвращает HTML-бейдж."""
    return f'<span class="badge badge-{kind}">{text}</span>'


def _empty_state(icon: str, title: str, desc: str) -> None:
    st.markdown(
        f'<div class="empty-state">'
        f'<div class="es-icon">{icon}</div>'
        f'<div class="es-title">{title}</div>'
        f'<div class="es-desc">{desc}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Управление состоянием сессии
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "uploaded_name": None,
        "sheets_data": {},
        "sheets": [],
        "active_sheet": None,
        "scans_by_sheet": {},
        "col_selected_by_sheet": {},
        "col_type_overrides_by_sheet": {},
        "results_by_sheet": {},
        "selections_by_sheet": {},
        "canonicals_by_sheet": {},
        "applied": False,
        "normalized_by_sheet": {},
        "mapping_payload": None,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


_init_state()


# ---------------------------------------------------------------------------
# Хелперы данных
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _read_excel(file_bytes: bytes) -> dict[str, pd.DataFrame]:
    """Читаем Excel через calamine — в разы быстрее openpyxl на больших файлах."""
    for engine in ("calamine", "openpyxl"):
        try:
            xls = pd.ExcelFile(io.BytesIO(file_bytes), engine=engine)
            return {
                name: pd.read_excel(xls, sheet_name=name, dtype=object)
                for name in xls.sheet_names
            }
        except Exception:
            continue
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
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
    for container in (
        "scans_by_sheet", "col_selected_by_sheet", "col_type_overrides_by_sheet",
        "results_by_sheet", "selections_by_sheet", "canonicals_by_sheet",
    ):
        st.session_state[container].setdefault(sheet, [] if container == "scans_by_sheet" else {})


def _scan_sheet(sheet: str, df: pd.DataFrame) -> None:
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
# Шапка приложения
# ---------------------------------------------------------------------------
_app_header()

# ---------------------------------------------------------------------------
# Переключатель режима (в сайдбаре)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.07em;color:#8C8C8C;padding:0.5rem 0 0.4rem;">Режим работы</div>',
        unsafe_allow_html=True,
    )
    mode = st.radio(
        "Режим",
        options=[
            "🧪 Нормализация",
            "🔍 Поиск аномалий",
            "📄 Нормализация документов",
        ],
        key="app_mode",
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown(
        '<div class="sidebar-section">'
        '<h4>О сервисе</h4>'
        'Проверка алгоритмов нормализации перед анонимизацией в проекте <b>Enigma</b>. '
        'Данные хранятся только в текущей сессии.'
        '</div>'
        '<div class="sidebar-section">'
        '<h4>Поддерживаемые типы</h4>'
        '<ul>'
        '<li>🧑 ФИО</li>'
        '<li>🏢 Организации</li>'
        '<li>📍 Адреса</li>'
        '<li>📞 Телефоны</li>'
        '<li>🪪 ИНН</li>'
        '<li>✉️ Email</li>'
        '<li>📝 Текстовые значения</li>'
        '</ul>'
        '</div>',
        unsafe_allow_html=True,
    )

if mode == "📄 Нормализация документов":
    from text_doc_workflow import run_text_document_mode
    run_text_document_mode()
    st.stop()


# ---------------------------------------------------------------------------
# Вычисляем текущий шаг для степпера
# ---------------------------------------------------------------------------
def _current_step() -> int:
    if not st.session_state.sheets_data:
        return 1
    if not st.session_state.sheets:
        return 2
    has_scans = any(st.session_state.scans_by_sheet.get(sh) for sh in st.session_state.sheets)
    if not has_scans:
        return 2
    has_results = any(st.session_state.results_by_sheet.get(sh) for sh in st.session_state.sheets)
    if not has_results:
        if mode == "🔍 Поиск аномалий":
            return 3
        return 3
    if not st.session_state.applied:
        return 4
    return 5


_STEPS_NORM = ["Загрузка", "Листы", "Настройка", "Запуск", "Результат"]
_STEPS_ANOM = ["Загрузка", "Параметры", "Результат"]

if mode == "🔍 Поиск аномалий":
    anom_step = 1 if not st.session_state.sheets_data else 2
    all_anom = st.session_state.get(f"anomaly_results::{st.session_state.uploaded_name}")
    if all_anom:
        anom_step = 3
    _progress_stepper(anom_step, _STEPS_ANOM)
else:
    _progress_stepper(_current_step(), _STEPS_NORM)


# ---------------------------------------------------------------------------
# Шаг 1. Загрузка файла
# ---------------------------------------------------------------------------
_step_header(1, "Загрузка Excel-файла")

uploaded = st.file_uploader(
    "Выберите .xlsx файл",
    type=["xlsx", "xls"],
    accept_multiple_files=False,
    label_visibility="collapsed",
    help="Поддерживаются форматы .xlsx и .xls",
)

if uploaded is not None:
    if st.session_state.uploaded_name != uploaded.name:
        _reset_after_upload()
        st.session_state.uploaded_name = uploaded.name
        with st.spinner("Читаю файл…"):
            st.session_state.sheets_data = _read_excel(uploaded.getvalue())
    sheet_count = len(st.session_state.sheets_data)
    st.success(
        f"✅ **{uploaded.name}** — {sheet_count} {'лист' if sheet_count == 1 else 'листа' if sheet_count < 5 else 'листов'}"
    )

if not st.session_state.sheets_data:
    _empty_state(
        "📂",
        "Файл не загружен",
        "Загрузите Excel-файл (.xlsx или .xls), чтобы начать нормализацию.",
    )
    st.stop()


# ---------------------------------------------------------------------------
# Режим: Поиск аномалий
# ---------------------------------------------------------------------------
if mode == "🔍 Поиск аномалий":
    _step_header(2, "Параметры проверки")
    st.caption(
        "Сканирование на пустые строки, дубликаты, нетипичные значения "
        "в числовых/текстовых колонках."
    )

    all_sheets = list(st.session_state.sheets_data.keys())
    a_sheets = st.multiselect(
        "Листы для проверки",
        options=all_sheets,
        default=all_sheets,
        key="anomaly_sheets",
        help="Можно выбрать несколько листов одновременно",
    )
    if not a_sheets:
        _empty_state("📋", "Нет выбранных листов", "Выберите хотя бы один лист для проверки.")
        st.stop()

    total_rows = sum(len(st.session_state.sheets_data[s]) for s in a_sheets)
    st.caption(
        f"Выбрано листов: **{len(a_sheets)}** · строк всего: **{total_rows:,}**".replace(",", " ")
    )

    col_a, col_b = st.columns([3, 2])
    with col_a:
        use_sample = st.checkbox(
            "Ограничить сэмплом (для больших файлов)",
            value=total_rows > 50_000,
            key="anomaly_use_sample",
        )
    with col_b:
        sample_size = st.number_input(
            "Размер сэмпла (строк на лист)",
            min_value=1_000, max_value=500_000,
            value=50_000, step=5_000,
            key="anomaly_sample_size",
            disabled=not use_sample,
        )

    run = st.button("🔍 Запустить поиск аномалий", type="primary", key="anomaly_run")

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
    all_results = (
        {s: all_results[s] for s in a_sheets if s in all_results}
        if all_results else None
    )

    if not all_results:
        _empty_state(
            "🔍",
            "Результатов пока нет",
            "Нажмите «Запустить поиск аномалий», чтобы проверить выбранные листы.",
        )
        st.stop()

    _step_header(3, "Результаты проверки")

    # Метрики с цветовым кодированием
    sev_icon = {"high": "🔴", "medium": "🟡", "low": "⚪"}
    total = sum(g.count for gs in all_results.values() for g in gs)
    by_sev = {
        sev: sum(g.count for gs in all_results.values() for g in gs if g.severity == sev)
        for sev in ("high", "medium", "low")
    }
    st.markdown(
        '<div class="metric-row">'
        f'<div class="metric-card total"><div class="mc-value">{total}</div><div class="mc-label">Всего находок</div></div>'
        f'<div class="metric-card high"><div class="mc-value">{by_sev["high"]}</div><div class="mc-label">🔴 Критичные</div></div>'
        f'<div class="metric-card medium"><div class="mc-value">{by_sev["medium"]}</div><div class="mc-label">🟡 Средние</div></div>'
        f'<div class="metric-card low"><div class="mc-value">{by_sev["low"]}</div><div class="mc-label">⚪ Незначительные</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    report_rows: list[dict] = []
    tabs = st.tabs([f"{s} ({sum(g.count for g in all_results[s])})" for s in a_sheets])
    for tab, sh in zip(tabs, a_sheets):
        with tab:
            groups = all_results[sh]
            if not groups:
                st.success("✅ Аномалий не найдено — лист выглядит чистым.")
                continue
            for g in sorted(groups, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x.severity]):
                badge_html = _badge(
                    {"high": "🔴 критично", "medium": "🟡 среднее", "low": "⚪ низкое"}[g.severity],
                    g.severity,
                )
                with st.expander(
                    f"{sev_icon[g.severity]} {g.title} — {g.count} вхождений",
                    expanded=g.severity == "high",
                ):
                    st.markdown(f"{badge_html} {g.description}", unsafe_allow_html=True)
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
                        st.caption(
                            f"… и ещё {g.count - len(g.examples)} "
                            f"(показаны первые {len(g.examples)})"
                        )
                    for e in g.examples:
                        report_rows.append({
                            "Лист": sh, "Тип": g.title, "Важность": g.severity,
                            "Строка": e.row, "Колонка": e.column,
                            "Значение": "" if e.value is None else str(e.value),
                        })

    if report_rows:
        csv = pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Скачать полный отчёт (CSV)",
            data=csv,
            file_name="anomalies_report.csv",
            mime="text/csv",
            key="anomaly_report_dl",
            use_container_width=True,
        )

    st.stop()


# ---------------------------------------------------------------------------
# Режим: Нормализация
# ---------------------------------------------------------------------------

# Шаг 2. Выбор листов
# ---------------------------------------------------------------------------
_step_header(2, "Выбор листов", "Система автоматически распознаёт колонки")

all_sheets = list(st.session_state.sheets_data.keys())
selected_sheets = st.multiselect(
    "Листы для нормализации",
    options=all_sheets,
    default=st.session_state.sheets or all_sheets[:1],
    key="norm_sheets",
    help="Можно выбрать несколько — нормализация пройдёт по всем",
)

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
    _empty_state("📋", "Нет выбранных листов", "Выберите хотя бы один лист, чтобы продолжить.")
    st.stop()

for sh in selected_sheets:
    _ensure_sheet_state(sh)
    if not st.session_state.scans_by_sheet.get(sh):
        with st.spinner(f"Анализирую колонки листа «{sh}»…"):
            _scan_sheet(sh, st.session_state.sheets_data[sh])

rescan_col1, rescan_col2 = st.columns([5, 1])
with rescan_col1:
    st.caption(
        f"Выбрано листов: **{len(selected_sheets)}**. "
        "Галочки и типы выставлены автоматически — можно скорректировать ниже."
    )
with rescan_col2:
    if st.button(
        "↻ Пересканировать",
        help="Сбросить правки и выставить галочки по автодетекту",
        use_container_width=True,
    ):
        for sh in selected_sheets:
            st.session_state.col_selected_by_sheet[sh] = {}
            st.session_state.col_type_overrides_by_sheet[sh] = {}
            _scan_sheet(sh, st.session_state.sheets_data[sh])
        st.rerun()


# ---------------------------------------------------------------------------
# Шаг 3. Настройка по листам
# ---------------------------------------------------------------------------
_step_header(3, "Настройка по листам", "Проверьте колонки и типы алгоритмов")

type_options_with_auto = ["(авто)"] + list(REGISTRY.keys())
sheet_tabs = st.tabs([f"📋 {sh}" for sh in selected_sheets])

for tab, sh in zip(sheet_tabs, selected_sheets):
    with tab:
        df_sh = st.session_state.sheets_data[sh]
        scans = st.session_state.scans_by_sheet.get(sh, [])
        recommended_cnt = sum(1 for s in scans if s.recommended)
        st.caption(
            f"Колонок: **{len(scans)}** · рекомендовано: **{recommended_cnt}** · "
            f"строк: **{len(df_sh):,}**".replace(",", " ")
        )

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
                "Непустых": s.non_empty,
            })

        if not scan_rows:
            st.warning("⚠️ В листе не обнаружено колонок.")
            continue

        scan_df = pd.DataFrame(scan_rows)
        edited_scan = st.data_editor(
            scan_df,
            use_container_width=True,
            hide_index=True,
            disabled=["Колонка", "Распознанный тип", "Уверенность", "Оценка", "Непустых"],
            column_config={
                "Включить": st.column_config.CheckboxColumn("Включить", width="small"),
                "Колонка": st.column_config.TextColumn("Колонка", width="medium"),
                "Распознанный тип": st.column_config.TextColumn("Тип", width="medium"),
                "Уверенность": st.column_config.TextColumn("Уверенность", width="small"),
                "Оценка": st.column_config.TextColumn("Оценка", width="small"),
                "Непустых": st.column_config.NumberColumn("Непустых", width="small"),
            },
            key=f"scan_editor::{sh}",
        )
        for _, row in edited_scan.iterrows():
            st.session_state.col_selected_by_sheet[sh][str(row["Колонка"])] = bool(row["Включить"])

        cols_sh = _selected_columns(sh)
        if not cols_sh:
            _empty_state(
                "☑️", "Нет выбранных колонок",
                "Отметьте хотя бы одну колонку в таблице выше.",
            )
            continue

        with st.expander(f"Превью данных ({len(cols_sh)} колонок, первые 10 строк)", expanded=False):
            st.dataframe(df_sh[cols_sh].head(10), use_container_width=True, hide_index=True)

        st.markdown("**Тип алгоритма для каждой колонки** — при необходимости переопределите автодетект.")
        for col in cols_sh:
            scan = _get_scan(sh, col)
            detected = scan.detected_type if scan else None
            score = scan.confidence if scan else 0.0

            with st.container():
                label_left, label_mid, label_right = st.columns([2, 2, 3])
                with label_left:
                    st.markdown(f"**`{col}`**")
                with label_mid:
                    if detected:
                        icon = "✅" if score >= 0.75 else ("🟡" if score >= 0.5 else "❓")
                        st.markdown(
                            f"{icon} **{LABELS[detected]}** "
                            f"<span style='color:#8C8C8C;font-size:0.85em'>({score:.0%})</span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown("❓ Тип не распознан")
                with label_right:
                    current_override = st.session_state.col_type_overrides_by_sheet[sh].get(col)
                    default_index = 0
                    if current_override:
                        default_index = 1 + list(REGISTRY.keys()).index(current_override)

                    def _fmt(opt: str, _detected=detected) -> str:
                        if opt == "(авто)":
                            return f"(авто: {LABELS[_detected]})" if _detected else "(не определено)"
                        return LABELS[opt]

                    choice = st.selectbox(
                        "Тип алгоритма",
                        options=type_options_with_auto,
                        index=default_index,
                        format_func=_fmt,
                        key=f"type_override::{sh}::{col}",
                        label_visibility="collapsed",
                    )
                    st.session_state.col_type_overrides_by_sheet[sh][col] = (
                        None if choice == "(авто)" else choice
                    )


# Сводка
per_sheet_cols: dict[str, list[str]] = {sh: _selected_columns(sh) for sh in selected_sheets}
total_cols = sum(len(v) for v in per_sheet_cols.values())
missing: list[tuple[str, str]] = [
    (sh, c)
    for sh, cols_sh in per_sheet_cols.items()
    for c in cols_sh
    if not _effective_type(sh, c)
]

if total_cols == 0:
    _empty_state("☑️", "Нет выбранных колонок", "Выберите хотя бы одну колонку на любом листе.")
    st.stop()

if missing:
    st.warning(
        "⚠️ Не определён тип для: "
        + ", ".join(f"`{sh} → {c}`" for sh, c in missing)
        + ". Переопределите тип вручную."
    )


# ---------------------------------------------------------------------------
# Шаг 4. Запуск алгоритмов
# ---------------------------------------------------------------------------
_step_header(4, "Запуск алгоритмов", f"{total_cols} колонок · {len(selected_sheets)} листов")

run_disabled = bool(missing)
run_clicked = st.button(
    f"▶ Запустить нормализацию",
    type="primary",
    disabled=run_disabled,
    use_container_width=True,
    help=f"Будет обработано {total_cols} колонок на {len(selected_sheets)} листах",
)

if run_clicked:
    for sh in selected_sheets:
        st.session_state.results_by_sheet[sh] = {}
        st.session_state.selections_by_sheet[sh] = {}
        st.session_state.canonicals_by_sheet[sh] = {}
    st.session_state.normalized_by_sheet = {}
    st.session_state.mapping_payload = None
    st.session_state.applied = False

    total_tasks = total_cols
    done = 0
    progress = st.progress(0.0, text="Запуск…")
    for sh in selected_sheets:
        df_sh = st.session_state.sheets_data[sh]
        for col in per_sheet_cols[sh]:
            data_type = _effective_type(sh, col)
            progress.progress(
                done / max(total_tasks, 1),
                text=f"[{done + 1}/{total_tasks}] «{sh}» · «{col}» · {LABELS[data_type]}…",
            )
            cands = _run_for_column(df_sh, col, data_type)
            st.session_state.results_by_sheet[sh][col] = cands
            st.session_state.selections_by_sheet[sh][col] = {
                j: (len(c.variants) > 1) for j, c in enumerate(cands)
            }
            st.session_state.canonicals_by_sheet[sh][col] = {
                j: c.canonical for j, c in enumerate(cands)
            }
            done += 1
    progress.empty()
    multi_cnt = sum(
        sum(1 for c in cands if len(c.variants) > 1)
        for sh_res in st.session_state.results_by_sheet.values()
        for cands in sh_res.values()
    )
    st.success(
        f"✅ Обработано **{done}** колонок на **{len(selected_sheets)}** листах. "
        f"Групп с вариантами: **{multi_cnt}**."
    )


# ---------------------------------------------------------------------------
# Шаг 5. Кандидаты
# ---------------------------------------------------------------------------
has_any_results = any(st.session_state.results_by_sheet.get(sh) for sh in selected_sheets)

if has_any_results:
    _step_header(5, "Кандидаты на объединение", "Отметьте группы для нормализации")

    sheets_with_res = [sh for sh in selected_sheets if st.session_state.results_by_sheet.get(sh)]
    res_sheet_tabs = st.tabs([f"📋 {sh}" for sh in sheets_with_res])

    for res_tab, sh in zip(res_sheet_tabs, sheets_with_res):
        with res_tab:
            results = st.session_state.results_by_sheet.get(sh, {})
            processed_cols = [c for c in per_sheet_cols.get(sh, []) if c in results]
            if not processed_cols:
                _empty_state("📋", "Нет обработанных колонок", "Для этого листа нет результатов.")
                continue

            col_tab_labels = [
                f"{c} · {LABELS[_effective_type(sh, c)]}" for c in processed_cols
            ]
            col_tabs = st.tabs(col_tab_labels)

            for col_tab, col in zip(col_tabs, processed_cols):
                with col_tab:
                    candidates: list[NormalizationCandidate] = results[col]
                    if not candidates:
                        _empty_state(
                            "🔎",
                            "Кандидатов не найдено",
                            "Колонка пуста или значения некорректны.",
                        )
                        continue

                    multi = sum(1 for c in candidates if len(c.variants) > 1)
                    col_a, col_b, col_c = st.columns([3, 1, 1])
                    with col_a:
                        st.caption(
                            f"Групп: **{len(candidates)}** · с вариантами: **{multi}**"
                        )
                    with col_b:
                        if st.button("✓ Все", key=f"check_all::{sh}::{col}", use_container_width=True):
                            for i in range(len(candidates)):
                                st.session_state.selections_by_sheet[sh][col][i] = True
                            st.rerun()
                    with col_c:
                        if st.button("✗ Сбросить", key=f"uncheck_all::{sh}::{col}", use_container_width=True):
                            for i in range(len(candidates)):
                                st.session_state.selections_by_sheet[sh][col][i] = False
                            st.rerun()

                    filter_mode = st.radio(
                        "Показывать:",
                        options=["Только группы с вариантами", "Все группы"],
                        horizontal=True,
                        index=0,
                        key=f"filter::{sh}::{col}",
                    )

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
                        _empty_state(
                            "🔎",
                            "Нет групп в этом фильтре",
                            "Переключитесь на «Все группы».",
                        )
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
# Шаг 6. Применение и экспорт
# ---------------------------------------------------------------------------
if has_any_results:
    _step_header(6, "Применение и экспорт")

    apply_clicked = st.button(
        "🛠 Выполнить нормализацию по всем выбранным листам",
        type="primary",
        use_container_width=True,
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

                col_series = normalized_df[col]
                str_series = col_series.astype(str)
                if mapping:
                    replaced = str_series.map(mapping)
                    new_series = replaced.where(replaced.notna(), col_series)
                else:
                    new_series = col_series
                changed = int((str_series != new_series.astype(str)).sum())
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
            f"✅ Нормализация завершена — заменено **{payload['meta']['total_values_changed']}** значений "
            f"по **{total_cols_applied}** колонкам на **{len(payload['sheets'])}** листах."
        )

        # Сравнение до/после
        with st.expander("Сравнение «до / после» (первые 15 строк)", expanded=True):
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
                    ordered_cols = [col for c in cols_list for col in (f"{c} (до)", f"{c} (после)")]
                    combined = pd.concat([before, after], axis=1)[ordered_cols]
                    st.dataframe(combined, use_container_width=True, hide_index=True)

        # Скачивание
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
