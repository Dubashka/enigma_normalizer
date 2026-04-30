"""POST /api/upload — accept an Excel file, return session_id + sheet names."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile

from backend import session as sess
from backend.services.excel_service import read_excel_bytes

router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile) -> dict:
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx / .xls files are supported.")

    raw = await file.read()
    try:
        sheets_data = read_excel_bytes(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {exc}") from exc

    sid = sess.create_session()
    sess.set_key(sid, "filename", file.filename)
    sess.set_key(sid, "sheets_data", sheets_data)

    return {
        "session_id": sid,
        "filename": file.filename,
        "sheets": list(sheets_data.keys()),
    }
