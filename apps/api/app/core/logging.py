from __future__ import annotations

import logging
from contextvars import ContextVar, Token

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


def set_request_id(request_id: str) -> Token[str]:
    return request_id_context.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    request_id_context.reset(token)


def configure_logging() -> None:
    """Configure concise operational logging without document/provider payloads."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
    )
    request_filter = RequestIdFilter()
    for handler in logging.getLogger().handlers:
        if not any(isinstance(item, RequestIdFilter) for item in handler.filters):
            handler.addFilter(request_filter)
