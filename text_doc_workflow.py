"""Streamlit-воркфлоу нормализации текстовых документов.

Этапы (по аналогии с excel-режимом):
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
# Состояние
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "td_uploaded_name": None,
        "td_doc": None,                  # ExtractedDocument
        "td_matches": [],                # list[TextMatch]
        "td_results": {},                # {data_type: list[NormalizationCandidate]}
        "td_selections": {},             # {data_type: {idx: bool}}
        "td_canonicals": {},             # {data_type: {idx: str}}
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

    st.title("📄 Нормализация текстовых документов")
    st.caption(
        "Загрузите документ (txt, docx, md, rtf). Система найдёт в тексте ФИО, "
        "адреса, ИНН, телефоны, email и названия организаций, предложит "
        "канонические значения и соберёт документ обратно в исходном формате."
    )

    # -------------------- Шаг 1. Загрузка --------------------
    st.header("1. Загрузка документа")
    uploaded = st.file_uploader(
        "Выберите файл",
        type=list(SUPPORTED_EXTENSIONS),
        accept_multiple_files=False,
        key="td_uploader",
    )
    if uploaded is None:
        st.info("Загрузите документ, чтобы продолжить.")
        return

    if st.session_state.td_uploaded_name != uploaded.name:
        _reset_after_upload(uploaded.name)
        try:
            st.session_state.td_doc = extract_document(
                uploaded.name, uploaded.getvalue()
            )
        except Exception as e:  # noqa: BLE001
            st.error(f"Не удалось прочитать документ: {e}")
            return

    doc = st.session_state.td_doc
    if doc is None:
        return

    st.success(
        f"Документ загружен: **{uploaded.name}** · формат: **{doc.fmt}** · "
        f"фрагментов: **{len(doc.chunks)}** · символов: **{len(doc.full_text):,}**"
        .replace(",", " ")
    )

    with st.expander("Превью первых 30 фрагментов"):
        preview_rows = [
            {"#": c.idx, "Тип": c.kind, "Текст": (c.text[:200] + "…") if len(c.text) > 200 else c.text}
            for c in doc.chunks[:30]
        ]
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

    # -------------------- Шаг 2. Поиск PII --------------------
    st.header("2. Поиск данных в тексте")

    if st.button("🔎 Найти данные", type="primary", key="td_scan"):
        with st.spinner("Ищу ФИО, адреса, ИНН, телефоны, email, организации…"):
            matches = scan_text_document(doc)
        st.session_state.td_matches = matches
        st.session_state.td_results = {}
        st.session_state.td_selections = {}
        st.session_state.td_canonicals = {}
        st.session_state.td_applied = False

        groups = group_by_type(matches)
        progress = st.progress(0.0)
        types = list(groups.keys())
        for i, dtype in enumerate(types, start=1):
            with st.spinner(f"[{i}/{len(types)}] Алгоритм «{LABELS[dtype]}»…"):
                normalizer = get_normalizer(dtype)
                cands = normalizer.build_candidates(groups[dtype])
            st.session_state.td_results[dtype] = cands
            st.session_state.td_selections[dtype] = {
                j: (len(c.variants) > 1) for j, c in enumerate(cands)
            }
            st.session_state.td_canonicals[dtype] = {
                j: c.canonical for j, c in enumerate(cands)
            }
            progress.progress(i / max(len(types), 1))
        progress.empty()

    matches = st.session_state.td_matches
    if not matches:
        st.info("Нажмите «Найти данные», чтобы начать.")
        return

    # Сводка по типам
    groups = group_by_type(matches)
    m_cols = st.columns(len(groups) or 1)
    for col, (dtype, values) in zip(m_cols, groups.items()):
        col.metric(LABELS[dtype], f"{len(values)} (уник: {len(set(values))})")

    # -------------------- Шаг 3. Кандидаты на объединение --------------------
    if not st.session_state.td_results:
        return

    st.header("3. Кандидаты на объединение")
    st.caption(
        "По каждому типу показаны группы похожих значений. Отметьте, какие из "
        "них стоит объединить к одному каноническому виду."
    )

    tabs = st.tabs([f"{LABELS[dt]} · {len(cs)}" for dt, cs in st.session_state.td_results.items()])
    for tab, (dtype, candidates) in zip(tabs, st.session_state.td_results.items()):
        with tab:
            if not candidates:
                st.warning("Алгоритм не нашёл кандидатов.")
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
                key=f"td_filter::{dtype}",
            )
            b1, b2, _ = st.columns([1, 1, 4])
            with b1:
                if st.button("✓ Отметить все", key=f"td_check::{dtype}"):
                    for i in range(len(candidates)):
                        st.session_state.td_selections[dtype][i] = True
                    st.rerun()
            with b2:
                if st.button("✗ Снять все", key=f"td_uncheck::{dtype}"):
                    for i in range(len(candidates)):
                        st.session_state.td_selections[dtype][i] = False
                    st.rerun()

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
                st.info("В этом режиме нет групп для отображения.")
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
    st.header("4. Применение и экспорт")

    if st.button("🛠 Выполнить нормализацию документа", type="primary", key="td_apply"):
        # Собираем mapping из одобренных групп.
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

        # Применяем к документу
        replaced, changed = apply_replacements(doc, st.session_state.td_matches, mapping)
        out_bytes, out_ext = rebuild_document(doc, replaced)

        st.session_state.td_output_bytes = out_bytes
        st.session_state.td_output_ext = out_ext

        # JSON-маппинг
        payload = {
            "meta": {
                "source_file": st.session_state.td_uploaded_name,
                "fmt": doc.fmt,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "total_matches": len(st.session_state.td_matches),
                "total_values_changed": changed,
            },
            "mapping": {
                dtype: m for dtype, m in mapping.items() if m
            },
            "groups": {
                dtype: g for dtype, g in groups_payload.items() if g
            },
        }
        st.session_state.td_mapping_payload = payload
        st.session_state.td_applied = True

    if st.session_state.td_applied and st.session_state.td_output_bytes is not None:
        payload = st.session_state.td_mapping_payload
        st.success(
            f"Готово. Заменено вхождений: **{payload['meta']['total_values_changed']}** "
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
