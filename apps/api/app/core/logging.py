from __future__ import annotations

import logging


def configure_logging() -> None:
    """Configure concise operational logging without document/provider payloads."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
