"""In-memory session storage.

Each upload creates a session_id (UUID).  All subsequent requests reference
that session_id to retrieve DataFrames, scan results, etc.

Sessions are stored in a plain dict — acceptable for a single-process dev
server.  Replace with Redis/etc. for multi-worker production.
"""
from __future__ import annotations

import uuid
from typing import Any

_STORE: dict[str, dict[str, Any]] = {}


def create_session() -> str:
    """Create a new empty session and return its id."""
    sid = str(uuid.uuid4())
    _STORE[sid] = {}
    return sid


def get_session(session_id: str) -> dict[str, Any]:
    """Return the session dict.  Raises KeyError if unknown."""
    if session_id not in _STORE:
        raise KeyError(f"Session '{session_id}' not found.")
    return _STORE[session_id]


def set_key(session_id: str, key: str, value: Any) -> None:
    get_session(session_id)[key] = value


def get_key(session_id: str, key: str, default: Any = None) -> Any:
    return get_session(session_id).get(key, default)


def delete_session(session_id: str) -> None:
    _STORE.pop(session_id, None)
