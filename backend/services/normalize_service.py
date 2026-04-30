"""Normalisation business logic — wraps normalizers/ and utils/detect."""
from __future__ import annotations

import pandas as pd

from normalizers import LABELS, REGISTRY, get_normalizer
from normalizers.base import NormalizationCandidate
from utils.detect import scan_dataframe


def _candidate_to_dict(c: NormalizationCandidate) -> dict:
    return {
        "canonical": c.canonical,
        "variants": c.variants,
        "count": c.count,
        "confidence": round(c.confidence, 4),
        "meta": c.meta or {},
    }


def scan_sheets(
    sheets: dict[str, pd.DataFrame],
) -> dict[str, list[dict]]:
    """Run detect.scan_dataframe on each sheet, return serialisable scan results.

    Returns: {sheet: [{column, detected_type, confidence, recommended, non_empty, scores}]}
    """
    result: dict[str, list[dict]] = {}
    for sheet, df in sheets.items():
        scans = scan_dataframe(df)
        result[sheet] = [
            {
                "column": s.column,
                "detected_type": s.detected_type,
                "detected_type_label": LABELS.get(s.detected_type, "") if s.detected_type else "",
                "confidence": round(s.confidence, 4),
                "recommended": s.recommended,
                "non_empty": s.non_empty,
                "scores": {k: round(v, 4) for k, v in (s.scores or {}).items()},
            }
            for s in scans
        ]
    return result


def run_normalizers(
    sheets_data: dict[str, pd.DataFrame],
    column_types: dict[str, dict[str, str]],
) -> dict[str, dict[str, list[dict]]]:
    """Run normalizers on the requested columns.

    Args:
        sheets_data: {sheet: DataFrame}
        column_types: {sheet: {column: type_key}}

    Returns:
        {sheet: {column: [candidate_dict, ...]}}
    """
    results: dict[str, dict[str, list[dict]]] = {}
    for sheet, cols in column_types.items():
        df = sheets_data.get(sheet)
        if df is None:
            continue
        results[sheet] = {}
        for col, dtype in cols.items():
            if col not in df.columns:
                continue
            values = [str(v) for v in df[col].dropna().tolist()]
            normalizer = get_normalizer(dtype)
            candidates = normalizer.build_candidates(values)
            results[sheet][col] = [_candidate_to_dict(c) for c in candidates]
    return results


def get_type_labels() -> dict[str, str]:
    """Return {type_key: label} for all registered normalizers."""
    return {k: LABELS[k] for k in REGISTRY}
