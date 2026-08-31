from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.documents.router import router as documents_router
from app.domains.router import router as domains_router
from app.parsing.router import router as parsing_router
from app.templates.router import router as templates_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(domains_router)
api_router.include_router(documents_router)
api_router.include_router(templates_router)
api_router.include_router(parsing_router)
