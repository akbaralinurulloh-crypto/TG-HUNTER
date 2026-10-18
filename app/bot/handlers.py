"""Telegram Bot command handlers strictly matching TZ Section 12."""
from datetime import datetime, timezone
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, func, and_
from app.config import settings
from app.logging_config import logger
from app.database.session import get_db
from app.database.models import (
    Source,
    SourcePost,
    ContentItem,
    PublishQueue,
    PublishedPost,
    SystemLog,
    SystemState,
)
from app.bot.middlewares import IsAdminFilter
from app.bot.keyboards import get_admin_main_menu
from app.scheduler.daily_report import compile_daily_report

router = Router()


# ------------------------------------------------------------------------------
# Unauthorized Access Guard
# ------------------------------------------------------------------------------
@router.message(~IsAdminFilter())
async def handle_unauthorized(message: Message):
    user_id = message.from_user.id if message.from_user else "Unknown"
    username = message.from_user.username if message.from_user else ""
    logger.warning(f"Ruxsatsiz kirishga urinish: User ID {user_id} (@{username})")
    async with get_db() as session:
        log = SystemLog(
            event_type="UNAUTHORIZED_ACCESS",
            severity="WARNING",
            message=f"Ruxsatsiz foydalanuvchi buyruq yubordi: ID {user_id} (@{username})",
        )
        session.add(log)
    await message.reply("⛔ <b>Kechirasiz, siz ushbu tizimni boshqarish huquqiga ega emassiz.</b>", parse_mode="HTML")


# ------------------------------------------------------------------------------
# Admin Commands (TZ Section 12)
# ------------------------------------------------------------------------------
@router.message(Command("start"), IsAdminFilter())
async def cmd_start(message: Message):
    text = (
        "🕋 <b>Muhtasham Travel — Telegram Umrah Content Agent</b>\n\n"
        "Agent faol. Umrah va ziyorat kanallari monitoring qilinmoqda va sifatli kontent "
        "avtomatik tarzda maqsadli kanalga taqsimlanadi.\n\n"
        "<b>Boshqaruv buyruqlari:</b>\n"
        "/status — Tizim holati va oxirgi nashr vaqti\n"
        "/stats — Kunlik to'liq statistika\n"
        "/queue — Rejalashtirilgan postlar navbati\n"
        "/sources — Faol manbalar va huquqlar holati\n"
        "/pause — Yangi nashrlarni vaqtincha to'xtatish\n"
        "/resume — Avtomatik nashrni qayta yoqish\n"
        "/errors — Oxirgi muhim xatoliklar\n"
        "/help — Buyruqlar bo'yicha yordam"
    )
    await message.reply(text, parse_mode="HTML", reply_markup=get_admin_main_menu())


@router.message(Command("status"), IsAdminFilter())
async def cmd_status(message: Message):
    async with get_db() as session:
        # Pause flag
        pause_state = await session.get(SystemState, "is_paused")
        is_paused = (pause_state.value.lower() == "true") if pause_state else False

        # Queue count
        queue_count = (
            await session.execute(
                select(func.count(PublishQueue.id)).where(PublishQueue.status == "PENDING")
            )
        ).scalar_one()

        # Last published post
        last_pub_stmt = (
            select(PublishedPost)
            .order_by(PublishedPost.published_at.desc())
            .limit(1)
        )
        last_pub = (await session.execute(last_pub_stmt)).scalars().first()
        last_pub_time = last_pub.published_at.strftime("%Y-%m-%d %H:%M UTC") if last_pub else "Hali nashr qilinmagan"

        status_text = (
            "⚙️ <b>AGENT JORIY HOLATI:</b>\n\n"
            f"🟢 <b>Faollik:</b> {'⏸ TO\'XTATILGAN (PAUSED)' if is_paused else '🟢 FAOLLAR (ACTIVE 24/7)'}\n"
            f"⏳ <b>Navbatdagi postlar:</b> {queue_count} ta\n"
            f"🕒 <b>Oxirgi muvaffaqiyatli nashr:</b> {last_pub_time}\n"
            f"🎯 <b>Maqsadli kanal:</b> {settings.TARGET_CHANNEL}\n"
            f"📅 <b>Vaqt mintaqasi:</b> {settings.TIMEZONE}\n"
        )
        await message.reply(status_text, parse_mode="HTML")


@router.message(Command("sources"), IsAdminFilter())
async def cmd_sources(message: Message):
    async with get_db() as session:
        sources = (await session.execute(select(Source).order_by(Source.id.asc()))).scalars().all()
        if not sources:
            await message.reply("ℹ️ Bazada hozircha manbalar mavjud emas.", parse_mode="HTML")
            return

        text = "📡 <b>KUZATILAYOTGAN MANBALAR VA HUQUQLAR:</b>\n\n"
        for s in sources:
            status_icon = "🟢" if s.active else "🔴"
            rights_badge = "✅ Huquq tasdiqlangan" if s.rights_status == "VERIFIED" else f"⚠️ {s.rights_status}"
            text += (
                f"{status_icon} <b>{s.title}</b> (@{s.telegram_identifier})\n"
                f"   • Holati: {'Faol' if s.active else 'Nofaol'}\n"
                f"   • Foydalanish huquqi: {rights_badge}\n"
                f"   • Eslatma: {s.rights_notes or 'Kiritilmagan'}\n\n"
            )
        await message.reply(text, parse_mode="HTML")


@router.message(Command("stats"), IsAdminFilter())
async def cmd_stats(message: Message):
    async with get_db() as session:
        report_text = await compile_daily_report(session, hours_back=24)
        await message.reply(report_text, parse_mode="HTML")


@router.message(Command("pause"), IsAdminFilter())
async def cmd_pause(message: Message):
    async with get_db() as session:
        state = await session.get(SystemState, "is_paused")
        if not state:
            state = SystemState(key="is_paused", value="true")
            session.add(state)
        else:
            state.value = "true"
        log = SystemLog(
            event_type="SYSTEM_PAUSED",
            severity="WARNING",
            message=f"Admin {message.from_user.id} avtomatik nashrni to'xtatdi.",
        )
        session.add(log)
        await session.commit()
    await message.reply("⏸ <b>Yangi avtomatik nashrlar vaqtincha to'xtatildi!</b>\nMavjud ma'lumotlar saqlanadi.", parse_mode="HTML")


@router.message(Command("resume"), IsAdminFilter())
async def cmd_resume(message: Message):
    async with get_db() as session:
        state = await session.get(SystemState, "is_paused")
        if not state:
            state = SystemState(key="is_paused", value="false")
            session.add(state)
        else:
            state.value = "false"
        log = SystemLog(
            event_type="SYSTEM_RESUMED",
            severity="INFO",
            message=f"Admin {message.from_user.id} avtomatik nashrni qayta yoqdi.",
        )
        session.add(log)
        await session.commit()
    await message.reply("▶️ <b>Avtomatik nashr qayta yoqildi!</b>", parse_mode="HTML")


@router.message(Command("queue"), IsAdminFilter())
async def cmd_queue(message: Message):
    async with get_db() as session:
        stmt = (
            select(PublishQueue)
            .where(PublishQueue.status == "PENDING")
            .order_by(PublishQueue.scheduled_at.asc())
            .limit(10)
        )
        items = (await session.execute(stmt)).scalars().all()
        if not items:
            await message.reply("✅ Hozirda navbatda kutilayotgan postlar yo'q.", parse_mode="HTML")
            return

        text = f"⏳ <b>NAVBATDAGI POSTLAR ({len(items)} ta ko'rsatilmoqda):</b>\n\n"
        for q in items:
            ci = q.content_item
            headline = ci.headline if ci else f"Post #{q.content_item_id}"
            time_str = q.scheduled_at.strftime("%H:%M (%d-%b)")
            text += f"• <b>{time_str}</b>: {headline[:60]}...\n"
        await message.reply(text, parse_mode="HTML")


@router.message(Command("errors"), IsAdminFilter())
async def cmd_errors(message: Message):
    async with get_db() as session:
        stmt = (
            select(SystemLog)
            .where(SystemLog.severity.in_(["ERROR", "CRITICAL", "WARNING"]))
            .order_by(SystemLog.created_at.desc())
            .limit(7)
        )
        logs = (await session.execute(stmt)).scalars().all()
        if not logs:
            await message.reply("✅ Tizimda yaqin orada jiddiy xatoliklar qayd etilmagan.", parse_mode="HTML")
            return

        text = "⚠️ <b>OXIRGI MUHIM LOGLAR VA XATOLIKLAR:</b>\n\n"
        for l in logs:
            t = l.created_at.strftime("%H:%M:%S")
            text += f"[{l.severity}] <b>{t}</b> — {l.event_type}\n<i>{l.message[:120]}</i>\n\n"
        await message.reply(text, parse_mode="HTML")


@router.message(Command("help"), IsAdminFilter())
async def cmd_help(message: Message):
    help_text = (
        "📖 <b>MUHTASHAM AGENT BUYRUQLARI BO'YICHA QO'LLANMA:</b>\n\n"
        "• /status — Agent holati, oxirgi nashr vaqti va navbat soni.\n"
        "• /stats — Oxirgi 24 soatlik monitoring, AI va nashr ko'rsatkichlari.\n"
        "• /sources — Ruxsat etilgan va kuzatilayotgan barcha manbalar ro'yxati.\n"
        "• /queue — Rejalashtirilgan postlarning yaqin vaqtlar bo'yicha jadvali.\n"
        "• /pause — Nashr qilishni zudlik bilan to'xtatish (kuzatuv davom etadi).\n"
        "• /resume — Avtomatik nashrni qayta davom ettirish.\n"
        "• /errors — Tizim jurnallaridagi oxirgi xatoliklarni ko'rish.\n"
        "• /help — Ushbu yordam oynasini ochish."
    )
    await message.reply(help_text, parse_mode="HTML")
