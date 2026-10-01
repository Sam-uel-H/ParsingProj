from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_development_user
from app.auth.models import User
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.parsing.dependencies import get_llm_provider
from app.providers.llm import LLMProvider
from app.templates import prompt_service
from app.templates.prompt_schemas import (
    AcceptPromptRequest,
    EditPromptRequest,
    GeneratePromptRequest,
    PromptDraftRead,
)

router = APIRouter(prefix="/templates/{template_id}/prompt-drafts", tags=["prompt-drafts"])


@router.get("", response_model=list[PromptDraftRead])
def list_prompt_drafts(
    template_id: uuid.UUID,
    column_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[PromptDraftRead]:
    return [
        PromptDraftRead.model_validate(item)
        for item in prompt_service.list_prompt_drafts(db, template_id, column_id, document_id)
    ]


@router.post("", response_model=PromptDraftRead, status_code=status.HTTP_201_CREATED)
async def generate_prompt(
    template_id: uuid.UUID,
    data: GeneratePromptRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
    provider: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
) -> PromptDraftRead:
    return PromptDraftRead.model_validate(
        await prompt_service.generate_prompt(
            db,
            template_id,
            data.template_column_id,
            data.document_id,
            actor,
            provider,
            settings.llm_timeout_seconds,
        )
    )


@router.put("/{draft_id}", response_model=PromptDraftRead)
def edit_prompt(
    template_id: uuid.UUID,
    draft_id: uuid.UUID,
    data: EditPromptRequest,
    db: Session = Depends(get_db),
) -> PromptDraftRead:
    return PromptDraftRead.model_validate(
        prompt_service.edit_prompt(db, template_id, draft_id, data.edited_prompt)
    )


@router.post("/{draft_id}/dry-runs", response_model=PromptDraftRead)
async def dry_run(
    template_id: uuid.UUID,
    draft_id: uuid.UUID,
    db: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
) -> PromptDraftRead:
    return PromptDraftRead.model_validate(
        await prompt_service.dry_run(
            db, template_id, draft_id, provider, settings.llm_timeout_seconds
        )
    )


@router.post("/{draft_id}/accept", response_model=PromptDraftRead)
def accept_prompt(
    template_id: uuid.UUID,
    draft_id: uuid.UUID,
    data: AcceptPromptRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> PromptDraftRead:
    return PromptDraftRead.model_validate(
        prompt_service.accept_prompt(db, template_id, draft_id, data.expected_lock_version, actor)
    )
