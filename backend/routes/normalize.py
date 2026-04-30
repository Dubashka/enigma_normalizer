"""Normalisation routes:
  POST /api/normalize/scan   — scan selected sheets, return column detection
  POST /api/normalize/run    — run normalizers, return candidates
  POST /api/normalize/apply  — apply confirmed selections, return download tokens
  GET  /api/download/excel/{token}
  GET  /api/download/mapping/{token}
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from backend import session as sess
from backend.services import excel_service, export_service, normalize_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    session_id: str
    sheets: list[str]


class RunRequest(BaseModel):
    session_id: str
    # {sheet: {col: type}}
    column_types: dict[str, dict[str, str]]


class CandidateSelection(BaseModel):
    apply: bool
    canonical: str


class ApplyRequest(BaseModel):
    session_id: str
    # {sheet: {col: {str(idx): CandidateSelection}}}
    selections: dict[str, dict[str, dict[str, CandidateSelection]]]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/normalize/scan")
def normalize_scan(req: ScanRequest) -> dict:
    """Scan the selected sheets and return column detection results."""
    try:
        session = sess.get_session(req.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found.")

    sheets_data = session.get("sheets_data", {})
    if not sheets_data:
        raise HTTPException(status_code=400, detail="No file data in session.")

    missing = [s for s in req.sheets if s not in sheets_data]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown sheets: {missing}")

    scans = normalize_service.scan_sheets(
        {s: sheets_data[s] for s in req.sheets}
    )
    sess.set_key(req.session_id, "selected_sheets", req.sheets)
    sess.set_key(req.session_id, "scans", scans)
    return {"scans": scans}


@router.post("/normalize/run")
def normalize_run(req: RunRequest) -> dict:
    """Run normalizers on the selected columns.  Returns candidates per column."""
    try:
        session = sess.get_session(req.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found.")

    sheets_data = session.get("sheets_data", {})
    candidates = normalize_service.run_normalizers(
        sheets_data, req.column_types
    )
    sess.set_key(req.session_id, "candidates", candidates)
    sess.set_key(req.session_id, "column_types", req.column_types)
    return {"candidates": candidates}


@router.post("/normalize/apply")
def normalize_apply(req: ApplyRequest) -> dict:
    """Apply the confirmed selections, produce output files, return tokens."""
    try:
        session = sess.get_session(req.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found.")

    sheets_data = session.get("sheets_data", {})
    candidates = session.get("candidates", {})
    column_types = session.get("column_types", {})
    filename = session.get("filename", "normalized")

    normalized, mapping_payload = export_service.build_normalized(
        sheets_data=sheets_data,
        candidates=candidates,
        selections=req.selections,
        column_types=column_types,
        filename=filename,
    )
    excel_bytes = excel_service.write_excel(
        original=sheets_data,
        normalized=normalized,
    )
    import json
    mapping_bytes = json.dumps(mapping_payload, ensure_ascii=False, indent=2).encode("utf-8")

    token = sess.create_session()  # reuse UUID mechanism as a download token
    sess.set_key(token, "_excel", excel_bytes)
    sess.set_key(token, "_mapping", mapping_bytes)
    sess.set_key(token, "_filename", filename)

    return {
        "token": token,
        "stats": mapping_payload["meta"],
    }


@router.get("/download/excel/{token}")
def download_excel(token: str) -> Response:
    try:
        data = sess.get_key(token, "_excel")
        filename = sess.get_key(token, "_filename", "normalized")
    except KeyError:
        raise HTTPException(status_code=404, detail="Token not found.")
    from pathlib import Path
    stem = Path(filename).stem if filename else "normalized"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{stem}__normalized.xlsx"'},
    )


@router.get("/download/mapping/{token}")
def download_mapping(token: str) -> Response:
    try:
        data = sess.get_key(token, "_mapping")
        filename = sess.get_key(token, "_filename", "normalized")
    except KeyError:
        raise HTTPException(status_code=404, detail="Token not found.")
    from pathlib import Path
    stem = Path(filename).stem if filename else "normalized"
    return Response(
        content=data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{stem}__mapping.json"'},
    )
