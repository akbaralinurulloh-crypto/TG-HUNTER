"""Quality control and moderation guardrails (TZ Section 8)."""
import re
from typing import Tuple, List, Optional
from app.ai.schemas import AIAnalysisOutput
from app.logging_config import logger

PROHIBITED_CLAIMS = [
    re.compile(r"100%\s*(tekin|bepul)", re.IGNORECASE),
    re.compile(r"kafolatlangan\s*jannat", re.IGNORECASE),
    re.compile(r"hujjatsiz\s*viza", re.IGNORECASE),
    re.compile(r"sirli\s*usul", re.IGNORECASE),
    re.compile(r"tez\s*tarqating", re.IGNORECASE),
    re.compile(r"shoshiling\s*joylar\s*cheklangan\s*faqat\s*bugun", re.IGNORECASE),
]

SPAM_DOMAINS = [
    "t.me/joinchat",
    "bit.ly",
    "tinyurl.com",
    "crypto",
    "kazino",
    "1xbet",
]


class QualityControlService:
    """Enforces strict quality, safety, and truthfulness guardrails on content items."""

    @staticmethod
    def inspect_content(ai_output: AIAnalysisOutput) -> Tuple[bool, Optional[str]]:
        """
        Run content through quality filter rules (TZ Section 8).
        Returns (is_approved: bool, rejection_reason: Optional[str]).
        """
        full_text = f"{ai_output.headline} {ai_output.body}".lower()

        # 1. Prohibited claims and spam markers
        for pattern in PROHIBITED_CLAIMS:
            if pattern.search(full_text):
                reason = "Asossiz da'vo, manipulyativ reklama yoki shubhali va'da aniqlandi"
                logger.warning(f"Sifat nazorati rad etdi: {reason}")
                return False, reason

        # 2. Spam links
        for spam in SPAM_DOMAINS:
            if spam in full_text:
                reason = "Spam yoki shubhali tashqi havola aniqlandi"
                logger.warning(f"Sifat nazorati rad etdi: {reason}")
                return False, reason

        # 3. Legal copyright check
        if ai_output.rights_status != "VERIFIED":
            reason = "Foydalanish huquqi (mualliflik ruxsati) tasdiqlanmagan"
            logger.warning(f"Sifat nazorati rad etdi: {reason}")
            return False, reason

        # 4. Factual risk check
        if ai_output.factual_risk in ("SUSPICIOUS", "HIGH"):
            reason = f"Tekshirilmagan fakt yoki jiddiy xavf ({ai_output.factual_risk}) mavjud"
            logger.warning(f"Sifat nazorati rad etdi: {reason}")
            return False, reason

        # 5. Score threshold
        if ai_output.quality_score < 7:
            reason = f"Sifat bahosi minimal chegaradan past: {ai_output.quality_score}/10"
            logger.warning(f"Sifat nazorati rad etdi: {reason}")
            return False, reason

        # 6. Headline & body congruence
        if len(ai_output.headline.strip()) < 5 or len(ai_output.body.strip()) < 20:
            reason = "Sarlavha yoki matn hajmi standartlarga mos kelmaydi"
            logger.warning(f"Sifat nazorati rad etdi: {reason}")
            return False, reason

        return True, None
