"""Anomaly detection service."""
from __future__ import annotations

import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.anomalies import scan_anomalies, AnomalyGroup, AnomalyExample

import pandas as pd


def run_anomaly_scan(df: pd.DataFrame, sample_size: int | None = None) -> list[dict]:
    groups = scan_anomalies(df, sample_size=sample_size)
    return [_group_to_dict(g) for g in groups]


def _group_to_dict(g: AnomalyGroup) -> dict:
    return {
        "key": g.key,
        "title": g.title,
        "severity": g.severity,
        "description": g.description,
        "count": g.count,
        "examples": [_example_to_dict(e) for e in g.examples],
    }


def _example_to_dict(e: AnomalyExample) -> dict:
    return {
        "row": e.row,
        "column": e.column,
        "value": None if e.value is None else str(e.value),
    }
