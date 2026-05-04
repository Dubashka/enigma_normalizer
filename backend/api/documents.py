"""Document normalization routes:
  POST /api/documents/process   — upload document, scan PII, return candidates
  POST /api/documents/apply     — apply selections, return download tokens
"""
from __future__ import annotations

import uuid as _uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..session_store import create_session, get_session
from ..services.document_service import (
    load_document,
    scan_document,
    apply_doc_normalization,
    match_to_dict,
    candidate_to_dict,
    SUPPORTED_DOC_EXTENSIONS,
)

router = APIRouter()


def _sess(sid: str) -> dict:
    try:
        return get_session(sid)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/process")
async def process_document(file: UploadFile = File(...)):
    filename = file.filename or "document.txt"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    if ext not in SUPPORTED_DOC_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format .{ext}. Supported: {', '.join(SUPPORTED_DOC_EXTENSIONS)}",
        )

    data = await file.read()
    try:
        doc = load_document(filename, data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Cannot read document: {e}")

    matches, results = scan_document(doc)

    sid = create_session()
    sess = get_session(sid)
    sess["doc"] = doc
    sess["doc_filename"] = filename
    sess["doc_matches"] = matches
    sess["doc_results"] = results

    # Build type summary
    type_summary: dict[str, dict] = {}
    for dtype, candidates in results.items():
        type_summary[dtype] = {
            "count": sum(c.count for c in candidates),
            "unique": len(set(v for c in candidates for v in c.variants)),
            "candidates": [candidate_to_dict(i, c) for i, c in enumerate(candidates)],
        }

    return {
        "session_id": sid,
        "filename": filename,
        "fmt": doc.fmt,
        "chunks": len(doc.chunks),
        "total_chars": len(doc.full_text),
        "total_matches": len(matches),
        "types": type_summary,
    }


class DocApplyRequest(BaseModel):
    session_id: str
    # {dtype: {idx: bool}}
    selections: dict[str, dict[str, bool]]
    # {dtype: {idx: str}}
    canonicals: dict[str, dict[str, str]]


@router.post("/apply")
def apply_document(req: DocApplyRequest):
    sess = _sess(req.session_id)
    doc = sess.get("doc")
    if doc is None:
        raise HTTPException(status_code=400, detail="No document loaded in this session")

    matches = sess["doc_matches"]
    results = sess["doc_results"]
    filename = sess["doc_filename"] or "document"

    int_selections = {
        dt: {int(k): v for k, v in sels.items()}
        for dt, sels in req.selections.items()
    }
    int_canonicals = {
        dt: {int(k): v for k, v in cans.items()}
        for dt, cans in req.canonicals.items()
    }

    out_bytes, out_ext, mapping_payload = apply_doc_normalization(
        doc, matches, results, int_selections, int_canonicals, filename
    )

    sess["doc_output"] = out_bytes
    sess["doc_ext"] = out_ext
    sess["doc_mapping"] = mapping_payload

    doc_token = str(_uuid.uuid4())
    map_token = str(_uuid.uuid4())
    sess["download_tokens"][doc_token] = "doc_output"
    sess["download_tokens"][map_token] = "doc_mapping"

    return {
        "total_matches": mapping_payload["meta"]["total_matches"],
        "total_values_changed": mapping_payload["meta"]["total_values_changed"],
        "output_ext": out_ext,
        "doc_token": doc_token,
        "mapping_token": map_token,
        "mapping_payload": mapping_payload,
    }
