"""Import every ORM model so Alembic sees the complete modular-monolith metadata."""

from app.auth.models import User
from app.documents.models import Document, DocumentExtraction, DocumentPage, DocumentTextBlock
from app.domains.models import Domain
from app.parsing.models import LLMInvocation, ParsingJob, ParsingResult
from app.templates.models import Template, TemplateColumn, TemplateVersion

__all__ = [
    "Document",
    "DocumentExtraction",
    "DocumentPage",
    "DocumentTextBlock",
    "Domain",
    "Template",
    "TemplateColumn",
    "TemplateVersion",
    "User",
    "ParsingJob",
    "ParsingResult",
    "LLMInvocation",
]
