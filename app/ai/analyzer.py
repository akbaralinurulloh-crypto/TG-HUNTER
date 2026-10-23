"""AI Content analysis, topic evaluation and Uzbek rewriting service (TZ Section 7)."""
import json
import re
from typing import Optional, Dict, Any, List
from app.config import settings
from app.logging_config import logger
from app.ai.schemas import AIAnalysisOutput

SYSTEM_INSTRUCTION = """
Berilgan ruxsatli material asosida o‘zbek tilida ravon, aniq, foydali va tabiiy Telegram posti tayyorla. 
Mavzuga mos qisqa sarlavha yoz. Asl mazmunni buzma. 
Manbada yo‘q fakt, narx, sana, mehmonxona nomi, masofa, viza talabi yoki diniy hukmni o‘zingdan qo‘shma. 
Shubhali ma’lumotlarni fakt sifatida bermagin. 
Keraksiz takrorlar, ortiqcha emoji va asossiz reklama da’volaridan qoch. 
Foydalanish huquqi va manba ko‘rsatish talablarini saqla.

Mavzular: Umrah, Makka, Madina, Masjid al-Haram, Masjid an-Nabaviy, ziyorat, sayohat va ziyoratchilar uchun foydali maslahatlar.

Quyidagi qat'iy JSON formatida javob ber:
{
  "headline": "Qisqa, jozibador sarlavha",
  "body": "O'zbek adabiy tilida ravon post matni...",
  "topic": "Umrah",
  "quality_score": 9,
  "factual_risk": "NONE",
  "media_action": "USE_ORIGINAL",
  "rights_status": "VERIFIED",
  "publish_decision": "AUTO_PUBLISH",
  "rejection_reason": null
}
"""

APPROVED_TOPICS = {
    "umrah", "haj", "makka", "madina", "masjid al-haram", "masjid an-nabaviy",
    "ziyorat", "sayohat", "maslahat", "viza", "parvoz", "mehmonxona"
}


class AIContentAnalyzer:
    """Evaluates and rewrites content using Gemini or deterministic rules."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = settings.AI_MODEL_NAME
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize Google Generative AI client if key is configured."""
        if self.api_key and self.api_key != "AIzaSyYourGeminiApiKeyHere123456789":
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.client = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=SYSTEM_INSTRUCTION,
                )
                logger.info(f"Gemini AI client initialized with model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini AI client: {e}")

    async def analyze_and_rewrite(
        self,
        raw_text: Optional[str],
        media_type: str = "TEXT",
        source_title: str = "Muhtasham",
        source_rights_status: str = "VERIFIED",
    ) -> AIAnalysisOutput:
        """
        Analyze and rewrite post content into fluent Uzbek, returning a validated AIAnalysisOutput.
        """
        prompt = (
            f"Manba: {source_title}\n"
            f"Media turi: {media_type}\n"
            f"Foydalanish huquqi: {source_rights_status}\n\n"
            f"Material matni:\n{raw_text or '[Matnsiz media post]'}"
        )

        parsed_data = None
        if self.client:
            try:
                import asyncio
                response = await asyncio.wait_for(self._call_gemini_async(prompt), timeout=8.0)
                parsed_data = self._parse_json(response)
            except asyncio.TimeoutError:
                logger.warning("Gemini API call timed out (8s limit). Seamlessly falling back to rule engine.")
                parsed_data = None
            except Exception as e:
                logger.error(f"Gemini API error during content analysis: {e}")
                parsed_data = None

        if not parsed_data:
            parsed_data = self._deterministic_fallback(raw_text, media_type, source_title, source_rights_status)

        # Enforce all safety and quality rules
        return self._enforce_quality_and_rights(parsed_data, source_rights_status)

    async def _call_gemini_async(self, prompt: str) -> str:
        import asyncio
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.generate_content(
                prompt,
                generation_config={"temperature": 0.2, "response_mime_type": "application/json"},
            ),
        )
        return response.text

    def _parse_json(self, text: str) -> Optional[dict]:
        try:
            cleaned = text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except Exception:
            return None

    def _deterministic_fallback(
        self, raw_text: Optional[str], media_type: str, source_title: str, source_rights: str
    ) -> dict:
        """Rule-based analyzer ensuring 100% offline reliability."""
        content = (raw_text or "").strip()
        lower = content.lower()

        # Check topic relevance
        is_relevant = any(t in lower for t in APPROVED_TOPICS) or "ziyorat" in lower or "umra" in lower
        topic = "Umrah" if is_relevant else "Boshqa"

        # Check for unverified suspicious claims
        suspicious_markers = ["100% tekin", "kafolatlangan jannat", "sirli usul", "shoshiling tarqating"]
        has_suspicious = any(sm in lower for sm in suspicious_markers)
        factual_risk = "SUSPICIOUS" if has_suspicious else "NONE"

        # Calculate quality score (0-10)
        score = 8 if (is_relevant and len(content) > 50) else (5 if is_relevant else 2)
        if has_suspicious:
            score = min(score, 4)

        headline = f"✨ {source_title}: Ziyorat yangiliklari" if is_relevant else "Ma'lumot"
        body = f"{content}\n\n📌 <i>Manba: {source_title}</i>"

        decision = "AUTO_PUBLISH" if (score >= 7 and not has_suspicious and source_rights == "VERIFIED") else (
            "PENDING_APPROVAL" if score >= 7 else "REJECT"
        )
        rejection_reason = "Mavzuga mos emas" if not is_relevant else ("Shubhali ma'lumot" if has_suspicious else None)

        return {
            "headline": headline,
            "body": body,
            "topic": topic,
            "quality_score": score,
            "factual_risk": factual_risk,
            "media_action": "USE_ORIGINAL",
            "rights_status": source_rights,
            "publish_decision": decision,
            "rejection_reason": rejection_reason,
        }

    def _enforce_quality_and_rights(self, data: dict, source_rights: str) -> AIAnalysisOutput:
        """
        Enforce strict business rules from TZ Sections 6, 7 & 8:
        1. Rights status: If not VERIFIED, NEVER AUTO_PUBLISH!
        2. Factual risk: If SUSPICIOUS or HIGH, NEVER AUTO_PUBLISH!
        3. Topic: If not in Umrah/travel domain, REJECT!
        4. Quality score: If < 7, REJECT!
        """
        score = max(0, min(10, int(data.get("quality_score", 0))))
        topic = str(data.get("topic", "Umrah")).strip()
        factual_risk = str(data.get("factual_risk", "NONE")).upper().strip()
        rights_status = "VERIFIED" if (source_rights == "VERIFIED" and str(data.get("rights_status", "")).upper() == "VERIFIED") else "UNVERIFIED"

        decision = str(data.get("publish_decision", "AUTO_PUBLISH")).upper().strip()
        rejection_reason = data.get("rejection_reason")

        # Rule 1: Copyright / Usage rights check (TZ Section 6)
        if rights_status != "VERIFIED":
            logger.warning("Foydalanish huquqi tasdiqlanmaganligi sababli avtonashr to'xtatildi.")
            decision = "REJECT"
            rejection_reason = rejection_reason or "Mualliflik huquqi / foydalanish ruxsati tasdiqlanmagan"

        # Rule 2: Factual Risk / Unverified claims (TZ Section 8)
        elif factual_risk in ("SUSPICIOUS", "HIGH"):
            logger.warning(f"Faktik xavf ({factual_risk}) aniqlanganligi sababli avtonashr to'xtatildi.")
            decision = "PENDING_APPROVAL" if score >= 7 else "REJECT"
            rejection_reason = rejection_reason or f"Faktik xavf aniqlandi ({factual_risk})"

        # Rule 3: Topic relevance check (TZ Section 8)
        elif topic.lower() not in APPROVED_TOPICS and not any(t in topic.lower() for t in ["umra", "ziyorat", "sayohat"]):
            logger.info(f"Post mavzusi ({topic}) Umrah va sayohatga mos emas deb topildi.")
            decision = "REJECT"
            rejection_reason = "Umrah yoki sayohat mavzusiga aloqador emas"

        # Rule 4: Quality score threshold
        elif score < 7:
            decision = "REJECT"
            rejection_reason = rejection_reason or f"Sifat bahosi yetarli emas ({score}/10)"

        else:
            decision = "AUTO_PUBLISH"

        return AIAnalysisOutput(
            headline=str(data.get("headline", "Ziyorat Yangiliklari")),
            body=str(data.get("body", "")),
            topic=topic,
            quality_score=score,
            factual_risk=factual_risk,
            media_action=str(data.get("media_action", "USE_ORIGINAL")),
            rights_status=rights_status,
            publish_decision=decision,
            rejection_reason=rejection_reason,
        )
