"""Normalization orchestration service."""
from __future__ import annotations

import sys
import os

# Ensure project root is importable
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from normalizers import LABELS, REGISTRY, get_normalizer
from normalizers.base import NormalizationCandidate
from utils.detect import scan_dataframe, ColumnScan

import pandas as pd


def scan_sheet(df: pd.DataFrame) -> list[ColumnScan]:
    return scan_dataframe(df)


def run_column(df: pd.DataFrame, col: str, data_type: str) -> list[NormalizationCandidate]:
    normalizer = get_normalizer(data_type)
    values = [str(v) for v in df[col].dropna().tolist()]
    return normalizer.build_candidates(values)


def candidate_to_dict(i: int, c: NormalizationCandidate) -> dict:
    return {
        "id": i,
        "canonical": c.canonical,
        "variants": c.variants,
        "count": c.count,
        "confidence": round(c.confidence, 3),
        "meta": c.meta,
    }


def column_scan_to_dict(s: ColumnScan) -> dict:
    return {
        "column": s.column,
        "detected_type": s.detected_type,
        "confidence": round(s.confidence, 3),
        "scores": {k: round(v, 3) for k, v in s.scores.items()},
        "non_empty": s.non_empty,
        "recommended": s.recommended,
        "label": LABELS.get(s.detected_type, "") if s.detected_type else "",
    }


def get_registry_labels() -> dict[str, str]:
    return dict(LABELS)


def get_registry_keys() -> list[str]:
    return list(REGISTRY.keys())
