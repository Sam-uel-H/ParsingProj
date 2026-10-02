"""Slow deterministic adapter used only by subprocess recovery acceptance tests."""

import asyncio

from app.jobs import runner
from app.jobs.celery_app import celery_app
from app.providers.fakes import FakeLLMProvider


class SlowProvider(FakeLLMProvider):
    async def extract(self, request):
        await asyncio.sleep(0.3)
        return await super().extract(request)


runner.get_llm_provider = SlowProvider

__all__ = ["celery_app"]
