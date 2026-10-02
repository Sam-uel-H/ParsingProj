from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.jobs.dispatch import get_dispatcher, publish_task, recover_pending
from app.jobs.models import BackgroundTask
from app.jobs.runner import process_task
from app.main import app
from app.parsing.execution import select_context
from app.parsing.models import LLMInvocation, ParsingResult
from app.providers.errors import RateLimitProviderError
from app.providers.fakes import FakeLLMProvider
from app.providers.llm import ExtractionResponse
from app.templates.models import ColumnType, TemplateColumn


async def no_dispatch(task_id):
    pass


def create_case(client: TestClient, count: int = 20):
    domain = client.post("/domains", json={"name": f"Phase11-{uuid.uuid4()}"}).json()
    template = client.post(
        "/templates",
        json={
            "domain_id": domain["id"],
            "name": "Scale template",
            "columns": [
                {
                    "name": f"Field {i:02}",
                    "column_type": "integer",
                    "prompt_text": f"Extract field {i}.",
                    "display_order": i,
                }
                for i in range(count)
            ],
        },
    ).json()
    client.post(
        f"/templates/{template['id']}/publish",
        json={"expected_lock_version": template["current_version"]["lock_version"]},
    ).raise_for_status()
    content = "\n\f\n".join(
        "\n".join(f"Field {i:02}: {i}" for i in range(page, count, 10)) for page in range(10)
    )
    document = client.post(
        "/documents/upload",
        data={"domain_id": domain["id"]},
        files={"files": ("scale.txt", content.encode(), "text/plain")},
    ).json()["results"][0]["document"]
    extraction = client.post(f"/documents/{document['id']}/extract").json()
    assert extraction["status"] == "succeeded"
    app.dependency_overrides[get_dispatcher] = lambda: no_dispatch
    return {"document_id": document["id"], "template_id": template["id"]}, extraction


def make_due(task_id):
    with SessionFactory() as db:
        task = db.get(BackgroundTask, task_id)
        task.available_at = datetime.now(UTC)
        db.commit()


class CountingProvider(FakeLLMProvider):
    def __init__(self, throttle=False):
        self.calls = 0
        self.active = 0
        self.peak = 0
        self.throttle = throttle

    async def extract(self, request):
        self.calls += 1
        if self.throttle:
            self.throttle = False
            raise RateLimitProviderError(retry_after=5)
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.01)
        result = await super().extract(request)
        self.active -= 1
        return ExtractionResponse(tuple(reversed(result.values)), result.metadata, result.usage)


@pytest.mark.parametrize(
    ("count", "strategy", "calls"),
    [(20, "per_column", 20), (50, "per_column", 50), (50, "batch", 10)],
)
def test_scale_concurrency_idempotency_and_context(phase1_client, count, strategy, calls):
    data, extraction = create_case(phase1_client, count)
    key = str(uuid.uuid4())
    data.update(idempotency_key=key, strategy=strategy)
    queued = phase1_client.post("/parsing-jobs", json=data).json()
    assert queued["status"] == "queued"
    assert queued["results"] == []
    assert queued["document_extraction_id"] == extraction["id"]
    assert phase1_client.post("/parsing-jobs", json=data).json()["id"] == queued["id"]
    assert phase1_client.get(f"/parsing-jobs/{queued['id']}/export.csv").status_code == 409
    task_id = uuid.UUID(queued["progress"]["id"])
    provider = CountingProvider()
    settings = get_settings().model_copy(update={"parsing_concurrency": 3})

    async def execute_twice():
        await asyncio.gather(
            process_task(task_id, provider=provider, settings=settings),
            process_task(task_id, provider=provider, settings=settings),
        )

    started = time.monotonic()
    asyncio.run(execute_twice())
    assert time.monotonic() - started < settings.performance_sla_seconds
    asyncio.run(process_task(task_id, provider=provider))
    result = phase1_client.get(f"/parsing-jobs/{queued['id']}").json()
    assert result["status"] == "completed"
    assert len(result["results"]) == count
    assert [r["canonical_value"] for r in result["results"]] == [str(i) for i in range(count)]
    assert result["progress"]["completed_units"] == count
    assert provider.calls == calls
    assert 1 < provider.peak <= 3
    with SessionFactory() as db:
        assert db.scalar(select(func.count()).select_from(ParsingResult)) == count
        assert db.scalar(select(func.count()).select_from(LLMInvocation)) == count


def test_rate_limit_retries_only_unfinished_columns(phase1_client):
    data, _ = create_case(phase1_client, 5)
    job = phase1_client.post("/parsing-jobs", json=data).json()
    task_id = uuid.UUID(job["progress"]["id"])
    provider = CountingProvider(throttle=True)
    asyncio.run(process_task(task_id, provider=provider))
    waiting = phase1_client.get(f"/parsing-jobs/{job['id']}").json()
    assert waiting["status"] == "queued"
    assert waiting["progress"]["error_code"] == "provider_rate_limited"
    assert waiting["progress"]["completed_units"] == 4
    assert datetime.fromisoformat(waiting["progress"]["available_at"]) > datetime.now(UTC)
    asyncio.run(process_task(task_id, provider=provider))
    assert provider.calls == 5
    make_due(task_id)
    asyncio.run(process_task(task_id, provider=provider))
    finished = phase1_client.get(f"/parsing-jobs/{job['id']}").json()
    assert finished["status"] == "completed"
    assert finished["progress"]["attempts"] == 2
    assert len(finished["results"]) == 5
    assert provider.calls == 6


def test_reprocessing_preserves_history_and_queued_job_snapshot(phase1_client):
    data, original = create_case(phase1_client, 3)
    job = phase1_client.post("/parsing-jobs", json=data).json()
    new = phase1_client.post(f"/documents/{data['document_id']}/reprocess").json()
    duplicate = phase1_client.post(f"/documents/{data['document_id']}/reprocess").json()
    assert new["id"] == duplicate["id"]
    assert new["version_number"] == 2
    asyncio.run(process_task(uuid.UUID(new["progress"]["id"])))
    asyncio.run(process_task(uuid.UUID(job["progress"]["id"])))
    finished = phase1_client.get(f"/parsing-jobs/{job['id']}").json()
    assert finished["status"] == "completed"
    assert finished["document_extraction_id"] == original["id"]
    history = phase1_client.get(f"/documents/{data['document_id']}/extractions").json()
    assert [item["version_number"] for item in history] == [2, 1]
    assert all(item["status"] == "succeeded" for item in history)
    old = phase1_client.get(
        f"/documents/{data['document_id']}/extraction", params={"extraction_id": original["id"]}
    ).json()
    assert old["pages"] == original["pages"]
    assert (
        phase1_client.get(
            f"/documents/{data['document_id']}/pages/1/preview",
            params={"extraction_id": original["id"]},
        ).status_code
        == 200
    )


def test_outbox_survives_unavailable_broker_and_can_be_recovered(phase1_client):
    data, _ = create_case(phase1_client, 2)
    job = phase1_client.post("/parsing-jobs", json=data).json()
    task_id = uuid.UUID(job["progress"]["id"])
    with patch("app.jobs.celery_app.celery_app.send_task", side_effect=ConnectionError):
        publish_task(task_id)
    with SessionFactory() as db:
        task = db.get(BackgroundTask, task_id)
        assert task.state == "queued"
        assert task.dispatched_at is None
    with patch("app.jobs.dispatch.publish_task") as publish:
        assert recover_pending() == 1
        publish.assert_called_once_with(task_id)
    asyncio.run(process_task(task_id))
    assert phase1_client.get(f"/parsing-jobs/{job['id']}").json()["status"] == "completed"


def test_multiple_jobs_run_concurrently(phase1_client):
    data, _ = create_case(phase1_client, 5)
    jobs = [phase1_client.post("/parsing-jobs", json=data).json() for _ in range(3)]

    async def execute():
        await asyncio.gather(
            *(
                process_task(uuid.UUID(job["progress"]["id"]), provider=CountingProvider())
                for job in jobs
            )
        )

    asyncio.run(execute())
    assert all(
        phase1_client.get(f"/parsing-jobs/{job['id']}").json()["status"] == "completed"
        for job in jobs
    )


def test_context_selection_preserves_late_matching_field_and_checks_prompt_budget():
    column = TemplateColumn(
        name="Interest Amount",
        column_type=ColumnType.CURRENCY,
        prompt_text="Extract the amount.",
        display_order=0,
    )
    text = "Unrelated text\n" * 10000 + "Interest Amount: 123.45\n"
    selected = select_context(text, [column], 4096)
    assert "Interest Amount: 123.45" in selected
    assert len(selected) < 4096
    column.prompt_text = "x" * 4096
    with pytest.raises(Exception, match="context budget"):
        select_context(text, [column], 4096)


def test_exhausted_provider_retries_fail_visibly_and_stop(phase1_client):
    class Unavailable(FakeLLMProvider):
        async def extract(self, request):
            raise RateLimitProviderError(1)

    data, _ = create_case(phase1_client, 2)
    job = phase1_client.post("/parsing-jobs", json=data).json()
    task_id = uuid.UUID(job["progress"]["id"])
    with SessionFactory() as db:
        task = db.get(BackgroundTask, task_id)
        task.max_attempts = 2
        db.commit()
    for _ in range(3):
        make_due(task_id)
        asyncio.run(process_task(task_id, provider=Unavailable()))
    result = phase1_client.get(f"/parsing-jobs/{job['id']}").json()
    assert result["status"] == "failed"
    assert result["progress"]["attempts"] == 2
    assert result["progress"]["error_code"] == "provider_rate_limited"
    assert result["results"] == []
