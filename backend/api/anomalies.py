"""POST /api/anomalies/run — scan sheets for anomalies."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..session_store import get_session
from ..services.anomaly_service import run_anomaly_scan

router = APIRouter()


class AnomalyRunRequest(BaseModel):
    session_id: str
    sheets: list[str]
    sample_size: int | None = None


def _sess(sid: str) -> dict:
    try:
        return get_session(sid)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/run")
def run_anomalies(req: AnomalyRunRequest):
    sess = _sess(req.session_id)
    sheets_df = sess.get("sheets_df", {})

    results: dict[str, list] = {}
    totals: dict[str, dict] = {}

    for sheet in req.sheets:
        if sheet not in sheets_df:
            raise HTTPException(status_code=400, detail=f"Sheet not found: {sheet}")
        df = sheets_df[sheet]
        groups = run_anomaly_scan(df, sample_size=req.sample_size)
        results[sheet] = groups
        total = sum(g["count"] for g in groups)
        by_sev = {
            sev: sum(g["count"] for g in groups if g["severity"] == sev)
            for sev in ("high", "medium", "low")
        }
        totals[sheet] = {"total": total, "by_severity": by_sev}

    grand_total = sum(t["total"] for t in totals.values())
    grand_by_sev = {
        sev: sum(t["by_severity"][sev] for t in totals.values())
        for sev in ("high", "medium", "low")
    }

    return {
        "results": results,
        "totals": totals,
        "summary": {
            "total": grand_total,
            "by_severity": grand_by_sev,
        },
    }
