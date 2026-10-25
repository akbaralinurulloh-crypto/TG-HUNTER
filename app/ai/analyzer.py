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
                self.client = genai.GenerativeModel(model_name=self.model_name)
                logger.info(f"Gemini AI client initialized with model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini AI client: {e}")

    def _extract_video_frames(self, video_path: str, max_frames: int = 3):
        """Extract representative frames from a video file using OpenCV."""
        import cv2
        from PIL import Image
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frames = []
        if total > 0:
            step = max(1, total // (max_frames + 1))
            for i in range(1, max_frames + 1):
                idx = min(step * i, total - 1)
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frames.append(Image.fromarray(rgb))
        cap.release()
        return frames

    async def _analyze_multimodal_media(
        self,
        media_path: str,
        media_type: str,
        raw_text: str,
        source_title: str,
        source_rights_status: str,
    ) -> Optional[dict]:
        """
        Multimodal analysis of image/video:
        1. Check for competitor text/logo ('Nurli Safar' or others) on screen, on bags, on clothes, in audio.
        2. Check for phone numbers other than user's official phone (+998 88 832 77 00).
        3. Check audio/speech for competitor mentions.
        4. Strictly prohibit hadiths.
        5. If clean, generate a beautiful, reverent, context-appropriate Uzbek caption for the channel.
        """
        import os
        import asyncio
        from PIL import Image

        try:
            parts = []
            if media_type == "PHOTO" and os.path.exists(media_path):
                parts.append(Image.open(media_path))
            elif media_type == "VIDEO" and os.path.exists(media_path):
                size_mb = os.path.getsize(media_path) / (1024 * 1024)
                if size_mb <= 15:
                    with open(media_path, "rb") as f:
                        parts.append({"mime_type": "video/mp4", "data": f.read()})
                else:
                    frames = self._extract_video_frames(media_path, max_frames=3)
                    parts.extend(frames)

            if not parts:
                return None

            prompt = (
                "Sen Muhtasham Travel agentligi uchun professional kontent tahlilchisisan.\n"
                "Ushbu media (rasm yoki video) va uning atrofidagi ma'lumotlarni juda qat'iy tekshir:\n"
                "1. Ekrandagi yozuvlarda, ziyoratchilarning kiyimlari, sumkalari, beydjiklarida, orqa fonda yoki "
                "videoning audio ovozida 'Nurli Safar' yoki boshqa har qanday begona firma/brend nomi yoki logotipi bormi?\n"
                "2. '+998 88 832 77 00' yoki '888327700' dan boshqa birorta begona telefon raqami ko'rsatilganmi (hatto sumkalarda yoki fonda bo'lsa ham)?\n"
                "3. Videoning audio ovozida 'Nurli Safar' yoki begona kompaniya haqida gapirilganmi?\n"
                "4. QAT'IY TAQIQLANADI: Birorta hadis to'qima va hadis qo'shma! Hadis yozish qat'iyan taqiqlangan!\n\n"
                "XULOSA QOIDALARI:\n"
                "- Agar 1, 2 yoki 3-bandlardan birortasida 'Nurli Safar', begona firma, begona logotip yoki begona telefon raqam bo'lsa:\n"
                "  \"has_competitor\": true, \"publish_decision\": \"REJECT\", \"rejection_reason\": \"Rasm yoki videoda begona belgi, firma nomi yoki telefon raqami aniqlandi\"\n"
                "- Faqat va faqat hech qanday begona firma belgisi va begona raqamsiz toza media bo'lsagina:\n"
                "  \"has_competitor\": false, \"publish_decision\": \"AUTO_PUBLISH\", \"topic\": \"Umrah\", \"quality_score\": 9,\n"
                "  \"headline\": \"Mavzuga yoki tasvirga mos qisqa, go'zal sarlavha\",\n"
                "  \"body\": \"Tasvirga mos, samimiy, chiroyli va ta'sirli o'zbek tilidagi izoh matni...\\n\\n📞 Murojaat uchun: +998 88 832 77 00\"\n\n"
                "Quyidagi JSON formatida javob ber:\n"
                "{\n"
                "  \"has_competitor\": true/false,\n"
                "  \"headline\": \"...\",\n"
                "  \"body\": \"...\\n\\n📞 Murojaat uchun: +998 88 832 77 00\",\n"
                "  \"topic\": \"Umrah\",\n"
                "  \"quality_score\": 9,\n"
                "  \"factual_risk\": \"NONE\",\n"
                "  \"media_action\": \"USE_ORIGINAL\",\n"
                "  \"publish_decision\": \"AUTO_PUBLISH\" yoki \"REJECT\",\n"
                "  \"rejection_reason\": null yoki \"sabab\"\n"
                "}"
            )

            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.client.generate_content(
                        [prompt] + parts,
                        generation_config={"temperature": 0.2, "response_mime_type": "application/json"},
                    )
                ),
                timeout=25.0
            )

            data = self._parse_json(response.text)
            if not data:
                return None

            # Safety check 1: Competitor mark
            if data.get("has_competitor") is True or str(data.get("publish_decision", "")).upper() == "REJECT":
                logger.info(f"Rasm yoki videoda raqobatchi belgisi/nomi aniqlandi: {data.get('rejection_reason')}")
                data["publish_decision"] = "REJECT"
                data["quality_score"] = 0
                data["rejection_reason"] = data.get("rejection_reason") or "Rasm yoki videoda Nurli Safar/begona belgi yoki telefon raqami aniqlandi"

            headline = str(data.get("headline") or "Umra va Ziyorat")
            body = str(data.get("body") or "")

            # Safety check 2: Hadith prohibition
            combined = (headline + " " + body).lower()
            if any(marker in combined for marker in self.HADITH_MARKERS):
                logger.warning("Generatsiya qilingan izohda hadis aniqlandi — darhol rad etilmoqda.")
                data["publish_decision"] = "REJECT"
                data["quality_score"] = 0
                data["rejection_reason"] = "Hadis yozish qat'iyan taqiqlangan (Foydalanuvchi talabi)"

            # Ensure contact phone is appended if auto publish
            if data.get("publish_decision") == "AUTO_PUBLISH":
                phone_contact = getattr(settings, "CONTACT_PHONE", "+998 88 832 77 00")
                if phone_contact not in body and "888327700" not in body and "88 832 77 00" not in body:
                    body = f"{body}\n\n📞 Murojaat uchun: {phone_contact}".strip()

            data["headline"] = headline
            data["body"] = body
            data["rights_status"] = source_rights_status
            return data

        except Exception as e:
            logger.error(f"Multimodal media analysis error for {media_path}: {e}")
            return None

    async def analyze_and_rewrite(
        self,
        raw_text: Optional[str],
        media_type: str = "TEXT",
        media_reference: Optional[str] = None,
        source_title: str = "Muhtasham",
        source_rights_status: str = "VERIFIED",
    ) -> AIAnalysisOutput:
        """
        Analyze and rewrite post content into fluent Uzbek, returning a validated AIAnalysisOutput.
        Supports multimodal inspection of images and videos.
        """
        import os
        raw = (raw_text or "").strip()

        # Guard 1: Strict Hadith prohibition on raw_text
        if any(marker in raw.lower() for marker in self.HADITH_MARKERS):
            logger.info("Hadis aniqlandi — foydalanuvchi talabiga ko'ra rad etildi.")
            fallback = self._deterministic_fallback(raw, media_type, source_title, source_rights_status)
            return self._enforce_quality_and_rights(fallback, source_rights_status)

        # Guard 2: Media with photo or video inspection
        has_media = bool(media_reference and os.path.exists(media_reference))
        if has_media and media_type in ("PHOTO", "VIDEO") and self.client:
            parsed_data = await self._analyze_multimodal_media(
                media_path=media_reference,
                media_type=media_type,
                raw_text=raw,
                source_title=source_title,
                source_rights_status=source_rights_status,
            )
            if parsed_data:
                return self._enforce_quality_and_rights(parsed_data, source_rights_status)

        # Guard 3: Textless post without verifiable media
        if not raw or len(raw) < 15:
            logger.info("Matnsiz yoki juda qisqa post aniqlandi — to'qish taqiqlanganligi sababli rad etildi.")
            fallback = self._deterministic_fallback(raw, media_type, source_title, source_rights_status)
            return self._enforce_quality_and_rights(fallback, source_rights_status)

        # Standard text post processing
        parsed_data = self._deterministic_fallback(raw, media_type, source_title, source_rights_status)
        return self._enforce_quality_and_rights(parsed_data, source_rights_status)

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
