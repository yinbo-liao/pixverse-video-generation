"""Structured logging configuration.

Uses Python stdlib logging with a format suitable for both human-readable
development output and JSON-structured production logging.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings


def setup_logging(settings: Settings | None = None) -> None:
    """Configure root logger based on application settings.

    In debug mode: colored, human-readable console output.
    In production: structured key=value format for log aggregation.
    """
    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    level = _resolve_level(settings.log_level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    if settings.debug:
        fmt = "%(asctime)s [%(levelname)-7s] %(name)s | %(message)s"
        datefmt = "%H:%M:%S"
    else:
        fmt = "time=%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s"
        datefmt = "%Y-%m-%dT%H:%M:%S"

    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(level)
    # Remove any pre-existing handlers to avoid duplicate output
    root.handlers.clear()
    root.addHandler(handler)

    # Silence noisy third-party loggers unless debugging
    if not settings.debug:
        for noisy in ("httpx", "httpcore", "urllib3", "asyncio"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def _resolve_level(name: str) -> int:
    """Resolve a case-insensitive log level name to its int constant."""
    try:
        return getattr(logging, name.upper())
    except AttributeError:
        return logging.INFO
