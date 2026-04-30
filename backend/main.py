"""FastAPI entry point for Enigma Normalizer."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import anomalies, documents, normalize, upload

app = FastAPI(
    title="Enigma Normalizer API",
    version="2.0.0",
    description="REST API for Excel normalisation, anomaly detection and document PII normalisation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(normalize.router, prefix="/api", tags=["normalize"])
app.include_router(anomalies.router, prefix="/api", tags=["anomalies"])
app.include_router(documents.router, prefix="/api", tags=["documents"])


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
