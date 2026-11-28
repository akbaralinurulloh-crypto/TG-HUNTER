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
ADMIN_LABEL = "@Muhtashamadmin"
ADMIN_URL = "https://t.me/muhiddinovak"
DEFAULT_TELEGRAM_CHANNEL = "@muhtashamtraveluzz"
DEFAULT_TELEGRAM_URL = "https://t.me/muhtashamtraveluz"
DEFAULT_INSTAGRAM_URL = "https://www.instagram.com/muhtasham_travel/"


def format_contact_footer(
    target_channel: str = DEFAULT_TELEGRAM_CHANNEL,
    instagram_url: str = DEFAULT_INSTAGRAM_URL,
    telegram_url: str = DEFAULT_TELEGRAM_URL,
) -> str:
    """Rasmiy kontaktlar va ijtimoiy tarmoqlar (Telegram va Instagram) zamonaviy giperhavolalari."""
    tg_url = telegram_url or DEFAULT_TELEGRAM_URL
    tg_link = f'<a href="{tg_url}">Telegram</a>'
    admin_link = f'<a href="{ADMIN_URL}">{ADMIN_LABEL}</a>'
    insta_link = f'<a href="{instagram_url}">Instagram</a>' if instagram_url else "Instagram"
    return (
        "📞 Batafsil va band qilish:\n"
        f"📲 {OFFICIAL_NUMBER}\n"
        f"📩 {admin_link}\n\n"
        f"📱 {tg_link}  |  📸 {insta_link}"
    )


def clean_trailing_contacts(text: str) -> str:
    """Eski yoki chala kontakt bloklarini, raqamlar ro'yxatini va YouTube/Facebook/Instagram/Telegram qatorlarini tozalaydi."""
    if not text:
        return text
    lines = []
    for line in text.splitlines():
        if re.search(
            r"\b(?:youtube|facebook|ютуб|фейсбук|instagram|инстаграм|telegram|телеграм)\b|@muhtashamadmin|https?://(?:www\.)?(?:instagram\.com|t\.me|youtube\.com|youtu\.be|facebook\.com)",
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


def _video_meta(path: Path, tmp_dir: Path | None = None) -> dict:
    """Telegram videoni telefonda qisib ('pakana') ko'rsatmasligi uchun width/height/duration va thumbnail ni tayyorlaydi."""
    try:
        import subprocess
        from PIL import Image
        from app.pipeline.video_clean import probe

        info = probe(path)
        meta: dict = {"supports_streaming": True}
        w, h = info.width, info.height
        if tmp_dir is not None and path.exists():
            thumb = tmp_dir / f"thumb_{path.stem}.jpg"
            p = subprocess.run(
                [
                    "ffmpeg", "-v", "error", "-y", "-i", str(path),
                    "-frames:v", "1",
                    "-vf", "scale='if(gte(iw,ih),320,-2)':'if(gte(iw,ih),-2,320)'",
                    "-q:v", "3", str(thumb),
                ],
                capture_output=True,
                timeout=20,
            )
            if p.returncode == 0 and thumb.exists() and thumb.stat().st_size > 0:
                meta["thumbnail"] = FSInputFile(thumb)
                with Image.open(thumb) as im:
                    tw, th = im.size
                if tw > 0 and th > 0 and w > 0 and h > 0:
                    # Agar thumbnail va probe nisbati bir-biridan farq qilsa, thumbnail nisbatini asos qilamiz
                    if (tw > th) != (w > h):
                        w, h = h, w
        if w > 0 and h > 0:
            meta["width"] = w
            meta["height"] = h
        if info.duration > 0:
            meta["duration"] = max(1, int(round(info.duration)))
        return meta
    except Exception:
        return {"supports_streaming": True}


class AiogramPublisher:
    def __init__(self, bot, *, max_retries: int = 5, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep, telethon_client=None):
        self.bot, self.max_retries, self._sleep, self.telethon_client = bot, max_retries, sleep, telethon_client

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

    async def _publish_via_telethon(self, chat_id: int | str, plan: PostPlan, tmp_dir: Path) -> list[int]:
        """Videolarni Telethon (MTProto) orqali 2 GB gacha hech qanday siqishsiz, asl sifat va nisbatda yuboradi."""
        from telethon.tl.types import DocumentAttributeVideo

        if len(plan.media) == 1:
            m = plan.media[0]
            meta = _video_meta(m.path, tmp_dir) if m.kind == "video" else {}
            kw: dict = {"caption": plan.caption or None, "parse_mode": "html"}
            if m.kind == "video":
                kw["supports_streaming"] = True
                if "thumbnail" in meta:
                    kw["thumb"] = str(meta["thumbnail"].path)
                if "width" in meta and "height" in meta:
                    kw["attributes"] = [
                        DocumentAttributeVideo(
                            duration=meta.get("duration", 1),
                            w=meta["width"],
                            h=meta["height"],
                            supports_streaming=True,
                        )
                    ]
            msg = await self.telethon_client.send_file(chat_id, str(m.path), **kw)
            return [msg.id]
        files = [str(m.path) for m in plan.media[:ALBUM_LIMIT]]
        msgs = await self.telethon_client.send_file(
            chat_id, files, caption=plan.caption or None, parse_mode="html", supports_streaming=True,
        )
        if not isinstance(msgs, list):
            msgs = [msgs]
        return [msg.id for msg in msgs]

    async def publish(self, chat_id: int | str, plan: PostPlan) -> list[int]:
        import tempfile
        ids: list[int] = []
        if not plan.media:
            for part in split_text(plan.text):
                ids.append((await self._call(self.bot.send_message, chat_id, part, parse_mode="HTML")).message_id)
            return ids
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            has_video = any(m.kind == "video" for m in plan.media)
            if has_video and self.telethon_client is not None:
                try:
                    ids = await self._publish_via_telethon(chat_id, plan, tmp_dir)
                    for part in split_text(plan.text):
                        ids.append((await self._call(self.bot.send_message, chat_id, part, parse_mode="HTML")).message_id)
                    return ids
                except Exception as exc:
                    max_size = max((m.path.stat().st_size for m in plan.media if m.path.exists()), default=0)
                    if max_size > 49 * 1024 * 1024:
                        raise
                    log.warning("telethon_publish_fallback_to_bot", error=str(exc)[:150])
            if len(plan.media) == 1:
                m = plan.media[0]
                send = self.bot.send_photo if m.kind == "photo" else self.bot.send_video
                kw = {"photo": FSInputFile(m.path)} if m.kind == "photo" else {"video": FSInputFile(m.path), **_video_meta(m.path, tmp_dir)}
                ids.append((await self._call(send, chat_id, caption=plan.caption or None, parse_mode="HTML", **kw)).message_id)
            else:
                group = [
                    (
                        InputMediaPhoto(
                            media=FSInputFile(m.path),
                            caption=(plan.caption or None) if i == 0 else None,
                            parse_mode="HTML" if (plan.caption and i == 0) else None,
                        )
                        if m.kind == "photo"
                        else InputMediaVideo(
                            media=FSInputFile(m.path),
                            caption=(plan.caption or None) if i == 0 else None,
                            parse_mode="HTML" if (plan.caption and i == 0) else None,
                            **_video_meta(m.path, tmp_dir),
                        )
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
