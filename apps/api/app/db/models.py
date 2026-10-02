"""Import every ORM model so Alembic sees the complete modular-monolith metadata."""

from app.auth.models import User
from app.documents.models import Document, DocumentExtraction, DocumentPage, DocumentTextBlock
from app.domains.models import Domain
from app.jobs.models import BackgroundTask
from app.parsing.models import LLMInvocation, ParsingJob, ParsingResult
from app.templates.models import Template, TemplateColumn, TemplateVersion
from app.templates.prompt_models import PromptDraft
from app.templates.tagged_models import TaggedExample

__all__ = [
    "BackgroundTask",
    "Document",
    "DocumentExtraction",
    "DocumentPage",
    "DocumentTextBlock",
    "Domain",
    "Template",
    "TemplateColumn",
    "TemplateVersion",
    "TaggedExample",
    "PromptDraft",
    "User",
    "ParsingJob",
    "ParsingResult",
    "LLMInvocation",
]
