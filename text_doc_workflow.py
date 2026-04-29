"""Streamlit-воркфлоу нормализации текстовых документов.

Этапы:
  1. Загрузка документа (txt / docx / md / rtf).
  2. Автоматический поиск PII-сущностей в тексте.
  3. Группировка по типу и запуск соответствующего нормализатора.
  4. Интерактивный чек-лист кандидатов по каждому типу.
  5. Применение нормализации и скачивание:
       * нормализованный документ в исходном формате,
       * JSON-справочник маппингов.
"""
from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from normalizers import LABELS, get_normalizer
from normalizers.base import NormalizationCandidate
from utils.text_extract import (
    SUPPORTED_EXTENSIONS,
    extract_document,
    rebuild_document,
)
from utils.text_scan import (
    TextMatch,
    apply_replacements,
    group_by_type,
    scan_text_document,
)


# ---------------------------------------------------------------------------
# UI-хелперы (аналог из app.py — переиспользуются локально)
# ---------------------------------------------------------------------------

def _step_header(num: int, title: str, hint: str = "") -> None:
    hint_html = f'<span class="step-hint">{hint}</span>' if hint else ""
    st.markdown(
        f"""
        <div class="step-header">
            <span class="step-num">{num}</span>
            <span class="step-title">{title}</span>
            {hint_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _progress_stepper(current_step: int, steps: list[str]) -> None:
    items_html = ""
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
        items_html += f"""
            <div class="step-item {cls}">
                <div class="step-circle">{circle}</div>
                <div class="step-label">{label}</div>
            </div>
        """
    st.markdown(
        f'<div class="step-progress">{items_html}</div>',
        unsafe_allow_html=True,
    )


def _empty_state(icon: str, title: str, desc: str) -> None:
    st.markdown(
        f"""
        <div class="empty-state">
            <div class="es-icon">{icon}</div>
            <div class="es-title">{title}</div>
            <div class="es-desc">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Состояние
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "td_uploaded_name": None,
        "td_doc": None,
        "td_matches": [],
        "td_results": {},
        "td_selections": {},
        "td_canonicals": {},
        "td_applied": False,
        "td_output_bytes": None,
        "td_output_ext": None,
        "td_mapping_payload": None,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def _reset_after_upload(name: str):
    st.session_state.td_uploaded_name = name
    st.session_state.td_doc = None
    st.session_state.td_matches = []
    st.session_state.td_results = {}
    st.session_state.td_selections = {}
    st.session_state.td_canonicals = {}
    st.session_state.td_applied = False
    st.session_state.td_output_bytes = None
    st.session_state.td_output_ext = None
    st.session_state.td_mapping_payload = None


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def run_text_document_mode():
    _init_state()

    # Заголовок
    st.markdown(
        """
        <div class="app-header">
            <span class="logo-mark">📄</span>
            <div>
                <h1>Нормализация документов</h1>
                <p class="subtitle">Поиск и нормализация PII в текстовых файлах</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Определяем текущий шаг для степпера
    td_step = 1
    if st.session_state.get("td_doc") is not None:
        td_step = 2
    if st.session_state.get("td_results"):
        td_step = 3
    if st.session_state.get("td_applied"):
        td_step = 4

    _progress_stepper(td_step, ["Загрузка", "Поиск PII", "Кандидаты", "Экспорт"])

    # -------------------- Шаг 1. Загрузка --------------------
    _step_header(1, "Загрузка документа")
    uploaded = st.file_uploader(
        "Выберите файл",
        type=list(SUPPORTED_EXTENSIONS),
        accept_multiple_files=False,
        key="td_uploader",
        label_visibility="collapsed",
        help=f"Поддерживаемые форматы: {', '.join(SUPPORTED_EXTENSIONS)}",
    )
    if uploaded is None:
        _empty_state(
            "📂",
            "Файл не загружен",
            f"Поддерживаются форматы: {', '.join(SUPPORTED_EXTENSIONS)}",
        )
        return

    if st.session_state.td_uploaded_name != uploaded.name:
        _reset_after_upload(uploaded.name)
        try:
            with st.spinner("Читаю документ…"):
                st.session_state.td_doc = extract_document(
                    uploaded.name, uploaded.getvalue()
                )
        except Exception as e:
            st.error(f"❌ Не удалось прочитать документ: {e}")
            return

    doc = st.session_state.td_doc
    if doc is None:
        return

    st.success(
        f"✅ **{uploaded.name}** · формат: **{doc.fmt}** · "
        f"фрагментов: **{len(doc.chunks)}** · "
        f"символов: **{len(doc.full_text):,}**".replace(",", " ")
    )

    with st.expander("Превью первых 30 фрагментов", expanded=False):
        preview_rows = [
            {
                "#": c.idx,
                "Тип": c.kind,
                "Текст": (c.text[:200] + "…") if len(c.text) > 200 else c.text,
            }
            for c in doc.chunks[:30]
        ]
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

    # -------------------- Шаг 2. Поиск PII --------------------
    _step_header(2, "Поиск данных в тексте", "ФИО · адреса · ИНН · телефоны · email · организации")

    if st.button("🔎 Найти данные", type="primary", key="td_scan", use_container_width=True):
        with st.spinner("Ищу ФИО, адреса, ИНН, телефоны, email, организации…"):
            matches = scan_text_document(doc)
        st.session_state.td_matches = matches
        st.session_state.td_results = {}
        st.session_state.td_selections = {}
        st.session_state.td_canonicals = {}
        st.session_state.td_applied = False

        groups = group_by_type(matches)
        progress = st.progress(0.0, text="Запускаю нормализаторы…")
        types = list(groups.keys())
        for i, dtype in enumerate(types, start=1):
            progress.progress(
                i / max(len(types), 1),
                text=f"[{i}/{len(types)}] {LABELS[dtype]}…",
            )
            normalizer = get_normalizer(dtype)
            cands = normalizer.build_candidates(groups[dtype])
            st.session_state.td_results[dtype] = cands
            st.session_state.td_selections[dtype] = {
                j: (len(c.variants) > 1) for j, c in enumerate(cands)
            }
            st.session_state.td_canonicals[dtype] = {
                j: c.canonical for j, c in enumerate(cands)
            }
        progress.empty()

    matches = st.session_state.td_matches
    if not matches:
        _empty_state(
            "🔎",
            "Данные не найдены",
            "Нажмите «Найти данные», чтобы запустить сканирование.",
        )
        return

    # Метрики по типам
    groups = group_by_type(matches)
    if groups:
        m_cols = st.columns(min(len(groups), 4))
        for col, (dtype, values) in zip(m_cols, groups.items()):
            col.metric(LABELS[dtype], len(values), delta=f"{len(set(values))} уник.", delta_color="off")

    # -------------------- Шаг 3. Кандидаты --------------------
    if not st.session_state.td_results:
        return

    _step_header(3, "Кандидаты на объединение", "Отметьте группы для нормализации")

    tabs = st.tabs([f"{LABELS[dt]} · {len(cs)}" for dt, cs in st.session_state.td_results.items()])
    for tab, (dtype, candidates) in zip(tabs, st.session_state.td_results.items()):
        with tab:
            if not candidates:
                _empty_state("🔎", "Кандидатов не найдено", "Алгоритм не нашёл групп для этого типа.")
                continue

            multi = sum(1 for c in candidates if len(c.variants) > 1)

            col_a, col_b, col_c = st.columns([3, 1, 1])
            with col_a:
                st.caption(f"Групп: **{len(candidates)}** · с вариантами: **{multi}**")
            with col_b:
                if st.button("✓ Все", key=f"td_check::{dtype}", use_container_width=True):
                    for i in range(len(candidates)):
                        st.session_state.td_selections[dtype][i] = True
                    st.rerun()
            with col_c:
                if st.button("✗ Сбросить", key=f"td_uncheck::{dtype}", use_container_width=True):
                    for i in range(len(candidates)):
                        st.session_state.td_selections[dtype][i] = False
                    st.rerun()

            filter_mode = st.radio(
                "Показывать:",
                options=["Только группы с вариантами", "Все группы"],
                horizontal=True,
                index=0,
                key=f"td_filter::{dtype}",
            )

            rows = []
            for i, c in enumerate(candidates):
                if filter_mode == "Только группы с вариантами" and len(c.variants) <= 1:
                    continue
                rows.append({
                    "id": i,
                    "Применить": st.session_state.td_selections[dtype].get(i, False),
                    "Каноническое значение": st.session_state.td_canonicals[dtype].get(i, c.canonical),
                    "Варианты (исходные)": " | ".join(c.variants),
                    "Вариантов": len(c.variants),
                    "Встречается": c.count,
                    "Уверенность": round(c.confidence, 2),
                })

            if not rows:
                _empty_state("🔎", "Нет групп в этом фильтре", "Переключитесь на «Все группы».")
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
                        "Каноническое значение", width="medium"),
                    "Варианты (исходные)": st.column_config.TextColumn(
                        "Варианты (исходные)", width="large"),
                },
                key=f"td_editor::{dtype}",
            )
            for _, row in edited.iterrows():
                idx = int(row["id"])
                st.session_state.td_selections[dtype][idx] = bool(row["Применить"])
                st.session_state.td_canonicals[dtype][idx] = str(row["Каноническое значение"])

    # -------------------- Шаг 4. Применение и экспорт --------------------
    _step_header(4, "Применение и экспорт")

    if st.button(
        "🛠 Выполнить нормализацию документа",
        type="primary",
        key="td_apply",
        use_container_width=True,
    ):
        mapping: dict[str, dict[str, str]] = {}
        groups_payload: dict[str, list] = {}

        for dtype, candidates in st.session_state.td_results.items():
            sel = st.session_state.td_selections.get(dtype, {})
            cans = st.session_state.td_canonicals.get(dtype, {})
            m: dict[str, str] = {}
            applied_groups = []
            for i, c in enumerate(candidates):
                if not sel.get(i, False):
                    continue
                canonical = (cans.get(i, c.canonical) or "").strip()
                if not canonical:
                    continue
                for v in c.variants:
                    m[v] = canonical
                applied_groups.append({
                    "canonical": canonical,
                    "variants": c.variants,
                    "count": c.count,
                    "confidence": round(c.confidence, 3),
                    "meta": c.meta,
                })
            mapping[dtype] = m
            groups_payload[dtype] = applied_groups

        replaced, changed = apply_replacements(doc, st.session_state.td_matches, mapping)
        out_bytes, out_ext = rebuild_document(doc, replaced)

        st.session_state.td_output_bytes = out_bytes
        st.session_state.td_output_ext = out_ext

        payload = {
            "meta": {
                "source_file": st.session_state.td_uploaded_name,
                "fmt": doc.fmt,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "total_matches": len(st.session_state.td_matches),
                "total_values_changed": changed,
            },
            "mapping": {dtype: m for dtype, m in mapping.items() if m},
            "groups": {dtype: g for dtype, g in groups_payload.items() if g},
        }
        st.session_state.td_mapping_payload = payload
        st.session_state.td_applied = True

    if st.session_state.td_applied and st.session_state.td_output_bytes is not None:
        payload = st.session_state.td_mapping_payload
        st.success(
            f"✅ Готово. Заменено: **{payload['meta']['total_values_changed']}** вхождений "
            f"из **{payload['meta']['total_matches']}** найденных."
        )

        base_name = Path(st.session_state.td_uploaded_name).stem
        out_ext = st.session_state.td_output_ext
        mime_by_ext = {
            "txt": "text/plain",
            "md": "text/markdown",
            "csv": "text/csv",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        mime = mime_by_ext.get(out_ext, "application/octet-stream")

        dl_a, dl_b = st.columns(2)
        with dl_a:
            st.download_button(
                f"⬇ Скачать нормализованный документ (.{out_ext})",
                data=st.session_state.td_output_bytes,
                file_name=f"{base_name}__normalized.{out_ext}",
                mime=mime,
                use_container_width=True,
            )
        with dl_b:
            mapping_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button(
                "⬇ Скачать JSON-справочник маппингов",
                data=mapping_bytes,
                file_name=f"{base_name}__mapping.json",
                mime="application/json",
                use_container_width=True,
            )
