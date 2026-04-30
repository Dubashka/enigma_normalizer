"""Anomaly detection — wraps utils/anomalies."""
from __future__ import annotations

import pandas as pd

from utils.anomalies import scan_anomalies


def run_anomalies(
    sheets: dict[str, pd.DataFrame],
    sample_size: int | None = None,
) -> dict[str, list[dict]]:
    """Run anomaly scan on all given sheets.

    Returns:
        {sheet: [{title, description, severity, count, examples}]}
    """
    output: dict[str, list[dict]] = {}
    for sheet, df in sheets.items():
        groups = scan_anomalies(df, sample_size=sample_size)
        output[sheet] = [
            {
                "title": g.title,
                "description": g.description,
                "severity": g.severity,
                "count": g.count,
                "examples": [
                    {
                        "row": e.row,
                        "column": e.column,
                        "value": "" if e.value is None else str(e.value),
                    }
                    for e in g.examples
                ],
            }
            for g in groups
        ]
    return output
