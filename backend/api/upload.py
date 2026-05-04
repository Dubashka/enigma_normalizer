"""POST /api/upload — upload Excel file and create session."""
from __future__ import annotations

from fastapi import APIRouter, File, UploadFile, HTTPException

from ..session_store import create_session, get_session
from ..services.excel_service import read_excel, df_to_records

router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if file.content_type not in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/octet-stream",
    ) and not (file.filename or "").lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx / .xls files are supported")

    data = await file.read()
    try:
        sheets_df = read_excel(data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Cannot read Excel file: {e}")

    sid = create_session()
    sess = get_session(sid)
    sess["filename"] = file.filename
    sess["sheets_df"] = sheets_df

    sheet_meta = {
        name: {"rows": len(df), "columns": list(df.columns)}
        for name, df in sheets_df.items()
    }

    return {
        "session_id": sid,
        "filename": file.filename,
        "sheets": list(sheets_df.keys()),
        "sheet_meta": sheet_meta,
    }
