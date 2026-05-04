"""Text document normalization service."""
from __future__ import annotations

import sys
import os
import json
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from normalizers import LABELS, get_normalizer
from normalizers.base import NormalizationCandidate
from utils.text_extract import extract_document, rebuild_document, ExtractedDocument, SUPPORTED_EXTENSIONS
from utils.text_scan import scan_text_document, group_by_type, apply_replacements, TextMatch


def load_document(filename: str, data: bytes) -> ExtractedDocument:
    return extract_document(filename, data)


def scan_document(doc: ExtractedDocument) -> tuple[list[TextMatch], dict[str, list[NormalizationCandidate]]]:
    """Scan document for PII and build normalization candidates per type."""
    matches = scan_text_document(doc)
    groups = group_by_type(matches)

    results: dict[str, list[NormalizationCandidate]] = {}
    for dtype, values in groups.items():
        normalizer = get_normalizer(dtype)
        results[dtype] = normalizer.build_candidates(values)

    return matches, results


def apply_doc_normalization(
    doc: ExtractedDocument,
    matches: list[TextMatch],
    results: dict[str, list[NormalizationCandidate]],
    selections: dict[str, dict[int, bool]],
    canonicals: dict[str, dict[int, str]],
    source_filename: str,
) -> tuple[bytes, str, dict]:
    """Apply selected candidates and rebuild the document.

    Returns:
        (output_bytes, output_ext, mapping_payload)
    """
    mapping: dict[str, dict[str, str]] = {}
    groups_payload: dict[str, list] = {}

    for dtype, candidates in results.items():
        sel = selections.get(dtype, {})
        cans = canonicals.get(dtype, {})
        m: dict[str, str] = {}
        applied = []
        for i, c in enumerate(candidates):
            if not sel.get(i, False):
                continue
            canonical = (cans.get(i, c.canonical) or "").strip()
            if not canonical:
                continue
            for v in c.variants:
                m[v] = canonical
            applied.append({
                "canonical": canonical,
                "variants": c.variants,
                "count": c.count,
                "confidence": round(c.confidence, 3),
                "meta": c.meta,
            })
        mapping[dtype] = m
        groups_payload[dtype] = applied

    replaced, changed = apply_replacements(doc, matches, mapping)
    out_bytes, out_ext = rebuild_document(doc, replaced)

    payload = {
        "meta": {
            "source_file": source_filename,
            "fmt": doc.fmt,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "total_matches": len(matches),
            "total_values_changed": changed,
        },
        "mapping": {dt: m for dt, m in mapping.items() if m},
        "groups": {dt: g for dt, g in groups_payload.items() if g},
    }

    return out_bytes, out_ext, payload


def match_to_dict(m: TextMatch) -> dict:
    return {
        "data_type": m.data_type,
        "value": m.value,
        "chunk_idx": m.chunk_idx,
        "start": m.start,
        "end": m.end,
    }


def candidate_to_dict(i: int, c: NormalizationCandidate) -> dict:
    return {
        "id": i,
        "canonical": c.canonical,
        "variants": c.variants,
        "count": c.count,
        "confidence": round(c.confidence, 3),
        "meta": c.meta,
    }


SUPPORTED_DOC_EXTENSIONS = list(SUPPORTED_EXTENSIONS)
