"""Tests for AI content analysis, schema validation, and quality guardrails (TZ Section 7 & 8)."""
import pytest
from app.ai.schemas import AIAnalysisOutput
from app.ai.analyzer import AIContentAnalyzer
from app.moderation.quality import QualityControlService


def test_ai_schema_validation_valid():
    """Test that valid AI response matches Pydantic schema."""
    data = {
        "headline": "Makka ziyorati uchun yangi reyslar",
        "body": "Ziyoratchilar uchun Makka shahriga to'g'ridan-to'g'ri yangi aviaqatnovlar yo'lga qo'yildi.",
        "topic": "Umrah",
        "quality_score": 9,
        "factual_risk": "NONE",
        "media_action": "USE_ORIGINAL",
        "rights_status": "VERIFIED",
        "publish_decision": "AUTO_PUBLISH",
        "rejection_reason": None,
    }
    model = AIAnalysisOutput(**data)
    assert model.quality_score == 9
    assert model.publish_decision == "AUTO_PUBLISH"


def test_ai_schema_validation_invalid_score():
    """Test that quality_score > 10 or < 0 fails schema validation."""
    with pytest.raises(ValueError):
        AIAnalysisOutput(
            headline="Sarlavha",
            body="Matn",
            quality_score=15,  # Invalid
            publish_decision="AUTO_PUBLISH",
        )


@pytest.mark.asyncio
async def test_irrelevant_topic_rejection():
    """Test that a post unrelated to Umrah/travel is rejected by AI and quality control."""
    analyzer = AIContentAnalyzer()
    res = await analyzer.analyze_and_rewrite(
        raw_text="Kriptovalyuta bozorida bugun Bitcoin narxi keskin ko'tarildi va yangi rekord o'rnatildi.",
        source_title="Crypto News",
        source_rights_status="VERIFIED",
    )
    assert res.publish_decision == "REJECT"
    assert "aloqador emas" in (res.rejection_reason or "").lower() or res.topic == "Boshqa"


@pytest.mark.asyncio
async def test_factual_risk_blocks_autopublish():
    """Test that suspicious/unverified claims block AUTO_PUBLISH and trigger review."""
    analyzer = AIContentAnalyzer()
    res = await analyzer.analyze_and_rewrite(
        raw_text="Shoshiling tarqating! 100% tekin viza va kafolatlangan ziyorat imkoniyati e'lon qilindi!",
        source_title="Shubhali Kanal",
        source_rights_status="VERIFIED",
    )
    assert res.publish_decision != "AUTO_PUBLISH"
    assert res.factual_risk in ("SUSPICIOUS", "HIGH")


@pytest.mark.asyncio
async def test_unverified_rights_blocks_autopublish():
    """Test that content from a source with UNVERIFIED rights is rejected."""
    analyzer = AIContentAnalyzer()
    res = await analyzer.analyze_and_rewrite(
        raw_text="Saudiya Arabistonida ziyoratchilar uchun yangi qulayliklar yaratildi.",
        source_title="Noma'lum Kanal",
        source_rights_status="UNVERIFIED",
    )
    assert res.publish_decision == "REJECT"
    assert "huquq" in (res.rejection_reason or "").lower()


def test_quality_control_spam_detection():
    """Test QualityControlService detects manipulative claims and spam."""
    ai_out = AIAnalysisOutput(
        headline="Yangi narxlar",
        body="Tez tarqating! 100% tekin ziyorat paketi bit.ly/free-umrah havolasida!",
        topic="Umrah",
        quality_score=9,
        factual_risk="NONE",
        media_action="USE_ORIGINAL",
        rights_status="VERIFIED",
        publish_decision="AUTO_PUBLISH",
    )
    approved, reason = QualityControlService.inspect_content(ai_out)
    assert approved is False
    assert reason is not None
