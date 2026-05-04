"""Normalize routes:
  POST /api/normalize/scan   — scan selected sheets for column types
  POST /api/normalize/run    — run normalizers on selected columns
  POST /api/normalize/apply  — apply selected candidates, build Excel
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..session_store import get_session
from ..services.normalize_service import (
    scan_sheet,
    run_column,
    candidate_to_dict,
    column_scan_to_dict,
    get_registry_labels,
    get_registry_keys,
)
from ..services.excel_service import apply_normalization, build_normalized_excel

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    session_id: str
    sheets: list[str]


class RunRequest(BaseModel):
    session_id: str
    # {sheet: {col: type_key}}
    columns: dict[str, dict[str, str]]


class ApplyRequest(BaseModel):
    session_id: str
    # {sheet: {col: {idx: bool}}}
    selections: dict[str, dict[str, dict[str, bool]]]
    # {sheet: {col: {idx: str}}}
    canonicals: dict[str, dict[str, dict[str, str]]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sess(sid: str) -> dict:
    try:
        return get_session(sid)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/labels")
def get_labels():
    return {"labels": get_registry_labels(), "types": get_registry_keys()}


@router.post("/scan")
def scan(req: ScanRequest):
    sess = _sess(req.session_id)
    sheets_df = sess.get("sheets_df", {})
    result: dict[str, list] = {}

    for sheet in req.sheets:
        if sheet not in sheets_df:
            raise HTTPException(status_code=400, detail=f"Sheet not found: {sheet}")
        df = sheets_df[sheet]
        scans = scan_sheet(df)
        sess["scans"][sheet] = scans
        result[sheet] = [column_scan_to_dict(s) for s in scans]

    return {"scans": result}


@router.post("/run")
def run(req: RunRequest):
    sess = _sess(req.session_id)
    sheets_df = sess.get("sheets_df", {})

    results_out: dict[str, dict[str, list]] = {}

    for sheet, col_types in req.columns.items():
        if sheet not in sheets_df:
            raise HTTPException(status_code=400, detail=f"Sheet not found: {sheet}")
        df = sheets_df[sheet]
        sess["results"][sheet] = {}
        results_out[sheet] = {}

        for col, data_type in col_types.items():
            if col not in df.columns:
                raise HTTPException(status_code=400, detail=f"Column not found: {sheet}/{col}")
            candidates = run_column(df, col, data_type)
            sess["results"][sheet][col] = candidates
            results_out[sheet][col] = [candidate_to_dict(i, c) for i, c in enumerate(candidates)]

    return {"results": results_out}


@router.post("/apply")
def apply(req: ApplyRequest):
    sess = _sess(req.session_id)
    sheets_df = sess.get("sheets_df", {})
    all_results = sess.get("results", {})

    sheets_payload: dict[str, Any] = {}
    grand_total_changed = 0
    labels = get_registry_labels()

    for sheet, col_selections in req.selections.items():
        if sheet not in sheets_df:
            raise HTTPException(status_code=400, detail=f"Sheet not found: {sheet}")
        if sheet not in all_results:
            continue

        df = sheets_df[sheet]
        results = all_results[sheet]  # col -> list[NormalizationCandidate]
        col_canonicals = req.canonicals.get(sheet, {})

        # Convert string keys back to int
        int_selections: dict[str, dict[int, bool]] = {
            col: {int(k): v for k, v in sels.items()}
            for col, sels in col_selections.items()
        }
        int_canonicals: dict[str, dict[int, str]] = {
            col: {int(k): v for k, v in cans.items()}
            for col, cans in col_canonicals.items()
        }

        normalized_df, per_col, changed = apply_normalization(
            df, results, int_selections, int_canonicals
        )
        sess["normalized"][sheet] = normalized_df
        grand_total_changed += changed
        sheets_payload[sheet] = {
            "columns": list(results.keys()),
            "values_changed": changed,
            "per_column": per_col,
        }

    mapping_payload = {
        "meta": {
            "source_file": sess.get("filename"),
            "sheets": list(sheets_payload.keys()),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "total_values_changed": grand_total_changed,
        },
        "sheets": sheets_payload,
    }
    sess["mapping_payload"] = mapping_payload

    # Build download tokens
    import uuid as _uuid
    excel_token = str(_uuid.uuid4())
    mapping_token = str(_uuid.uuid4())
    sess["download_tokens"][excel_token] = "excel"
    sess["download_tokens"][mapping_token] = "mapping"

    return {
        "total_values_changed": grand_total_changed,
        "sheets": {s: {"values_changed": p["values_changed"]} for s, p in sheets_payload.items()},
        "excel_token": excel_token,
        "mapping_token": mapping_token,
        "mapping_payload": mapping_payload,
    }
