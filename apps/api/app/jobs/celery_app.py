from __future__ import annotations

import asyncio
import uuid
from typing import Any

from celery import Celery  # type: ignore[import-untyped]

from app.core.config import get_settings

celery_app: Any = Celery("document_parsing", broker=get_settings().redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=2,
    broker_transport_options={
        "visibility_timeout": 300,
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
    },
    beat_schedule={"recover-durable-jobs": {"task": "parsing.recover", "schedule": 5.0}},
)


def execute(task_id: str) -> None:
    from app.jobs.runner import process_task

    asyncio.run(process_task(uuid.UUID(task_id)))


def recover() -> int:
    from app.jobs.dispatch import recover_pending

    return recover_pending()


celery_app.task(name="parsing.execute")(execute)
celery_app.task(name="parsing.recover")(recover)
