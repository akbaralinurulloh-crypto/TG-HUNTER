"""Tests for sources and legal usage rights management (TZ Section 5, 6 & 18)."""
import pytest
from app.sources.manager import SourceManager
from app.sources.collector import ContentCollector
from app.database.models import Source, SourcePost


@pytest.mark.asyncio
async def test_source_registration_and_rights(db_session):
    """Test registering source and verifying usage rights."""
    mgr = SourceManager(db_session)
    src = await mgr.register_source(
        identifier="MuhtashamUmra",
        title="Muhtasham Umra",
        rights_status="VERIFIED",
        rights_notes="Rasmiy manba",
    )
    assert src.id is not None
    assert src.telegram_identifier == "MuhtashamUmra"
    assert src.rights_status == "VERIFIED"

    # Test rights check
    rights = await mgr.check_usage_rights("MuhtashamUmra")
    assert rights["allowed"] is True
    assert rights["status"] == "VERIFIED"

    # Test unknown source rights check
    unknown_rights = await mgr.check_usage_rights("random_channel_999")
    assert unknown_rights["allowed"] is False
    assert unknown_rights["status"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_unverified_source_is_not_allowed(db_session):
    """Test that a source with UNVERIFIED rights is not allowed for auto-publishing."""
    mgr = SourceManager(db_session)
    await mgr.register_source(
        identifier="shubhali_kanal",
        title="Shubhali Kanal",
        rights_status="UNVERIFIED",
        rights_notes="Huquqi aniqlanmagan",
    )
    rights = await mgr.check_usage_rights("shubhali_kanal")
    assert rights["allowed"] is False
    assert rights["status"] == "UNVERIFIED"


@pytest.mark.asyncio
async def test_post_ingestion_and_duplicate_prevention(db_session):
    """Test that a new post is saved in source_posts and duplicates with same source_message_id are skipped."""
    mgr = SourceManager(db_session)
    await mgr.register_source("nurlisafar", "Nurli Safar", "VERIFIED")

    collector = ContentCollector(db_session)

    # Ingest post 1
    post1 = await collector.ingest_post(
        source_identifier="nurlisafar",
        source_message_id=101,
        original_text="Ramozon oyi Umra ziyorati narxlari va qulayliklari.",
        media_type="PHOTO",
    )
    assert post1 is not None
    assert post1.source_message_id == 101
    assert post1.content_hash is not None

    # Ingest duplicate post with identical source_message_id
    dup_post = await collector.ingest_post(
        source_identifier="nurlisafar",
        source_message_id=101,
        original_text="Boshqa matn bo'lsa ham ID bir xil",
    )
    assert dup_post is None, "A post with the same (source_id, source_message_id) must be skipped."
