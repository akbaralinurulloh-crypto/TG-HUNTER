"""Pydantic schemas for AI content analysis output strictly matching TZ Section 7."""
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class AIAnalysisOutput(BaseModel):
    """Structured response required from AI analysis."""
    headline: str = Field(description="Qisqa, jozibador va mavzuga mos sarlavha")
    body: str = Field(description="O'zbek adabiy tilida ravon, tabiiy qayta yozilgan post matni")
    topic: str = Field(default="Umrah", description="Mavzu: Umrah, Makka, Madina, Ziyorat, Sayohat, Maslahat")
    quality_score: int = Field(ge=0, le=10, description="0 dan 10 gacha bo'lgan umumiy sifat bahosi")
    factual_risk: str = Field(default="NONE", description="Faktik xavf: NONE, SUSPICIOUS, HIGH")
    media_action: str = Field(default="USE_ORIGINAL", description="USE_ORIGINAL, USE_TEXT_ONLY, DISCARD")
    rights_status: str = Field(default="VERIFIED", description="VERIFIED yoki UNVERIFIED")
    publish_decision: str = Field(description="AUTO_PUBLISH, PENDING_APPROVAL, yoki REJECT")
    rejection_reason: Optional[str] = Field(default=None, description="Rad etilgan yoki to'xtatilgan bo'lsa sababi")

    @field_validator("quality_score")
    @classmethod
    def validate_quality_score(cls, v: int) -> int:
        if v < 0 or v > 10:
            raise ValueError("quality_score must be between 0 and 10")
        return v

    @field_validator("publish_decision")
    @classmethod
    def validate_publish_decision(cls, v: str) -> str:
        valid = {"AUTO_PUBLISH", "PENDING_APPROVAL", "REJECT"}
        upper_v = v.upper().strip()
        if upper_v not in valid:
            raise ValueError(f"publish_decision must be one of {valid}")
        return upper_v
