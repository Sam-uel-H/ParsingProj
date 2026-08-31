from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.db.session import database_is_ready

logger = logging.getLogger(__name__)
router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    service: str
    version: str
    checks: dict[str, str] = Field(default_factory=dict)


@router.get("/health", response_model=HealthResponse, summary="Application liveness")
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.project_name,
        version=settings.app_version,
    )


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
    summary="Application readiness",
)
def ready() -> HealthResponse | JSONResponse:
    settings = get_settings()
    try:
        database_is_ready()
    except Exception as exc:  # The health response must not expose credentials or query details.
        logger.warning("Database readiness check failed", extra={"error_type": type(exc).__name__})
        response = HealthResponse(
            status="unavailable",
            service=settings.project_name,
            version=settings.app_version,
            checks={"database": "unavailable"},
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response.model_dump(),
        )

    return HealthResponse(
        status="ok",
        service=settings.project_name,
        version=settings.app_version,
        checks={"database": "ok"},
    )
