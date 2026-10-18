"""Tests for administrator permissions, configuration validation, and log sanitization (TZ Section 12, 15 & 18)."""
import pytest
from unittest.mock import MagicMock
from aiogram.types import User
from app.config import settings
from app.bot.middlewares import IsAdminFilter
from app.logging_config import sanitize_text


@pytest.mark.asyncio
async def test_admin_filter_permissions(mock_admin_ids):
    """Test that only authorized admin Telegram IDs pass IsAdminFilter."""
    admin_filter = IsAdminFilter()

    # Authorized admin user
    admin_event = MagicMock()
    admin_event.from_user = User(id=999888111, is_bot=False, first_name="AuthorizedAdmin")

    # Unauthorized stranger user
    stranger_event = MagicMock()
    stranger_event.from_user = User(id=11223344, is_bot=False, first_name="Stranger")

    assert await admin_filter(admin_event) is True
    assert await admin_filter(stranger_event) is False


def test_missing_config_validation(monkeypatch):
    """Test that missing mandatory settings are detected with clear error messages."""
    monkeypatch.setattr(settings, "BOT_TOKEN", "")
    monkeypatch.setattr(settings, "ADMIN_IDS", "")
    missing = settings.validate_required_settings()
    assert "BOT_TOKEN" in missing
    assert "ADMIN_IDS" in missing


def test_sensitive_log_sanitization():
    """Test that tokens, passwords, and API keys are masked in logs."""
    sample_text = (
        "Connecting to bot1234567890:ABCDefGhIJKlmNoPQRsTUVwxyZ_1234567 with "
        "AIzaSyDemoSecretGeminiKey12345678 and postgresql://postgres:MySuperSecretPass123@localhost:5432/db"
    )
    cleaned = sanitize_text(sample_text)

    assert "1234567890:ABCDefGhIJKlmNoPQRsTUVwxyZ_1234567" not in cleaned
    assert "AIzaSyDemoSecretGeminiKey12345678" not in cleaned
    assert "MySuperSecretPass123" not in cleaned
    assert "[REDACTED_SECRET]" in cleaned or "***@" in cleaned
