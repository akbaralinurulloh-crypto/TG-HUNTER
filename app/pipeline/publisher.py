"""Kanalga joylash (aiogram). DRY-RUN'da kanalga emas, adminga ko'rsatadi."""
from __future__ import annotations

import asyncio
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Protocol

from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.types import FSInputFile, InputMediaPhoto, InputMediaVideo

from app.utils.logging import get_logger

log = get_logger("publisher")

CAPTION_LIMIT = 1024
TEXT_LIMIT = 4096
ALBUM_LIMIT = 10


@dataclass
class MediaItem:
    path: Path
    kind: str  # "photo" | "video"


@dataclass
class PostPlan:
    """Joylanadigan narsa: matn, yoki media (albom bo'lishi mumkin) + sarlavha + (sig'masa) alohida matn."""

    media: list[MediaItem]
    caption: str = ""
    text: str = ""  # media bo'lmasa — post matni; media bo'lsa va sarlavhaga sig'masa — alohida xabar


def split_text(text: str, limit: int = TEXT_LIMIT) -> list[str]:
    text = text.strip()
    parts: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        cut = cut if cut > limit // 2 else limit
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        parts.append(text)
    return parts


OFFICIAL_NUMBER = "+998 88 832 77 00"
ADMIN_USERNAME = "@Muhtashamadmin"
DEFAULT_TELEGRAM_CHANNEL = "@muhtashamtraveluzz"
DEFAULT_INSTAGRAM_URL = "https://www.instagram.com/muhtasham_travel/"


def format_contact_footer(
    target_channel: str = DEFAULT_TELEGRAM_CHANNEL,
    instagram_url: str = DEFAULT_INSTAGRAM_URL,
) -> str:
    """Rasmiy kontaktlar va ijtimoiy tarmoqlar (Telegram va Instagram) zamonaviy giperhavolalari."""
    tg_name = (target_channel or DEFAULT_TELEGRAM_CHANNEL).lstrip("@").strip()
    tg_url = f"https://t.me/{tg_name}"
    tg_link = f'<a href="{tg_url}">Telegram</a>'
    insta_link = f'<a href="{instagram_url}">Instagram</a>' if instagram_url else "Instagram"
    return (
        "📞 Batafsil va band qilish:\n"
        f"📲 {OFFICIAL_NUMBER}\n"
        f"📩 {ADMIN_USERNAME}\n\n"
        f"📱 {tg_link}  |  📸 {insta_link}"
    )


def clean_trailing_contacts(text: str) -> str:
    """Eski yoki chala kontakt bloklarini, raqamlar ro'yxatini va YouTube/Facebook/Instagram/Telegram qatorlarini tozalaydi."""
    if not text:
        return text
    lines = []
    for line in text.splitlines():
        if re.search(
            r"\b(?:youtube|facebook|ютуб|фейсбук|instagram|инстаграм|telegram|телеграм)\b|https?://(?:www\.)?(?:instagram\.com|t\.me|youtube\.com|youtu\.be|facebook\.com)",
            line,
            re.IGNORECASE,
        ):
            continue
        lines.append(line)
    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(
        r"(?:\n|^)\s*(?:[📞📱☎️📲📩✈️]|batafsil\s*va\s*band\s*qilish|batafsil|murojaat|aloqa|bog['’`]?lanish)[\s\S]*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned


def build_plan(
    cleaned_text: str,
    caption: str,
    media: list[MediaItem],
    instagram_url: str = "",
    target_channel: str = DEFAULT_TELEGRAM_CHANNEL,
) -> PostPlan:
    """Media bo'lsa: sarlavha = asl matn + izoh + kontaktlar (1024 ga sig'sa). Sig'masa — sarlavha = izoh + kontaktlar, asl matn alohida xabar."""
    raw_text = clean_trailing_contacts(cleaned_text.strip()) if instagram_url else cleaned_text.strip()
    raw_cap = clean_trailing_contacts(caption.strip()) if instagram_url else caption.strip()

    text = html.escape(raw_text, quote=False)
    cap = html.escape(raw_cap, quote=False)

    if instagram_url:
        footer = format_contact_footer(target_channel=target_channel, instagram_url=instagram_url)
        body = f"{text}\n\n{cap}".strip() if (text and cap) else (text or cap)
        combined = f"{body}\n\n{footer}".strip() if body else footer
    else:
        combined = f"{text}\n\n{cap}".strip() if (text and cap) else (text or cap)

    if not media:
        return PostPlan([], text=combined)
    if len(combined) <= CAPTION_LIMIT:
        return PostPlan(media, caption=combined)

    # Sig'masa: sarlavhaga izoh + kontaktlar, asl matn esa alohida xabar
    if instagram_url:
        cap_with_footer = f"{cap}\n\n{footer}".strip() if cap else footer
        if len(cap_with_footer) <= CAPTION_LIMIT:
            return PostPlan(media, caption=cap_with_footer, text=text)
        cut = max(0, CAPTION_LIMIT - len(footer) - 2)
        return PostPlan(media, caption=f"{cap[:cut]}\n\n{footer}", text=text)
    return PostPlan(media, caption=cap[:CAPTION_LIMIT], text=text)


class Publisher(Protocol):
    async def publish(self, chat_id: int | str, plan: PostPlan) -> list[int]: ...


class AiogramPublisher:
    def __init__(self, bot, *, max_retries: int = 5, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        self.bot, self.max_retries, self._sleep = bot, max_retries, sleep

    async def _call(self, fn, *args, **kwargs):
        """FloodWait (TelegramRetryAfter) va tarmoq xatolarida qayta uriniladi."""
        for attempt in range(self.max_retries + 1):
            try:
                return await fn(*args, **kwargs)
            except TelegramRetryAfter as exc:
                log.warning("flood_wait", seconds=exc.retry_after)
                if attempt == self.max_retries:
                    raise
                await self._sleep(exc.retry_after + 1)
            except TelegramNetworkError:
                if attempt == self.max_retries:
                    raise
                await self._sleep(min(2.0 * 2**attempt, 30))

    async def publish(self, chat_id: int | str, plan: PostPlan) -> list[int]:
        ids: list[int] = []
        if not plan.media:
            for part in split_text(plan.text):
                ids.append((await self._call(self.bot.send_message, chat_id, part, parse_mode="HTML")).message_id)
            return ids
        if len(plan.media) == 1:
            m = plan.media[0]
            send = self.bot.send_photo if m.kind == "photo" else self.bot.send_video
            kw = {"photo": FSInputFile(m.path)} if m.kind == "photo" else {"video": FSInputFile(m.path), "supports_streaming": True}
            ids.append((await self._call(send, chat_id, caption=plan.caption or None, parse_mode="HTML", **kw)).message_id)
        else:
            group = [
                (InputMediaPhoto if m.kind == "photo" else InputMediaVideo)(
                    media=FSInputFile(m.path),
                    caption=(plan.caption or None) if i == 0 else None,
                    parse_mode="HTML" if (plan.caption and i == 0) else None,
                )
                for i, m in enumerate(plan.media[:ALBUM_LIMIT])
            ]
            ids += [msg.message_id for msg in await self._call(self.bot.send_media_group, chat_id, group)]
        for part in split_text(plan.text):  # sarlavhaga sig'magan asl matn
            ids.append((await self._call(self.bot.send_message, chat_id, part, parse_mode="HTML")).message_id)
        return ids


def message_link(target_channel: str, message_id: int) -> str:
    t = target_channel.strip()
    if t.startswith("@"):
        return f"https://t.me/{t[1:]}/{message_id}"
    if t.lstrip("-").isdigit():
        n = t.lstrip("-")
        n = n[3:] if n.startswith("100") else n
        return f"https://t.me/c/{n}/{message_id}"
    return f"https://t.me/{t}/{message_id}"
