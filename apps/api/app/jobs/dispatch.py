from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select

from app.db.session import SessionFactory
from app.jobs.models import ACTIVE_STATES, BackgroundTask

Dispatcher = Callable[[uuid.UUID], Awaitable[None]]
logger = logging.getLogger(__name__)


def publish_task(task_id: uuid.UUID) -> None:
    from app.jobs.celery_app import celery_app

    # The row is the outbox. A failed publish is recovered by the periodic sweep.
    try:
        celery_app.send_task("parsing.execute", args=[str(task_id)], retry=False)
    except Exception:
        logger.warning("task_dispatch_unavailable task_id=%s", task_id)
        return
    with SessionFactory() as db:
        task = db.get(BackgroundTask, task_id)
        if task is not None:
            task.dispatched_at = datetime.now(UTC)
            db.commit()


async def dispatch_task(task_id: uuid.UUID) -> None:
    await asyncio.to_thread(publish_task, task_id)


def get_dispatcher() -> Dispatcher:
    return dispatch_task


def recover_pending() -> int:
    now = datetime.now(UTC)
    with SessionFactory() as db:
        ids = list(
            db.scalars(
                select(BackgroundTask.id)
                .where(
                    BackgroundTask.state.in_(ACTIVE_STATES),
                    BackgroundTask.available_at <= now,
                    or_(
                        BackgroundTask.dispatched_at.is_(None),
                        BackgroundTask.dispatched_at < now - timedelta(seconds=30),
                    ),
                )
                .order_by(BackgroundTask.available_at)
                .limit(100)
            )
        )
    for task_id in ids:
        publish_task(task_id)
    return len(ids)
