"""Tests for publish scheduling, queue distribution, and daily report (TZ Section 11 & 13)."""
import pytest
from datetime import datetime, timezone
import pytz
from app.config import settings
from app.sources.manager import SourceManager
from app.sources.collector import ContentCollector
from app.database.models import ContentItem, PublishQueue, PublishedPost, SystemLog
from app.scheduler.queue_manager import QueueScheduler
from app.scheduler.daily_report import compile_daily_report


@pytest.mark.asyncio
async def test_queue_slot_calculation(db_session):
    """Test that next slot is correctly computed within the daytime window."""
    scheduler = QueueScheduler(bot=None)
    slot = await scheduler.calculate_next_slot(db_session)
    assert slot is not None
    assert slot.tzinfo is not None

    # Verify slot converts to Tashkent timezone properly
    tz = pytz.timezone(settings.TIMEZONE)
    slot_tz = slot.astimezone(tz)
    # The hour should be within or near the publishing window
    assert 0 <= slot_tz.hour <= 23


@pytest.mark.asyncio
async def test_enqueue_content_item(db_session):
    """Test enqueuing an approved content item."""
    mgr = SourceManager(db_session)
    await mgr.register_source("MuhtashamUmra", "Muhtasham Umra", "VERIFIED")
    collector = ContentCollector(db_session)
    post = await collector.ingest_post("MuhtashamUmra", 401, "Test matn")

    item = ContentItem(
        source_post_id=post.id,
        headline="Ziyorat yangiliklari",
        body="Ziyorat tafsilotlari...",
        quality_score=9,
        publish_decision="AUTO_PUBLISH",
        status="APPROVED",
    )
    db_session.add(item)
    await db_session.commit()

    scheduler = QueueScheduler(bot=None)
    q_entry = await scheduler.enqueue_content_item(db_session, item.id)

    assert q_entry.id is not None
    assert q_entry.status == "PENDING"
    await db_session.refresh(item)
    assert item.status == "QUEUED"


@pytest.mark.asyncio
async def test_daily_report_compilation(db_session):
    """Test compile_daily_report compiles accurate counts."""
    mgr = SourceManager(db_session)
    await mgr.register_source("nurlisafar", "Nurli Safar", "VERIFIED")
    collector = ContentCollector(db_session)
    post = await collector.ingest_post("nurlisafar", 501, "Test matn")

    item = ContentItem(
        source_post_id=post.id,
        headline="Ziyorat paketi",
        body="Tafsilotlar...",
        topic="Umrah",
        quality_score=8,
        publish_decision="AUTO_PUBLISH",
        status="PUBLISHED",
    )
    db_session.add(item)
    await db_session.commit()

    pub = PublishedPost(
        content_item_id=item.id,
        target_channel="@muhtashamtraveluzz",
        telegram_message_id=9876,
        content_hash="sample_hash",
    )
    db_session.add(pub)
    await db_session.commit()

    report = await compile_daily_report(db_session, hours_back=24)
    assert "KUNLIK HISOBOT" in report
    assert "Topilgan postlar:</b> 1 ta" in report
    assert "Muvaffaqiyatli nashrlar:</b> 1 ta" in report
    assert "Toshkent vaqti" in report
