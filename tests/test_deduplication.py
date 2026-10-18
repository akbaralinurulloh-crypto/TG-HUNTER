"""Tests for deduplication engine and semantic similarity (TZ Section 10)."""
import pytest
from app.sources.manager import SourceManager
from app.sources.collector import ContentCollector
from app.moderation.deduplication import DeduplicationEngine, calculate_semantic_similarity
from app.database.models import ContentItem, PublishedPost


@pytest.mark.asyncio
async def test_exact_hash_duplicate_detected(db_session):
    """Test that a post with identical content_hash is detected as duplicate."""
    mgr = SourceManager(db_session)
    await mgr.register_source("MuhtashamUmra", "Muhtasham Umra", "VERIFIED")

    collector = ContentCollector(db_session)
    post1 = await collector.ingest_post(
        source_identifier="MuhtashamUmra",
        source_message_id=201,
        original_text="Umrah ziyorati uchun yangi viza talablari e'lon qilindi.",
    )

    dedup = DeduplicationEngine(db_session)
    # Check post with same hash
    is_dup, reason, dup_id = await dedup.is_duplicate(
        content_hash=post1.content_hash,
        text_content=post1.original_text,
        current_post_id=999,  # different ID
    )
    assert is_dup is True
    assert dup_id == post1.id


@pytest.mark.asyncio
async def test_published_post_hash_duplicate_detected(db_session):
    """Test that content matching an already published post hash is blocked."""
    # Create fake published post
    mgr = SourceManager(db_session)
    await mgr.register_source("nurlisafar", "Nurli Safar", "VERIFIED")
    collector = ContentCollector(db_session)
    post = await collector.ingest_post("nurlisafar", 301, "Test matn")

    item = ContentItem(
        source_post_id=post.id,
        headline="Test Headline",
        body="Test Body",
        quality_score=9,
        publish_decision="AUTO_PUBLISH",
        status="PUBLISHED",
    )
    db_session.add(item)
    await db_session.commit()

    pub = PublishedPost(
        content_item_id=item.id,
        target_channel="@muhtashamtraveluzz",
        telegram_message_id=5555,
        content_hash="unique_hash_xyz123",
    )
    db_session.add(pub)
    await db_session.commit()

    dedup = DeduplicationEngine(db_session)
    is_dup, reason, pub_id = await dedup.is_duplicate(
        content_hash="unique_hash_xyz123",
        text_content="Some other text",
    )
    assert is_dup is True
    assert pub_id == pub.id


def test_semantic_similarity_paraphrase():
    """Test that paraphrased text in Uzbek has high semantic similarity."""
    t1 = "Saudiya Arabistoni Umra vizalarini rasmiylashtirish bo'yicha yangi soddalashtirilgan qoidalarni e'lon qildi."
    t2 = "Saudiya Arabistonida Umra vizalarini rasmiylashtirish tartibi yanada soddalashtirilgan yangi qoidalar bilan tasdiqlandi."
    sim = calculate_semantic_similarity(t1, t2)
    assert sim >= 0.70, f"Expected high similarity for paraphrased text, got {sim}"


def test_different_topics_have_low_similarity():
    """Test that two completely different texts have low similarity."""
    t1 = "Makka shahrida Masjid al-Haram hududi kengaytirilmoqda."
    t2 = "Toshkent shahridan Samarqandga tezyurar poyezd qatnovi yo'lga qo'yildi."
    sim = calculate_semantic_similarity(t1, t2)
    assert sim < 0.40
