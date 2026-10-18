"""Logging configuration with sensitive data sanitization."""
import sys
import re
import os
from pathlib import Path
from loguru import logger

# Regex patterns to sanitize sensitive tokens from logs
SENSITIVE_PATTERNS = [
    re.compile(r"bot\d+:[a-zA-Z0-9_-]{30,}", re.IGNORECASE),
    re.compile(r"\b\d{8,10}:[a-zA-Z0-9_-]{30,}\b"),
    re.compile(r"AIza[0-9A-Za-z-_]{20,}"),
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),
    re.compile(r"://([^:]+):([^@]+)@"),
    re.compile(r"1[a-zA-Z0-9_\-=]{50,}"),
]


def sanitize_text(text: str) -> str:
    """Mask known sensitive patterns from log messages."""
    if not isinstance(text, str):
        text = str(text)
    for pattern in SENSITIVE_PATTERNS:
        if pattern.pattern == r"://([^:]+):([^@]+)@":
            text = pattern.sub(r"://\1:***@", text)
        else:
            text = pattern.sub("[REDACTED_SECRET]", text)
    return text


def secret_filter(record: dict) -> bool:
    """Loguru filter to sanitize log messages before emission."""
    record["message"] = sanitize_text(record["message"])
    return True


def setup_logging(log_level: str = "INFO", log_dir: str = "logs"):
    """Configure structured logging to console and daily rotating file."""
    logger.remove()
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Console sink
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        filter=secret_filter,
    )

    # File sink with rotation and retention
    log_file = os.path.join(log_dir, "umrah_agent_{time:YYYY-MM-DD}.log")
    logger.add(
        log_file,
        level=log_level,
        rotation="00:00",
        retention="14 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        filter=secret_filter,
        encoding="utf-8",
    )
    return logger


# Initialize default setup
setup_logging()

__all__ = ["logger", "setup_logging", "sanitize_text"]
