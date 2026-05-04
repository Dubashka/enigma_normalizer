"""Download routes:
  GET /api/download/excel/{token}
  GET /api/download/mapping/{token}
  GET /api/download/doc/{token}
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..session_store import _STORE
from ..services.excel_service import build_normalized_excel

router = APIRouter()


def _find_session_by_token(token: str) -> tuple[str, dict] | None:
    for sid, sess in _STORE.items():
        if token in sess.get("download_tokens", {}):
            return sid, sess
    return None


@router.get("/excel/{token}")
def download_excel(token: str):
    found = _find_session_by_token(token)
    if not found:
        raise HTTPException(status_code=404, detail="Token not found or expired")
    sid, sess = found
    token_type = sess["download_tokens"][token]
    if token_type != "excel":
        raise HTTPException(status_code=400, detail="Token type mismatch")

    sheets_df = sess.get("sheets_df", {})
    normalized = sess.get("normalized", {})
    if not sheets_df:
        raise HTTPException(status_code=400, detail="No data available")

    xlsx_bytes = build_normalized_excel(sheets_df, normalized)
    filename = Path(sess.get("filename") or "normalized").stem
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}__normalized.xlsx"'},
    )


@router.get("/mapping/{token}")
def download_mapping(token: str):
    found = _find_session_by_token(token)
    if not found:
        raise HTTPException(status_code=404, detail="Token not found or expired")
    sid, sess = found
    token_type = sess["download_tokens"][token]

    if token_type == "mapping":
        payload = sess.get("mapping_payload")
        filename = Path(sess.get("filename") or "mapping").stem
        out_filename = f"{filename}__mapping.json"
    elif token_type == "doc_mapping":
        payload = sess.get("doc_mapping")
        filename = Path(sess.get("doc_filename") or "mapping").stem
        out_filename = f"{filename}__mapping.json"
    else:
        raise HTTPException(status_code=400, detail="Token type mismatch")

    if payload is None:
        raise HTTPException(status_code=400, detail="No mapping available")

    json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{out_filename}"'},
    )


@router.get("/doc/{token}")
def download_doc(token: str):
    found = _find_session_by_token(token)
    if not found:
        raise HTTPException(status_code=404, detail="Token not found or expired")
    sid, sess = found
    token_type = sess["download_tokens"][token]
    if token_type != "doc_output":
        raise HTTPException(status_code=400, detail="Token type mismatch")

    out_bytes = sess.get("doc_output")
    out_ext = sess.get("doc_ext", "txt")
    if out_bytes is None:
        raise HTTPException(status_code=400, detail="No document output available")

    filename = Path(sess.get("doc_filename") or "document").stem
    mime_by_ext = {
        "txt": "text/plain",
        "md": "text/markdown",
        "csv": "text/csv",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    mime = mime_by_ext.get(out_ext, "application/octet-stream")
    return Response(
        content=out_bytes,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}__normalized.{out_ext}"'},
    )
