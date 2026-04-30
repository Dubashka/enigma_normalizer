"""Excel read / write helpers."""
from __future__ import annotations

import io

import pandas as pd


def read_excel_bytes(raw: bytes) -> dict[str, pd.DataFrame]:
    """Parse Excel bytes into a {sheet_name: DataFrame} dict."""
    for engine in ("calamine", "openpyxl"):
        try:
            xls = pd.ExcelFile(io.BytesIO(raw), engine=engine)
            return {
                name: pd.read_excel(xls, sheet_name=name, dtype=object)
                for name in xls.sheet_names
            }
        except Exception:
            continue
    # final fallback
    xls = pd.ExcelFile(io.BytesIO(raw))
    return {name: pd.read_excel(xls, sheet_name=name, dtype=object) for name in xls.sheet_names}


def write_excel(
    original: dict[str, pd.DataFrame],
    normalized: dict[str, pd.DataFrame],
) -> bytes:
    """Write all sheets to an Excel file in memory.  Normalised sheets replace originals."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        for name, df in original.items():
            out_df = normalized.get(name, df)
            out_df.to_excel(writer, sheet_name=name, index=False)
    return buf.getvalue()
