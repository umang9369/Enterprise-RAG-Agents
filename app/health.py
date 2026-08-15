"""Health and readiness checks for the Enterprise RAG API."""

import logfire
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.health.connection_checker import check_all_connections

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Liveness probe — returns 200 if the process is running."""
    return {"status": "ok"}


