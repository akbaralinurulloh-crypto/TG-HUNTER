"""Tests for channel publishing and idempotency (TZ Section 9, 10 & 17)."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.sources.manager import SourceManager
from app.sources.collector import ContentCollector
from app.database.models import ContentItem, PublishedPost, SystemState
from app.publisher.telegram_publisher import TelegramPublisher
from app.publisher.channel_tester import ChannelTester


@pytest.mark.asyncio
async def test_publisher_atomic_and_idempotent(db_session):
    """Test that a post is published atomically and duplicate publishing attempts are skipped."""
    mgr = SourceManager(db_session)
    await mgr.register_source("MuhtashamUmra", "Muhtasham Umra", "VERIFIED")
    collector = ContentCollector(db_session)
    post = await collector.ingest_post("MuhtashamUmra", 601, "Test matn")

    item = ContentItem(
        source_post_id=post.id,
        headline="Yangilik",
        body="Matn",
        quality_score=9,
        publish_decision="AUTO_PUBLISH",
        status="APPROVED",
    )
    db_session.add(item)
    await db_session.commit()

    publisher = TelegramPublisher(bot=None)  # None runs in mock mode

    # First attempt: succeeds
    res1 = await publisher.publish_content_item(db_session, item.id)
    assert res1 is True
    await db_session.refresh(item)
    assert item.status == "PUBLISHED"

    # Second attempt: idempotent skip (does not duplicate)
    res2 = await publisher.publish_content_item(db_session, item.id)
    assert res2 is True

    from sqlalchemy import select, func
    count = (
        await db_session.execute(
            select(func.count(PublishedPost.id)).where(PublishedPost.content_item_id == item.id)
        )
    ).scalar_one()
    assert count == 1, "Kanalga bitta post uchun faqat bitta yozuv bo'lishi shart"


@pytest.mark.asyncio
async def test_publisher_paused_guard(db_session):
    """Test that publication is skipped when system is paused."""
    db_session.add(SystemState(key="is_paused", value="true"))

    mgr = SourceManager(db_session)
    await mgr.register_source("MuhtashamUmra", "Muhtasham Umra", "VERIFIED")
    collector = ContentCollector(db_session)
    post = await collector.ingest_post("MuhtashamUmra", 602, "Paused post")

    item = ContentItem(
        source_post_id=post.id,
        headline="Sarlavha",
        body="Matn",
        quality_score=9,
        publish_decision="AUTO_PUBLISH",
        status="APPROVED",
    )
    db_session.add(item)
    await db_session.commit()

    publisher = TelegramPublisher(bot=None)
    res = await publisher.publish_content_item(db_session, item.id)
    assert res is False
    await db_session.refresh(item)
    assert item.status != "PUBLISHED"


@pytest.mark.asyncio
async def test_channel_tester_mock_auth():
    """Test ChannelTester with mocked aiogram bot."""
    mock_bot = MagicMock()
    mock_bot.get_me = AsyncMock(return_value=MagicMock(id=12345, username="MuhtashamTestBot", first_name="Bot"))
    tester = ChannelTester(bot=mock_bot)
    auth_res = await tester.verify_bot_auth()
    assert auth_res["success"] is True
    assert auth_res["username"] == "MuhtashamTestBot"
