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
        formatted_text = f"🕋 <b>{content_item.headline}</b>\n\n{content_item.body}"

        # Resolve media if any from source_post
        source_post = content_item.source_post
        media_ref = source_post.media_reference if source_post else None
        media_type = source_post.media_type if source_post else "TEXT"

        success = False
        telegram_msg_id = None
        error_msg = None

        try:
            if not self.bot:
                logger.info(f"[DRY-RUN / MOCK] Publishing ContentItem #{content_item_id} to {self.target_channel}")
                telegram_msg_id = 99990000 + content_item_id
                success = True
            else:
                telegram_msg_id = await self._send_telegram(formatted_text, media_type, media_ref)
                success = True

        except TelegramRetryAfter as retry_err:
            logger.warning(f"Telegram FloodWait while publishing #{content_item_id}: waiting {retry_err.retry_after}s")
            await asyncio.sleep(retry_err.retry_after)
            try:
                telegram_msg_id = await self._send_telegram(formatted_text, media_type, media_ref)
                success = True
            except Exception as e:
                error_msg = str(e)
                success = False

        except TelegramNetworkError as net_err:
            logger.error(f"Network timeout while publishing #{content_item_id}: {net_err}")
            error_msg = f"Network timeout: {net_err}"
            success = False

        except TelegramAPIError as api_err:
            logger.error(f"Telegram API error while publishing #{content_item_id}: {api_err}")
            error_msg = str(api_err)
            success = False

        except Exception as e:
            logger.error(f"Unexpected error publishing #{content_item_id}: {e}")
            error_msg = str(e)
            success = False

        # Atomic finalize
        if success and telegram_msg_id:
            content_item.status = "PUBLISHED"
            content_hash = source_post.content_hash if source_post else str(content_item_id)
            published_record = PublishedPost(
                content_item_id=content_item.id,
                target_channel=self.target_channel,
                telegram_message_id=telegram_msg_id,
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
                message=f"Post #{content_item.id} kanalga joylandi (Msg ID: {telegram_msg_id})",
            )
            session.add(log)
            await session.commit()
            logger.info(f"Post #{content_item.id} muvaffaqiyatli kanalga joylandi (Msg ID: {telegram_msg_id})")
            return True
        else:
            content_item.status = "FAILED"
            log = SystemLog(
                event_type="PUBLISH_FAILED",
                severity="ERROR",
                message=f"Post #{content_item.id} nashri muvaffaqiyatsiz bo'ldi: {error_msg}",
            )
            session.add(log)
            await session.commit()
            return False

    async def _send_telegram(self, text: str, media_type: str, media_ref: Optional[str]) -> int:
        """Send message, photo, or video to Telegram target channel."""
        has_local_file = media_ref and os.path.exists(media_ref)

        if not has_local_file or media_type == "TEXT":
            msg = await self.bot.send_message(
                chat_id=self.target_channel,
                text=text[:4096],
                parse_mode="HTML",
                disable_web_page_preview=False,
            )
            return msg.message_id

        caption_trunc = text[:1024]
        if media_type == "PHOTO":
            msg = await self.bot.send_photo(
                chat_id=self.target_channel,
                photo=FSInputFile(media_ref),
                caption=caption_trunc,
                parse_mode="HTML",
            )
            return msg.message_id
        elif media_type == "VIDEO":
            msg = await self.bot.send_video(
                chat_id=self.target_channel,
                video=FSInputFile(media_ref),
                caption=caption_trunc,
                parse_mode="HTML",
            )
            return msg.message_id
        else:
            msg = await self.bot.send_message(
                chat_id=self.target_channel,
                text=text[:4096],
                parse_mode="HTML",
            )
            return msg.message_id
