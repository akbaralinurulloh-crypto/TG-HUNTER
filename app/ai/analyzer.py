"""AI Content analysis, topic evaluation and Uzbek rewriting service (TZ Section 7)."""
import json
import re
from typing import Optional, Dict, Any, List
from app.config import settings
from app.logging_config import logger
from app.ai.schemas import AIAnalysisOutput

SYSTEM_INSTRUCTION = """
Kanalga kelgan asl material asosida post tayyorla.
O‘zingdan hech narsa to‘qima, yolg‘on yoki yangi gap qo‘shma.
QAT'IY TAQIQLANADI: O'zingdan birorta hadis, diniy hukm yoki fatvo to‘qib yozish qat'iyan man etiladi! Hadis qo‘shma!
Hech qachon olingan manba yoki kanal nomini ko‘rsatma.
Begona telefon raqamlar va kontaktlarni olib tashla.
Post yakuniga faqat quyidagi rasmiy aloqa raqamini qo‘sh:
📞 Murojaat uchun: +998 88 832 77 00

Asl mazmunni qanday bo‘lsa shunday saqla. Faqat Umrah, Makka, Madina, ziyorat, sayohat va ziyoratchilar uchun foydali maslahatlarni qoldir.

Quyidagi qat'iy JSON formatida javob ber:
{
  "headline": "Qisqa sarlavha",
  "body": "Asl material matni (o'zgarishsiz, toza holda)...\n\n📞 Murojaat uchun: +998 88 832 77 00",
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
        raw = (raw_text or "").strip()

        # Guard 1: Textless post (never fabricate text or hadiths for empty media)
        if not raw or len(raw) < 15:
            logger.info("Matnsiz yoki juda qisqa post aniqlandi — to'qish taqiqlanganligi sababli rad etildi.")
            fallback = self._deterministic_fallback(raw, media_type, source_title, source_rights_status)
            return self._enforce_quality_and_rights(fallback, source_rights_status)

        # Guard 2: Strict Hadith prohibition
        if any(marker in raw.lower() for marker in self.HADITH_MARKERS):
            logger.info("Hadis aniqlandi — foydalanuvchi talabiga ko'ra rad etildi.")
            fallback = self._deterministic_fallback(raw, media_type, source_title, source_rights_status)
            return self._enforce_quality_and_rights(fallback, source_rights_status)

        prompt = (
            f"Manba: {source_title}\n"
            f"Media turi: {media_type}\n"
            f"Foydalanish huquqi: {source_rights_status}\n\n"
            f"Material matni:\n{raw}"
        )

        parsed_data = None
        if self.client:
            try:
                import asyncio
                response = await asyncio.wait_for(self._call_gemini_async(prompt), timeout=8.0)
                parsed_data = self._parse_json(response)
                # Ensure Gemini didn't fabricate hadiths
                if parsed_data:
                    gen_text = (parsed_data.get("body", "") + " " + parsed_data.get("headline", "")).lower()
                    if any(marker in gen_text for marker in self.HADITH_MARKERS):
                        logger.warning("AI javobida hadis aniqlandi — rad etilmoqda.")
                        parsed_data = None
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

    HADITH_MARKERS = [
        "hadis", "rivoyat", "payg'ambarimiz", "payg‘ambarimiz", "rasululloh",
        "sollallohu alayhi vasallam", "sahoba", "hadisi sharif", "imom buxoriy",
        "buxoriy rivoyati", "muslim rivoyati", "termiziy rivoyati",
    ]

    def _clean_and_sanitize_text(self, text: str) -> str:
        """Strip external phone numbers, competitor contacts, and third-party social media handles."""
        import re
        # Remove phone numbers
        text = re.sub(r'(\+?998[\s-]?)?\(?\d{2,3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}', '', text)
        text = re.sub(r'\+?\d{1,3}[\s-]?\d{2,3}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}', '', text)
        
        lines = text.split("\n")
        cleaned_lines = []
        skip_keywords = [
            "murojaat uchun", "telefon:", "murojaat:", "@muhtashamadmin",
            "batafsil va band", "batafsil ma'lumot", "batafsil ma’lumot", "batafsil ma`lumot",
            "batafsil malumot", "instagram", "facebook", "youtube", "tiktok", "t.me/",
            "manba:", "manba :", "nurli safar", "muhtasham umra", "muhtasham travel",
        ]
        
        for line in lines:
            line_str = line.strip()
            l_lower = line_str.lower()
            if any(kw in l_lower for kw in skip_keywords):
                continue
            # Filter pure handle or contact lines
            if line_str.startswith("@") or line_str.startswith("📞") or line_str.startswith("☎️") or line_str.startswith("📱"):
                continue
            cleaned_lines.append(line_str)
            
        result = "\n".join(l for l in cleaned_lines if l).strip()
        # Collapse multiple empty lines
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result

    def _deterministic_fallback(
        self, raw_text: Optional[str], media_type: str, source_title: str, source_rights: str
    ) -> dict:
        """Rule-based analyzer ensuring genuine channel Umrah content without hallucination or hadiths."""
        raw = (raw_text or "").strip()

        # Rule 1: Textless post rejection (never invent text or hadith for a picture)
        if not raw or len(raw) < 15:
            return {
                "headline": "Rad etildi",
                "body": "",
                "topic": "Boshqa",
                "quality_score": 0,
                "factual_risk": "NONE",
                "media_action": "IGNORE",
                "rights_status": source_rights,
                "publish_decision": "REJECT",
                "rejection_reason": "Matnsiz media post (o'zidan to'qib yozish taqiqlangan)",
            }

        # Rule 2: Strict Hadith prohibition (user requested: hadis yozish mumkin emas)
        raw_lower = raw.lower()
        if any(marker in raw_lower for marker in self.HADITH_MARKERS):
            logger.info("Hadis aniqlandi — foydalanuvchi talabiga ko'ra post rad etildi.")
            return {
                "headline": "Rad etildi (Hadis)",
                "body": raw,
                "topic": "Hadis",
                "quality_score": 0,
                "factual_risk": "SUSPICIOUS",
                "media_action": "IGNORE",
                "rights_status": source_rights,
                "publish_decision": "REJECT",
                "rejection_reason": "Hadis yozish qat'iyan taqiqlangan (Foydalanuvchi talabi)",
            }

        sanitized = self._clean_and_sanitize_text(raw)
        lower = sanitized.lower()

        # Check topic relevance
        is_relevant = any(t in lower for t in APPROVED_TOPICS) or "ziyorat" in lower or "umra" in lower
        topic = "Umrah" if is_relevant else "Boshqa"

        # Check if too short after sanitizing contacts
        is_too_short = len(sanitized) < 30

        # Check for unverified suspicious claims
        suspicious_markers = ["100% tekin", "kafolatlangan jannat", "sirli usul", "shoshiling tarqating"]
        has_suspicious = any(sm in lower for sm in suspicious_markers)
        factual_risk = "SUSPICIOUS" if has_suspicious else "NONE"

        # Calculate quality score (0-10)
        if is_too_short:
            score = 3
        elif is_relevant and len(sanitized) > 60:
            score = 8
        elif is_relevant:
            score = 7
        else:
            score = 2

        if has_suspicious:
            score = min(score, 4)

        # Headline without any source channel name
        headline = "Umra va Ziyorat Ma'lumotlari" if is_relevant else "Ma'lumot"
        first_line = sanitized.split('\n')[0].strip() if sanitized else ""
        if 10 <= len(first_line) <= 80 and not any(ch in first_line for ch in ["http", "@", "+998", "📞", "☎️", "📍", "💰"]):
            headline = first_line

        # Contact footer with official phone number (888327700)
        phone_contact = getattr(settings, "CONTACT_PHONE", "+998 88 832 77 00")
        body = f"{sanitized}\n\n📞 Murojaat uchun: {phone_contact}"

        decision = "AUTO_PUBLISH" if (score >= 7 and not has_suspicious and not is_too_short and source_rights == "VERIFIED") else "REJECT"
        rejection_reason = "Yetarlicha ma'lumot yo'q" if is_too_short else ("Mavzuga mos emas" if not is_relevant else None)

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
            rejection_reason = rejection_reason or "Umrah yoki sayohat mavzusiga aloqador emas"

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
