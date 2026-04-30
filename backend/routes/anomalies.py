"""POST /api/anomalies/run — scan Excel sheets for anomalies."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import session as sess
from backend.services.anomalies_service import run_anomalies

router = APIRouter()


class AnomalyRequest(BaseModel):
    session_id: str
    sheets: list[str]
    use_sample: bool = False
    sample_size: int = 50_000


@router.post("/anomalies/run")
def anomalies_run(req: AnomalyRequest) -> dict:
    try:
        session = sess.get_session(req.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found.")

    sheets_data = session.get("sheets_data", {})
    missing = [s for s in req.sheets if s not in sheets_data]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown sheets: {missing}")

    results = run_anomalies(
        {s: sheets_data[s] for s in req.sheets},
        sample_size=req.sample_size if req.use_sample else None,
    )
    return {"results": results}
