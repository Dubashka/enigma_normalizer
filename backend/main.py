"""FastAPI backend for Enigma Normalizer."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import upload, normalize, anomalies, documents, download

app = FastAPI(
    title="Enigma Normalizer API",
    version="2.0.0",
    description="Normalization and anonymization preprocessing API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(normalize.router, prefix="/api/normalize")
app.include_router(anomalies.router, prefix="/api/anomalies")
app.include_router(documents.router, prefix="/api/documents")
app.include_router(download.router, prefix="/api/download")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
