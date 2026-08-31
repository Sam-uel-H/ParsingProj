from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.common.errors import register_exception_handlers
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import close_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    configure_logging()
    yield
    close_database()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.project_name,
        version=settings.app_version,
        description="Document parsing system API through Phase 5.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)
    application.include_router(api_router)
    return application


app = create_app()
