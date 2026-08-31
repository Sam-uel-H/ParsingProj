import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_development_user
from app.auth.models import User
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.parsing.dependencies import get_llm_provider
from app.parsing.schemas import ParsingJobCreate, ParsingJobRead
from app.parsing.service import get_job, run_job
from app.providers.llm import LLMProvider

router = APIRouter(prefix="/parsing-jobs", tags=["parsing-jobs"])


@router.post("", response_model=ParsingJobRead, summary="Run a parsing job")
async def create_job(
    data: ParsingJobCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
    provider: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
) -> ParsingJobRead:
    return await run_job(
        db,
        data,
        actor,
        provider,
        settings.validation_retry_limit,
        settings.llm_timeout_seconds,
    )


@router.get("/{job_id}", response_model=ParsingJobRead, summary="Get parsing job")
def read_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> ParsingJobRead:
    return get_job(db, job_id)
