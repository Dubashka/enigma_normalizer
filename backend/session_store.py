"""In-memory session store.

Each upload creates a session_id (UUID). The session holds:
- sheets_data: dict[sheet_name, list[dict]]  (records-orient, for JSON)
- sheets_df:   dict[sheet_name, pd.DataFrame] (for actual processing)
- scans:       dict[sheet_name, list[ColumnScan]]
- results:     dict[sheet_name, dict[col, list[NormalizationCandidate]]]
- normalized:  dict[sheet_name, pd.DataFrame]
- mapping_payload: dict | None
- filename:    str

Document mode:
- doc:         ExtractedDocument | None
- doc_matches: list[TextMatch]
- doc_results: dict[dtype, list[NormalizationCandidate]]
- doc_output:  bytes | None
- doc_ext:     str | None
- doc_mapping: dict | None
"""
from __future__ import annotations

import time
import uuid
from typing import Any

_STORE: dict[str, dict[str, Any]] = {}
_TTL = 3600  # 1 hour


def create_session() -> str:
    sid = str(uuid.uuid4())
    _STORE[sid] = {
        "created_at": time.time(),
        "filename": None,
        "sheets_df": {},
        "scans": {},
        "results": {},
        "normalized": {},
        "mapping_payload": None,
        # document mode
        "doc": None,
        "doc_filename": None,
        "doc_matches": [],
        "doc_results": {},
        "doc_output": None,
        "doc_ext": None,
        "doc_mapping": None,
        # download tokens
        "download_tokens": {},
    }
    _cleanup()
    return sid


def get_session(sid: str) -> dict[str, Any]:
    sess = _STORE.get(sid)
    if sess is None:
        raise KeyError(f"Session not found: {sid}")
    return sess


def _cleanup():
    now = time.time()
    stale = [k for k, v in _STORE.items() if now - v["created_at"] > _TTL]
    for k in stale:
        del _STORE[k]
