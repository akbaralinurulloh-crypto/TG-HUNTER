"""Publish queue manager distributing 20-50 posts across the day (TZ Section 11)."""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import pytz
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot
from app.config import settings
from app.logging_config import logger
from app.database.models import ContentItem, PublishQueue, SystemLog, SystemState
from app.publisher.telegram_publisher import TelegramPublisher


class QueueScheduler:
    """Schedules and distributes approved posts evenly across the daytime window (Asia/Tashkent)."""

    def __init__(self, bot: Optional[Bot] = None):
        self.bot = bot
        self.tz = pytz.timezone(settings.TIMEZONE)
        self.publisher = TelegramPublisher(bot=bot)

    async def calculate_next_slot(self, session: AsyncSession) -> datetime:
        """
        Calculate the next even publishing timestamp in Asia/Tashkent timezone.
        Distributes posts between PUBLISH_START_HOUR (07:00) and PUBLISH_END_HOUR (23:00).
        """
        now_tz = datetime.now(self.tz)
        today_start = now_tz.replace(hour=settings.PUBLISH_START_HOUR, minute=0, second=0, microsecond=0)
        today_end = now_tz.replace(hour=settings.PUBLISH_END_HOUR, minute=0, second=0, microsecond=0)

        # Count pending items in queue scheduled for today
        stmt = select(func.count(PublishQueue.id)).where(
            and_(
                PublishQueue.status.in_(["PENDING", "PROCESSING"]),
                PublishQueue.scheduled_at >= today_start,
                PublishQueue.scheduled_at <= today_end,
            )
        )
        existing_count = (await session.execute(stmt)).scalar_one()

        # Slot interval: 16 hours (960 mins) divided by target daily max (e.g. 30-50 posts) -> ~20-30 mins
        window_minutes = (settings.PUBLISH_END_HOUR - settings.PUBLISH_START_HOUR) * 60
        target_posts = max(settings.DAILY_POST_MIN, min(settings.DAILY_POST_MAX, 30))
        interval_minutes = max(15, window_minutes // target_posts)

        # If current time is before window, start at 07:00 + offset
        if now_tz < today_start:
            slot = today_start + timedelta(minutes=existing_count * interval_minutes)
        elif now_tz > today_end:
            # Shift to tomorrow morning
            tomorrow_start = today_start + timedelta(days=1)
            slot = tomorrow_start + timedelta(minutes=existing_count * interval_minutes)
        else:
            # During window: place at least interval_minutes after last scheduled or now
            last_stmt = (
                select(PublishQueue.scheduled_at)
                .where(PublishQueue.status == "PENDING")
                .order_by(PublishQueue.scheduled_at.desc())
                .limit(1)
            )
            last_scheduled = (await session.execute(last_stmt)).scalars().first()
            if last_scheduled:
                if last_scheduled.tzinfo is None:
                    last_scheduled = last_scheduled.replace(tzinfo=timezone.utc).astimezone(self.tz)
                else:
                    last_scheduled = last_scheduled.astimezone(self.tz)

            if last_scheduled and last_scheduled > now_tz:
                slot = last_scheduled + timedelta(minutes=interval_minutes)
            elif existing_count == 0:
                slot = now_tz  # Publish immediately if queue is empty
            else:
                slot = now_tz + timedelta(minutes=interval_minutes)

        return slot.astimezone(timezone.utc)

    async def enqueue_content_item(
        self,
        session: AsyncSession,
        content_item_id: int,
        custom_time: Optional[datetime] = None,
    ) -> PublishQueue:
        """Add an approved ContentItem to the publish_queue."""
        scheduled_at = custom_time or (await self.calculate_next_slot(session))

        queue_item = PublishQueue(
            content_item_id=content_item_id,
            scheduled_at=scheduled_at,
            status="PENDING",
            attempt_count=0,
        )
        session.add(queue_item)

        # Update ContentItem status
        item = await session.get(ContentItem, content_item_id)
        if item:
            item.status = "QUEUED"

        await session.commit()
        logger.info(f"ContentItem #{content_item_id} navbatga qo'yildi: {scheduled_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        return queue_item

    async def process_due_items(self, session: AsyncSession) -> int:
        """
        Check for any pending items whose scheduled_at <= current UTC time and publish them.
        Returns the number of published items.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(PublishQueue)
            .where(
                and_(
                    PublishQueue.status == "PENDING",
                    PublishQueue.scheduled_at <= now,
                )
            )
            .order_by(PublishQueue.scheduled_at.asc())
            .limit(5)
        )
        due_items = (await session.execute(stmt)).scalars().all()

        published_count = 0
        for q in due_items:
            q.status = "PROCESSING"
            q.attempt_count += 1
            await session.commit()

            success = await self.publisher.publish_content_item(session, q.content_item_id)
            if success:
                q.status = "PUBLISHED"
                published_count += 1
            else:
                q.status = "FAILED"
                q.last_error = "Nashr qilishda xatolik yuz berdi"
            await session.commit()

        return published_count
