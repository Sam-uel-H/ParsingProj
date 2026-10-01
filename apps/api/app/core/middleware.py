from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from time import perf_counter

from fastapi import Request, Response

from app.core.logging import reset_request_id, set_request_id

logger = logging.getLogger("app.requests")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "")
    if REQUEST_ID_PATTERN.fullmatch(supplied):
        return supplied
    return str(uuid.uuid4())


async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = _request_id(request)
    request.state.request_id = request_id
    token = set_request_id(request_id)
    started = perf_counter()
    try:
        response = await call_next(request)
        duration_ms = round((perf_counter() - started) * 1000)
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        reset_request_id(token)
