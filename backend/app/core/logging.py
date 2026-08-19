"""Structured logging foundation.

Configures Python's standard logging with a consistent, parseable format.
Kept intentionally simple - no external logging framework is needed yet.
"""
import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging handlers. Safe to call multiple times."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
    root_logger.setLevel(level)
