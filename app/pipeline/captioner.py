"""Izoh yozish + ikki qatlamli tekshiruv (kod validatorlari, so'ng LLM validator). Q1/Q2/Q3."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from app.config import AppConfig
from app.llm.base import LLMClient, LLMError
from app.llm.prompts import load_prompt
from app.pipeline.validators import HADITH_KEYWORD, caption_problems, verdict_problems


@dataclass
class CaptionResult:
    ok: bool
    caption: str = ""
    reason: str | None = None  # rad etilganda: hadis_validator | fact_validator | caption_failed | llm_error
    attempts: int = 0
    problems: list[str] = field(default_factory=list)


def _reason(problems: list[str]) -> str:
    if HADITH_KEYWORD in problems:
        return "hadis_validator"
    if "unsupported_claim" in problems or "unsupported_number" in problems:
        return "fact_validator"
    return "caption_failed"


async def make_caption(llm: LLMClient, cfg: AppConfig, source_text: str, images: Sequence[bytes] = ()) -> CaptionResult:
    imgs = list(images)[: cfg.llm.max_images]
    cap_system = load_prompt("captioner")
    val_system = load_prompt("validator")
    feedback = ""
    problems: list[str] = []
    for attempt in range(1, cfg.caption.max_attempts + 1):
        hint = ""
        if not source_text or len(source_text.strip()) < 80:
            hint = (
                "\n\nKo'rsatma: Manba matni yo'q yoki juda kam. Kadrlardagi ziyorat ruhiyatidan kelib chiqib, "
                "inson qalbini hissiyotlantiradigan, mehr va ziyoratga sog'inch uyg'otadigan 3–4 jumlali samimiy va ta'sirli izoh yozing. "
                "'Birodar' so'zi mutlaqo ishlatilmasin, o'rniga umumiy 'ziyoratchilarimiz' (ayollar bo'lsa 'hoji onalarimiz', erkaklar bo'lsa 'hoji otalarimiz') deb yozilsin. "
                "Hadis va rivoyatlar mutlaqo ishlatilmasin."
            )
        else:
            hint = (
                "\n\nKo'rsatma: Matn mazmuni va ziyorat ruhiyatiga mos, insonni to'lqinlantiradigan 3–4 jumlali ta'sirli va samimiy izoh yozing. "
                "'Birodar' so'zi mutlaqo ishlatilmasin, o'rniga umumiy 'ziyoratchilarimiz' (ayollar bo'lsa 'hoji onalarimiz', erkaklar bo'lsa 'hoji otalarimiz') deb yozilsin. "
                "Hadis va rivoyatlar mutlaqo ishlatilmasin."
            )
        user = f"MANBA MATNI:\n<<<\n{source_text or '(matn yo`q, faqat media)'}\n>>>{hint}"
        if feedback:
            user += f"\n\nTuzatish: oldingi izoh quyidagi sabablarga ko'ra rad etildi: {feedback}. Qoidalarga qat'iy rioya qiling."
        try:
            raw = (await llm.generate_json(system=cap_system, user=user, images=imgs)).get("caption")
        except LLMError as exc:
            return CaptionResult(False, reason="llm_error", attempts=attempt, problems=[str(exc)])
        caption = re.sub(r"\s+", " ", raw).strip() if isinstance(raw, str) else ""

        problems = caption_problems(
            caption,
            source_text,
            banned_keywords=cfg.banned_caption_keywords,
            max_length=cfg.caption.max_length,
            max_sentences=getattr(cfg.caption, "max_sentences", 4),
        )
        if not problems:
            vuser = f"MANBA MATNI:\n<<<\n{source_text or '(matn yo`q)'}\n>>>\n\nIZOH:\n<<<\n{caption}\n>>>"
            try:
                verdict = await llm.generate_json(system=val_system, user=vuser, images=imgs)
            except LLMError as exc:
                return CaptionResult(False, reason="llm_error", attempts=attempt, problems=[str(exc)])
            problems = verdict_problems(verdict)
            if not problems:
                return CaptionResult(True, caption, attempts=attempt)
        feedback = ", ".join(problems)
    return CaptionResult(False, reason=_reason(problems), attempts=cfg.caption.max_attempts, problems=problems)
