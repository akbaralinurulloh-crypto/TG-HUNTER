"""Target channel publisher with atomic locking and idempotency (TZ Section 9, 10 & 11)."""
import os
import asyncio
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot
from aiogram.types import FSInputFile, InputMediaPhoto, InputMediaVideo
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError, TelegramRetryAfter
from app.config import settings
from app.logging_config import logger
from app.database.models import (
    ContentItem,
    PublishQueue,
    PublishedPost,
    SystemLog,
    SystemState,
    SourcePost,
)


class TelegramPublisher:
    """Publishes moderated Umrah content to the target channel atomically."""

    def __init__(self, bot: Optional[Bot] = None):
        self.bot = bot
        self.target_channel = settings.TARGET_CHANNEL

    async def publish_content_item(
        self,
        session: AsyncSession,
        content_item_id: int,
    ) -> bool:
        """
        Atomically lock and publish a ContentItem to the target channel.
        Guarantees that a post is never published more than once.
        """
        # 1. Check system pause flag
        pause_state = await session.get(SystemState, "is_paused")
        if pause_state and pause_state.value.lower() == "true":
            logger.warning(f"Avtomatik nashr to'xtatilgan (PAUSED). Post #{content_item_id} o'tkazib yuborildi.")
            return False

        # 2. Check if already published
        pub_stmt = select(PublishedPost).where(PublishedPost.content_item_id == content_item_id)
        already_pub = (await session.execute(pub_stmt)).scalars().first()
        if already_pub:
            logger.warning(f"ContentItem #{content_item_id} allaqachon kanalga chiqqan (Msg ID: {already_pub.telegram_message_id}). Idempotent skip.")
            return True

        # 3. Query ContentItem with row lock
        stmt = select(ContentItem).where(ContentItem.id == content_item_id)
        if session.bind and session.bind.dialect.name != "sqlite":
            stmt = stmt.with_for_update()
        content_item: Optional[ContentItem] = (await session.execute(stmt)).scalars().first()

        if not content_item:
            logger.error(f"ContentItem #{content_item_id} topilmadi.")
            return False

        if content_item.status == "PUBLISHED":
            logger.warning(f"ContentItem #{content_item_id} statusi PUBLISHED. Qayta yuborilmaydi.")
            return True

        if content_item.status not in ("QUEUED", "APPROVED", "NEW"):
            logger.warning(f"ContentItem #{content_item_id} nashr uchun yaroqsiz statusda: {content_item.status}")
            return False

        # Atomically transition to PUBLISHING
        content_item.status = "PUBLISHING"
        await session.commit()

        # Format message text: Bold headline + body
        headline = content_item.headline
        for bad in ["Muhtasham Travel:", "Nurli Safar:", "Muhtasham Umra:", "Manba:", "✨ "]:
            headline = headline.replace(bad, "").strip()
        if not headline or headline.lower() == "ma'lumot":
            headline = "Umra va Ziyorat Ma'lumotlari"

        body = content_item.body
        for bad in [
            "📌 Manba: Nurli Safar", "📌 Manba: Muhtasham Travel", "📌 Manba: Muhtasham Umra",
            "📌 Manba:", "Manba: Nurli Safar", "Manba: Muhtasham Travel", "Manba: Muhtasham Umra",
            "📌 <i>Muhtasham Travel rasmiy ziyorat xabarnomasi</i>",
        ]:
            body = body.replace(bad, "").strip()

        # Ensure contact phone 888327700 is appended at the end
        contact_phone = getattr(settings, "CONTACT_PHONE", "+998 88 832 77 00")
        if "888327700" not in body and "88 832 77 00" not in body and contact_phone not in body:
            body = f"{body}\n\n📞 Murojaat uchun: {contact_phone}"

        formatted_text = f"🕋 <b>{headline}</b>\n\n{body}"

        # Resolve media if any from source_post
        source_post = await session.get(SourcePost, content_item.source_post_id) if content_item.source_post_id else None
        media_ref = source_post.media_reference if source_post else None
        media_type = source_post.media_type if source_post else "TEXT"

        channels = settings.target_channels_list or [self.target_channel]
        published_records = []
        error_msgs = []

        for ch in channels:
            try:
                if not self.bot:
                    logger.info(f"[DRY-RUN / MOCK] Publishing ContentItem #{content_item_id} to {ch}")
                    published_records.append((ch, 99990000 + content_item_id))
                else:
                    msg_id = await self._send_telegram(formatted_text, media_type, media_ref, target_channel=ch)
                    published_records.append((ch, msg_id))
            except TelegramRetryAfter as retry_err:
                logger.warning(f"Telegram FloodWait while publishing #{content_item_id} to {ch}: waiting {retry_err.retry_after}s")
                await asyncio.sleep(retry_err.retry_after)
                try:
                    msg_id = await self._send_telegram(formatted_text, media_type, media_ref, target_channel=ch)
                    published_records.append((ch, msg_id))
                except Exception as e:
                    error_msgs.append(f"{ch}: {e}")
            except Exception as e:
                logger.error(f"Error publishing #{content_item_id} to {ch}: {e}")
                error_msgs.append(f"{ch}: {e}")

        # Atomic finalize
        if published_records:
            primary_ch, primary_msg_id = published_records[0]
            all_channels = ", ".join(ch for ch, _ in published_records)
            content_item.status = "PUBLISHED"
            content_hash = source_post.content_hash if source_post else str(content_item_id)
            published_record = PublishedPost(
                content_item_id=content_item.id,
                target_channel=all_channels,
                telegram_message_id=primary_msg_id,
                content_hash=content_hash,
            )
            session.add(published_record)

            # Update queue entry if exists
            q_stmt = select(PublishQueue).where(PublishQueue.content_item_id == content_item.id)
            q_entry = (await session.execute(q_stmt)).scalars().first()
            if q_entry:
                q_entry.status = "PUBLISHED"

            log = SystemLog(
                event_type="POST_PUBLISHED",
                severity="INFO",
                message=f"Post #{content_item.id} {all_channels} ga joylandi (Msg ID: {primary_msg_id})",
            )
            session.add(log)
            await session.commit()
            logger.info(f"Post #{content_item.id} muvaffaqiyatli kanal(lar)ga joylandi ({all_channels})")
            return True
        else:
            content_item.status = "FAILED"
            combined_err = "; ".join(error_msgs) if error_msgs else "Noma'lum xatolik"
            log = SystemLog(
                event_type="PUBLISH_FAILED",
                severity="ERROR",
                message=f"Post #{content_item.id} nashri muvaffaqiyatsiz bo'ldi: {combined_err}",
            )
            session.add(log)
            await session.commit()
            return False

    async def _send_telegram(
        self,
        text: str,
        media_type: str,
        media_ref: Optional[str],
        target_channel: Optional[str] = None,
    ) -> int:
        """Send message, photo, or video to Telegram target channel."""
        has_local_file = media_ref and os.path.exists(media_ref)
        dest_channel = target_channel or self.target_channel

        if not has_local_file or media_type == "TEXT":
            msg = await self.bot.send_message(
                chat_id=dest_channel,
                text=text[:4096],
                parse_mode="HTML",
                disable_web_page_preview=False,
            )
            return msg.message_id

        caption_trunc = text[:1024]
        if media_type == "PHOTO":
            msg = await self.bot.send_photo(
                chat_id=dest_channel,
                photo=FSInputFile(media_ref),
                caption=caption_trunc,
                parse_mode="HTML",
            )
            return msg.message_id
        elif media_type == "VIDEO":
            msg = await self.bot.send_video(
                chat_id=dest_channel,
                video=FSInputFile(media_ref),
                caption=caption_trunc,
                parse_mode="HTML",
            )
            return msg.message_id
        else:
            msg = await self.bot.send_message(
                chat_id=dest_channel,
                text=text[:4096],
                parse_mode="HTML",
            )
            return msg.message_id
