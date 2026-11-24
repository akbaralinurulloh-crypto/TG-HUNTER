"""Matnni tozalash: begona brendlar, reklama, so'ng telefon raqam. Ishonchsiz bo'lsa — fail-closed."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from app.pipeline.ad_filter import clean_ads
from app.pipeline.phone_replace import replace_phones

Status = Literal["ok", "reject", "manual_review"]

_BRAND_RE = re.compile(
    r"(?:[\s:–—\-«\"\*•|]*\b(?:nurli\s*safar|нурли\s*сафар|nurlisafar)(?:\s+(?:bilan|jamoasi|travel|umra))?\b[\s:–—\-»\"\*•|]*)"
    r"|(?:\b(?:nurli\s*safar|нурли\s*сафар|nurlisafar)\b)",
    re.IGNORECASE,
)

_BIRODAR_REPLACES = [
    (re.compile(r"\bbirodarlarimiz\b", re.IGNORECASE), "ziyoratchilarimiz"),
    (re.compile(r"\bbirodarlar\b", re.IGNORECASE), "ziyoratchilarimiz"),
    (re.compile(r"\bbirodarimiz\b", re.IGNORECASE), "ziyoratchimiz"),
    (re.compile(r"\bbirodar\b", re.IGNORECASE), "ziyoratchi"),
    (re.compile(r"\bбиродарларимиз\b", re.IGNORECASE), "зиёратчиларимиз"),
    (re.compile(r"\bбиродарлар\b", re.IGNORECASE), "зиёратчиларимиз"),
    (re.compile(r"\bбиродаримиз\b", re.IGNORECASE), "зиёратчимиз"),
    (re.compile(r"\bбиродар\b", re.IGNORECASE), "зиёратчи"),
]


def replace_birodar(text: str) -> str:
    """'Birodar' so'zlarini 'ziyoratchi / ziyoratchilarimiz'ga almashtiradi."""
    if not text:
        return text
    for pat, repl in _BIRODAR_REPLACES:
        text = pat.sub(repl, text)
    return text


def clean_brands(text: str) -> str:
    """Begona brend/kanal nomlarini (masalan Nurli Safar, stilistik shriftlar va h.k.) tozalaydi."""
    if not text:
        return text
    norm = unicodedata.normalize("NFKD", text)
    lines = []
    for line in norm.split("\n"):
        cleaned_line = _BRAND_RE.sub(" ", line).strip(" :–—-|")
        cleaned_line = re.sub(r" {2,}", " ", cleaned_line).strip()
        lines.append(cleaned_line)
    res = "\n".join(lines)
    res = re.sub(r"\n{3,}", "\n\n", res)
    return res.strip()


@dataclass
class TextCleanResult:
    text: str
    status: Status = "ok"
    reason: str | None = None
    phones_replaced: int = 0
    ads_removed: list[str] = field(default_factory=list)
    uncertain_numbers: list[str] = field(default_factory=list)


def clean_text(text: str) -> TextCleanResult:
    text = clean_brands(text)
    text = replace_birodar(text)
    ad = clean_ads(text)
    if ad.reject_reason:
        return TextCleanResult(text, "reject", ad.reject_reason)
    ph = replace_phones(ad.text)
    base = dict(text=ph.text, phones_replaced=ph.replaced, ads_removed=ad.removed, uncertain_numbers=ph.uncertain)
    if ph.uncertain:
        # Raqamni ishonchli almashtirib bo'lmadi: joylanmaydi, hisobotda "qo'lda ko'rib chiqing".
        return TextCleanResult(status="manual_review", reason="phone_uncertain", **base)
    return TextCleanResult(**base)
