"""Daily performance reports compiled for administrators (TZ Section 13)."""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import pytz
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot
from app.config import settings
from app.logging_config import logger
from app.database.models import (
    SourcePost,
    ContentItem,
    PublishQueue,
    PublishedPost,
    SystemLog,
    SystemState,
)


async def compile_daily_report(session: AsyncSession, hours_back: int = 24) -> str:
    """Compile formatted metrics summary for the last 24 hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    # 1. Manbalardan topilgan postlar
    stmt_found = select(func.count(SourcePost.id)).where(SourcePost.received_at >= since)
    found_count = (await session.execute(stmt_found)).scalar_one()

    # 2. Mavzuga mos deb topilganlar
    stmt_relevant = select(func.count(ContentItem.id)).where(
        and_(
            ContentItem.created_at >= since,
            ContentItem.topic != "Boshqa",
        )
    )
    relevant_count = (await session.execute(stmt_relevant)).scalar_one()

    # 3. AI qayta ishlaganlar
    stmt_ai = select(func.count(ContentItem.id)).where(ContentItem.created_at >= since)
    ai_count = (await session.execute(stmt_ai)).scalar_one()

    # 4. Huquq yoki sifat sabab rad etilganlar
    stmt_rejected = select(func.count(ContentItem.id)).where(
        and_(
            ContentItem.created_at >= since,
            ContentItem.publish_decision == "REJECT",
        )
    )
    rejected_count = (await session.execute(stmt_rejected)).scalar_one()

    # 5. Takroriy postlar
    stmt_dup = select(func.count(SystemLog.id)).where(
        and_(
            SystemLog.created_at >= since,
            SystemLog.event_type.in_(["DUPLICATE_BLOCKED", "INGEST_SKIPPED"]),
        )
    )
    duplicate_count = (await session.execute(stmt_dup)).scalar_one()

    # 6. Muvaffaqiyatli nashrlar (faqat haqiqiy muvaffaqiyatlar!)
    stmt_pub = select(func.count(PublishedPost.id)).where(PublishedPost.published_at >= since)
    published_count = (await session.execute(stmt_pub)).scalar_one()

    # 7. Nashr xatolari
    stmt_err = select(func.count(SystemLog.id)).where(
        and_(
            SystemLog.created_at >= since,
            SystemLog.severity.in_(["ERROR", "CRITICAL"]),
        )
    )
    errors_count = (await session.execute(stmt_err)).scalar_one()

    # 8. Navbatda qolgan materiallar
    stmt_queue = select(func.count(PublishQueue.id)).where(PublishQueue.status == "PENDING")
    queue_pending_count = (await session.execute(stmt_queue)).scalar_one()

    # Pause flag
    pause_state = await session.get(SystemState, "is_paused")
    is_paused = (pause_state.value.lower() == "true") if pause_state else False
    status_str = "⏸ To'xtatilgan (PAUSED)" if is_paused else "🟢 Faol (ACTIVE)"

    now_tz = datetime.now(pytz.timezone(settings.TIMEZONE)).strftime("%Y-%m-%d %H:%M")

    report_text = (
        f"📊 <b>KUNLIK HISOBOT — MUHTASHAM TRAVEL AI AGENT</b>\n"
        f"🕒 <i>Vaqt: {now_tz} (Toshkent vaqti)</i>\n"
        f"⏱ <i>Davr: Oxirgi {hours_back} soat</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 <b>Topilgan postlar:</b> {found_count} ta\n"
        f"🎯 <b>Mavzuga mos:</b> {relevant_count} ta\n"
        f"🧠 <b>AI tahlil qilgan:</b> {ai_count} ta\n"
        f"⛔ <b>Rad etilganlar (sifat/huquq):</b> {rejected_count} ta\n"
        f"🛡 <b>Takroriy postlar:</b> {duplicate_count} ta\n"
        f"🚀 <b>Muvaffaqiyatli nashrlar:</b> {published_count} ta\n"
        f"⚠️ <b>Nashr xatolari:</b> {errors_count} ta\n"
        f"⏳ <b>Navbatdagi materiallar:</b> {queue_pending_count} ta\n"
        f"⚙️ <b>Tizim holati:</b> {status_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Kanal: {settings.TARGET_CHANNEL}</i>"
    )
    return report_text


async def send_daily_report_to_admins(bot: Bot, session: AsyncSession) -> bool:
    """Send compiled daily report to all configured administrators."""
    try:
        report_text = await compile_daily_report(session)
        for admin_id in settings.admin_ids_list:
            try:
                await bot.send_message(chat_id=admin_id, text=report_text, parse_mode="HTML")
                logger.info(f"Kunlik hisobot admin {admin_id} ga yuborildi.")
            except Exception as e:
                logger.warning(f"Admin {admin_id} ga hisobot yuborishda xatolik: {e}")
        return True
    except Exception as e:
        logger.error(f"Kunlik hisobot tayyorlashda xatolik: {e}")
        return False
