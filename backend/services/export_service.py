"""Build normalised DataFrames and mapping payload from confirmed candidate selections."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from normalizers import LABELS


def build_normalized(
    sheets_data: dict[str, pd.DataFrame],
    candidates: dict[str, dict[str, list[dict]]],
    selections: dict,  # {sheet: {col: {str(idx): {apply, canonical}}}}
    column_types: dict[str, dict[str, str]],
    filename: str = "",
) -> tuple[dict[str, pd.DataFrame], dict]:
    """Apply selections to DataFrames and build the JSON mapping payload.

    Returns:
        (normalized_sheets, mapping_payload)
    """
    normalized: dict[str, pd.DataFrame] = {}
    sheets_payload: dict[str, dict] = {}
    grand_total_changed = 0

    for sheet, col_candidates in candidates.items():
        df = sheets_data.get(sheet)
        if df is None:
            continue
        norm_df = df.copy()
        per_col: dict[str, dict] = {}
        sheet_changed = 0

        for col, cands in col_candidates.items():
            col_sels = (selections.get(sheet) or {}).get(col) or {}
            mapping: dict[str, str] = {}
            applied_groups = []

            for idx_str, c in enumerate(cands):
                sel = col_sels.get(str(idx_str)) or {}
                if not sel.get("apply", False):
                    continue
                canonical = (sel.get("canonical") or c["canonical"] or "").strip()
                if not canonical:
                    continue
                for v in c["variants"]:
                    mapping[v] = canonical
                applied_groups.append({"canonical": canonical, "variants": c["variants"],
                                        "count": c["count"], "confidence": c["confidence"]})

            col_series = norm_df[col]
            str_series = col_series.astype(str)
            if mapping:
                replaced = str_series.map(mapping)
                new_series = replaced.where(replaced.notna(), col_series)
            else:
                new_series = col_series
            changed = int((str_series != new_series.astype(str)).sum())
            sheet_changed += changed
            norm_df[col] = new_series

            dtype = (column_types.get(sheet) or {}).get(col, "")
            per_col[col] = {
                "data_type": dtype,
                "data_type_label": LABELS.get(dtype, dtype),
                "total_candidates": len(cands),
                "applied_groups": len(applied_groups),
                "values_changed": changed,
                "mapping": mapping,
                "groups": applied_groups,
            }

        normalized[sheet] = norm_df
        grand_total_changed += sheet_changed
        sheets_payload[sheet] = {
            "columns": list(col_candidates.keys()),
            "values_changed": sheet_changed,
            "per_column": per_col,
        }

    from pathlib import Path
    mapping_payload = {
        "meta": {
            "source_file": filename,
            "sheets": list(sheets_payload.keys()),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "total_values_changed": grand_total_changed,
        },
        "sheets": sheets_payload,
    }
    return normalized, mapping_payload
