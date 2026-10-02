import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_development_user
from app.auth.models import User
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.jobs.dispatch import Dispatcher, get_dispatcher
from app.parsing.schemas import (
    ParsingJobCreate,
    ParsingJobRead,
    ParsingResultCorrection,
    ParsingResultRead,
)
from app.parsing.service import (
    correct_result,
    export_job_csv,
    export_job_json,
    get_job,
    get_job_results,
    list_jobs,
    queue_job,
)

router = APIRouter(prefix="/parsing-jobs", tags=["parsing-jobs"])


@router.post("", response_model=ParsingJobRead, summary="Queue a parsing job")
async def create_job(
    data: ParsingJobCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
    dispatch: Dispatcher = Depends(get_dispatcher),
    settings: Settings = Depends(get_settings),
) -> ParsingJobRead:
    job, task = queue_job(db, data, actor, settings)
    await dispatch(task.id)
    db.expire_all()
    return get_job(db, job.id)


@router.get("", response_model=list[ParsingJobRead], summary="List recent parsing jobs")
def read_jobs(
    document_id: uuid.UUID | None = None, db: Session = Depends(get_db)
) -> list[ParsingJobRead]:
    return list_jobs(db, document_id)


@router.get("/{job_id}", response_model=ParsingJobRead, summary="Get parsing job")
def read_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> ParsingJobRead:
    return get_job(db, job_id)


@router.get(
    "/{job_id}/results",
    response_model=list[ParsingResultRead],
    summary="List parsing results for review",
)
def list_job_results(job_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ParsingResultRead]:
    return get_job_results(db, job_id)


@router.patch(
    "/{job_id}/results/{result_id}",
    response_model=ParsingResultRead,
    summary="Correct and verify a parsing result",
)
def update_result(
    job_id: uuid.UUID,
    result_id: uuid.UUID,
    data: ParsingResultCorrection,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> ParsingResultRead:
    return correct_result(db, job_id, result_id, data.value, actor)


@router.get("/{job_id}/export.csv", summary="Export reviewed parsing results as CSV")
def export_csv(job_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    return Response(
        export_job_csv(db, job_id),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="parsing-job-{job_id}.csv"'},
    )


@router.get("/{job_id}/export.json", summary="Export reviewed parsing results as JSON")
def export_json(job_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, object]:
    return export_job_json(db, job_id)
