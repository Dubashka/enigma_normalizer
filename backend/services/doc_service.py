"""Document normalisation service — refactored from text_doc_workflow.py.

All Streamlit calls are removed; this module is pure business logic.
"""
from __future__ import annotations

from datetime import datetime

from normalizers import LABELS, get_normalizer
from utils.text_extract import extract_document, rebuild_document
from utils.text_scan import apply_replacements, group_by_type, scan_text_document


def process_document(filename: str, raw: bytes) -> dict:
    """Extract text, scan for PII, run normalizers.

    Returns:
        {
          doc: ParsedDocument,
          matches: list[TextMatch],
          candidates: {dtype: [candidate_dict, ...]},
        }
    """
    doc = extract_document(filename, raw)
    matches = scan_text_document(doc)
    groups = group_by_type(matches)

    candidates: dict[str, list[dict]] = {}
    for dtype, values in groups.items():
        normalizer = get_normalizer(dtype)
        cands = normalizer.build_candidates(values)
        candidates[dtype] = [
            {
                "canonical": c.canonical,
                "variants": c.variants,
                "count": c.count,
                "confidence": round(c.confidence, 4),
                "meta": c.meta or {},
                "label": LABELS.get(dtype, dtype),
            }
            for c in cands
        ]

    return {"doc": doc, "matches": matches, "candidates": candidates}


def apply_doc_normalisation(
    doc,
    matches: list,
    candidates: dict[str, list[dict]],
    selections: dict[str, dict[str, dict]],
    filename: str = "",
) -> dict:
    """Apply user-confirmed selections, rebuild the document.

    Returns:
        {doc_bytes, ext, mapping, stats}
    """
    mapping: dict[str, dict[str, str]] = {}
    groups_payload: dict[str, list] = {}

    for dtype, cands in candidates.items():
        dtype_sels = selections.get(dtype) or {}
        m: dict[str, str] = {}
        applied: list[dict] = []

        for idx, c in enumerate(cands):
            sel = dtype_sels.get(str(idx)) or {}
            if not sel.get("apply", False):
                continue
            canonical = (sel.get("canonical") or c["canonical"] or "").strip()
            if not canonical:
                continue
            for v in c["variants"]:
                m[v] = canonical
            applied.append({"canonical": canonical, "variants": c["variants"],
                             "count": c["count"], "confidence": c["confidence"]})

        mapping[dtype] = m
        if applied:
            groups_payload[dtype] = applied

    replaced, changed = apply_replacements(doc, matches, mapping)
    doc_bytes, ext = rebuild_document(doc, replaced)

    payload = {
        "meta": {
            "source_file": filename,
            "fmt": doc.fmt,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "total_matches": len(matches),
            "total_values_changed": changed,
        },
        "mapping": {dt: m for dt, m in mapping.items() if m},
        "groups": groups_payload,
    }
    return {
        "doc_bytes": doc_bytes,
        "ext": ext,
        "mapping": payload,
        "stats": payload["meta"],
    }
