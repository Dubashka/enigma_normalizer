"""POST /api/documents/process — normalise a text document.

Flow:
  1. POST /api/documents/process  — upload + scan + return candidates
  2. POST /api/documents/apply    — apply selections, return download token
  GET  /api/download/document/{token}
  GET  /api/download/docmapping/{token}
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from backend import session as sess
from backend.services.doc_service import apply_doc_normalisation, process_document

router = APIRouter()


class DocApplyRequest(BaseModel):
    session_id: str
    # {dtype: {str(idx): {apply: bool, canonical: str}}}
    selections: dict[str, dict[str, dict]]


@router.post("/documents/process")
async def documents_process(file: UploadFile) -> dict:
    raw = await file.read()
    try:
        result = process_document(file.filename or "", raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    sid = sess.create_session()
    sess.set_key(sid, "doc_filename", file.filename)
    sess.set_key(sid, "doc_obj", result["doc"])
    sess.set_key(sid, "doc_matches", result["matches"])
    sess.set_key(sid, "doc_candidates", result["candidates"])
    return {
        "session_id": sid,
        "filename": file.filename,
        "fmt": result["doc"].fmt,
        "chunk_count": len(result["doc"].chunks),
        "char_count": len(result["doc"].full_text),
        "candidates": result["candidates"],
    }


@router.post("/documents/apply")
def documents_apply(req: DocApplyRequest) -> dict:
    try:
        session = sess.get_session(req.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found.")

    doc = session.get("doc_obj")
    matches = session.get("doc_matches", [])
    candidates = session.get("doc_candidates", {})
    filename = session.get("doc_filename", "document")

    out = apply_doc_normalisation(
        doc=doc,
        matches=matches,
        candidates=candidates,
        selections=req.selections,
        filename=filename,
    )

    token = sess.create_session()
    sess.set_key(token, "_doc_bytes", out["doc_bytes"])
    sess.set_key(token, "_doc_ext", out["ext"])
    sess.set_key(token, "_doc_mapping", json.dumps(out["mapping"], ensure_ascii=False, indent=2).encode())
    sess.set_key(token, "_doc_filename", filename)

    return {"token": token, "stats": out["stats"]}


@router.get("/download/document/{token}")
def download_document(token: str) -> Response:
    try:
        data = sess.get_key(token, "_doc_bytes")
        ext = sess.get_key(token, "_doc_ext", "txt")
        filename = sess.get_key(token, "_doc_filename", "document")
    except KeyError:
        raise HTTPException(status_code=404, detail="Token not found.")
    from pathlib import Path
    stem = Path(filename).stem
    mime_map = {
        "txt": "text/plain", "md": "text/markdown",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    mime = mime_map.get(ext, "application/octet-stream")
    return Response(
        content=data, media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{stem}__normalized.{ext}"'},
    )


@router.get("/download/docmapping/{token}")
def download_doc_mapping(token: str) -> Response:
    try:
        data = sess.get_key(token, "_doc_mapping")
        filename = sess.get_key(token, "_doc_filename", "document")
    except KeyError:
        raise HTTPException(status_code=404, detail="Token not found.")
    from pathlib import Path
    stem = Path(filename).stem
    return Response(
        content=data, media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{stem}__mapping.json"'},
    )
