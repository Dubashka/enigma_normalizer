"""Excel reading and normalization service."""
from __future__ import annotations

import io

import pandas as pd


def read_excel(file_bytes: bytes) -> dict[str, pd.DataFrame]:
    """Read all sheets from Excel bytes. Try calamine first (faster), fall back to openpyxl."""
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


def df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to JSON-serializable records (handles NaN/NaT)."""
    return df.where(df.notna(), other=None).to_dict(orient="records")


def build_normalized_excel(
    original_sheets: dict[str, pd.DataFrame],
    normalized_sheets: dict[str, pd.DataFrame],
) -> bytes:
    """Build Excel bytes with normalized data (original sheets not in normalized stay unchanged)."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        for name, df in original_sheets.items():
            out_df = normalized_sheets.get(name, df)
            out_df.to_excel(writer, sheet_name=name, index=False)
    return buf.getvalue()


def apply_normalization(
    df: pd.DataFrame,
    results: dict,  # col -> list[NormalizationCandidate]
    selections: dict,  # col -> {idx: bool}
    canonicals: dict,  # col -> {idx: str}
) -> tuple[pd.DataFrame, dict, int]:
    """Apply normalization candidates to a DataFrame.

    Returns:
        (normalized_df, per_column_payload, total_changed)
    """
    from normalizers import LABELS
    from utils.detect import scan_dataframe

    normalized_df = df.copy()
    per_column_payload: dict = {}
    total_changed = 0

    for col, candidates in results.items():
        col_selections = selections.get(col, {})
        col_canonicals = canonicals.get(col, {})

        mapping: dict[str, str] = {}
        applied_groups = []
        for i, c in enumerate(candidates):
            if not col_selections.get(i, False):
                continue
            canonical = (col_canonicals.get(i, c.canonical) or "").strip()
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
        total_changed += changed
        normalized_df[col] = new_series

        per_column_payload[col] = {
            "total_candidates": len(candidates),
            "applied_groups": len(applied_groups),
            "values_changed": changed,
            "mapping": mapping,
            "groups": applied_groups,
        }

    return normalized_df, per_column_payload, total_changed
