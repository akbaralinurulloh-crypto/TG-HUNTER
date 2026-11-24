"""Admin bot: faqat ADMIN_ID buyruq bera oladi. Mantiq `handle_command` va `handle_message` da."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Awaitable, Callable

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from app.db.repository import Repository
from app.llm.base import LLMClient
from app.utils.logging import get_logger
from app.utils.text import split_message

log = get_logger("admin")

PAUSED, DRYRUN = "paused", "dry_run"


@dataclass
class AdminContext:
    repo: Repository
    sources: list[str]
    target: str
    status_fn: "callable"  # async () -> str
    report_fn: Callable[[], Awaitable[str]] | None = None  # async () -> hisobot matni
    sources_fn: Callable[[], list[str]] | None = None  # manbalar tavsifi (tur bilan)
    llm: LLMClient | None = None
    publish_fn: Callable[[int], Awaitable[str]] | None = None  # async (unit_id) -> natija matni
    recheck_fn: Callable[[], Awaitable[str]] | None = None  # async () -> qayta tekshirish natijasi


async def is_paused(repo: Repository) -> bool:
    return (await repo.get_kv(PAUSED, "0")) == "1"


async def is_dry_run(repo: Repository, default: bool = True) -> bool:
    v = await repo.get_kv(DRYRUN)
    return default if v is None else v == "1"


async def handle_command(cmd: str, args: list[str], ctx: AdminContext) -> str:
    cmd = cmd.lstrip("/").split("@")[0].lower()
    if cmd in ("start", "help"):
        return "Buyruqlar: /status, /report, /recheck, /pause, /resume, /dryrun on|off, /sources, /last [N]"
    if cmd in ("recheck", "retry", "poll"):
        if ctx.recheck_fn:
            return await ctx.recheck_fn()
        return "Qayta tekshirish xizmati ulanmagan."
    if cmd == "status":
        return await ctx.status_fn()
    if cmd == "report":
        if ctx.report_fn is None:
            return "Hisobot xizmati ulanmagan."
        return await ctx.report_fn()
    if cmd == "pause":
        await ctx.repo.set_kv(PAUSED, "1")
        await ctx.repo.audit("admin_pause")
        return "⏸ Pauza: yangi xabarlar qayta ishlanmaydi (o'qish davom etadi)."
    if cmd == "resume":
        await ctx.repo.set_kv(PAUSED, "0")
        await ctx.repo.set_kv("consecutive_errors", "0")
        await ctx.repo.audit("admin_resume")
        return "▶️ Davom etdi."
    if cmd == "dryrun":
        if not args or args[0].lower() not in ("on", "off"):
            return f"Hozir DRY-RUN: {'yoqiq' if await is_dry_run(ctx.repo) else 'o`chiq (JONLI)'}.\nFoydalanish: /dryrun on|off"
        on = args[0].lower() == "on"
        await ctx.repo.set_kv(DRYRUN, "1" if on else "0")
        await ctx.repo.audit("admin_dryrun", on=on)
        return "🧪 DRY-RUN yoqildi: kanalga joylanmaydi, faqat sizga ko'rsatiladi." if on else f"🔴 JONLI rejim: postlar {ctx.target} ga joylanadi."
    if cmd == "sources":
        lines = ctx.sources_fn() if ctx.sources_fn else [f"• {s}" for s in ctx.sources]
        return "Manbalar:\n" + "\n".join(lines) + f"\nMaqsad: {ctx.target}"
    if cmd == "last":
        n = int(args[0]) if args and args[0].isdigit() else 10
        rows = await ctx.repo.last_units(max(1, min(n, 30)))
        if not rows:
            return "Hali xabar yo'q."
        return "\n".join(
            f"#{u.id} {u.state}{'/' + u.decision_reason if u.decision_reason else ''}"
            f"{f' ball={u.score:.1f}' if u.score is not None else ''} — {u.channel_title}: {(u.text or '(media)')[:40]!r}"
            for u in rows
        )
    return "Noma'lum buyruq. /help"


async def handle_message(text: str, ctx: AdminContext, reply_to_text: str | None = None) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""

    if raw.startswith("/"):
        parts = raw.split()
        return await handle_command(parts[0], parts[1:], ctx)

    low = raw.lower()
    # Kirish so'zlarini (hop, iltimos, menga, qani, endi va h.k.) olib tashlash
    cleaned = re.sub(r"^(?:hop|xo['’`]?p|iltimos|menga|qani|endi|bot|shuni|bir)\s+", "", low).strip()

    # 0.0 Qayta tekshirish: "ishlamagan paytidagi xabarlar", "eskilarini tekshir", "qayta tekshir", "xatolarni tekshir"
    if re.search(r"\b(?:qayta|eskilar(?:ini)?|ishlamagan|oldin(?:gi)?|xatolar(?:ni)?)\s*(?:tekshir|ishla|qarab\s*chiq|qo['’`]?y|qoy|tashla)\b|\b(?:recheck|retry|poll)\b", cleaned):
        return await handle_command("recheck", [], ctx)

    # 0. Kanalga qo'lda joylash buyrug'i: "mana shuni qoy kanalga", "shuni joyla", "hozirgi postni joyla", "/post", "/publish"
    if re.search(r"\b(?:joyla|joylash|kanalga\s*(?:qo['’`]?y|joyla)|mana\s*shuni\s*(?:qo['’`]?y|joyla)|shuni\s*joyla|postni\s*joyla)\b|^/publish|^/post", cleaned):
        target_unit_id = None
        num_match = re.search(r"#?(\d+)", cleaned)
        if num_match and int(num_match.group(1)) > 0:
            target_unit_id = int(num_match.group(1))

        if not target_unit_id and reply_to_text:
            reply_match = re.search(r"#(\d+)", reply_to_text)
            if reply_match:
                target_unit_id = int(reply_match.group(1))

        if not target_unit_id:
            units = await ctx.repo.last_units(10)
            for u in units:
                if u.state in ("dryrun", "received", "manual_review"):
                    target_unit_id = u.id
                    break
            if not target_unit_id and units:
                target_unit_id = units[0].id

        if target_unit_id and ctx.publish_fn:
            return await ctx.publish_fn(target_unit_id)
        return "Qaysi postni joylash kerakligini aniqlay olmadim. Masalan: '/post 10' deb yozing yoki postga reply qilib 'joyla' deng."

    # Tabiiy tildagi tezkor buyruqlar
    # 1. Dry run yoqish (on)
    if re.search(r"\b(?:dry\s*run(?:ni)?|sinov\s*rejimini?|test\s*rejimini?)\s*(?:yoq|yoqish|on|boshla|qil)\b|\b(?:dry\s*run\s*on|sinov\s*rejimi)\b", cleaned):
        return await handle_command("dryrun", ["on"], ctx)

    # 2. Dry run o'chirish / Jonli rejim (off)
    if re.search(r"\b(?:dry\s*run(?:ni)?|sinov\s*rejimini?|test\s*rejimini?)\s*(?:o['’`]?chir|ochir|off|to['’`]?xtat)\b|\b(?:jonli\s*rejim(?:ga|ni)?)\s*(?:o['’`]?t|yoq|boshla|qil)\b|\b(?:dry\s*run\s*off|jonli\s*rejim)\b", cleaned):
        return await handle_command("dryrun", ["off"], ctx)

    # 3. Davom ettirish / Pauzani o'chirish (pauza so'zidan OLDIN tekshiriladi!)
    if re.search(
        r"\b(?:pauza(?:ni)?\s*(?:o['’`]?chir(?:ilsin)?|ochir(?:ilsin)?|bekor\s*qil|yech|olib\s*tashla)|davom\s*et(?:tir)?|ishla(?:yver)?|boshla|davom)\b",
        cleaned,
    ):
        return await handle_command("resume", [], ctx)

    # 4. Pauza (savollar bundan mustasno: 'nimaga/nega pauza')
    if not re.search(r"\b(?:nimaga|nega|nima\s*uchun|qanaqa)\b", cleaned) and re.search(
        r"\b(?:pauza(?:ga)?(?:\s*qo['’`]?y)?|to['’`]?xtat(?:ib\s*tur)?|botni\s*to['’`]?xtat|toxtat)\b",
        cleaned,
    ):
        return await handle_command("pause", [], ctx)

    # 5. Holat / Status
    if re.search(r"\b(?:holat|status|ahvol|qalay|qanday|nima\s*gap)\b", cleaned):
        return await handle_command("status", [], ctx)

    # 6. Hisobot
    if re.search(r"\b(?:hisobot|bugungi\s*hisobot|report)\b", cleaned):
        return await handle_command("report", [], ctx)

    # 7. Oxirgi postlar
    if re.search(r"\b(?:oxirgi\s*(?:postlar|xabarlar|post)|last)\b", cleaned):
        m = re.search(r"\d+", cleaned)
        return await handle_command("last", [m.group()] if m else ["10"], ctx)

    # 8. Manbalar
    if re.search(r"\b(?:manbalar|kanallar|qaysi\s*kanallar|sources)\b", cleaned):
        return await handle_command("sources", [], ctx)

    # 9. AI suhbat (savollarga do'stona javob berish)
    if ctx.llm and hasattr(ctx.llm, "generate_text"):
        try:
            recent_units = await ctx.repo.last_units(5)
            recent_summary = "\n".join(
                f"- Post #{u.id}: {u.channel_title} | Holat: {u.state}{'/' + u.decision_reason if u.decision_reason else ''}"
                f"{f' | Ball: {u.score:.1f}' if u.score is not None else ''}\n  Matn: {(u.text or '')[:120].strip()}"
                for u in recent_units
            ) or "Hozircha postlar yo'q."

            unit_match = re.search(r"#?(\d+)\s*(?:-|chi)?\s*post", low)
            unit_detail = ""
            if unit_match:
                uid = int(unit_match.group(1))
                unit = await ctx.repo.get_unit(uid)
                if unit:
                    unit_detail = (
                        f"\nSo'ralgan post batafsil ma'lumoti:\nID: #{unit.id}\nManba: {unit.channel_title}\n"
                        f"Holat: {unit.state} (Sabab: {unit.decision_reason})\nBall: {unit.score}\n"
                        f"Asl matn: {unit.text}\nIzoh: {unit.caption}\nTafsilot: {unit.decision_detail}"
                    )

            reply_context = f'\nAdmin quyidagi xabarga javob (reply) berdi:\n"{reply_to_text}"' if reply_to_text else ""

            system_prompt = f"""# ROLE: TG_HUNTER_ASSISTANT
Siz TG Hunter Telegram botining shaxsiy aqlli yordamchisisiz.
Admin sizga savol bermoqda. Unga faqat samimiy, aniq va do'stona o'zbek tilida javob bering (1-3 gap).

Tizim ma'lumotlari:
- Maqsadli kanal: {ctx.target}
- Manba kanallar: {', '.join(ctx.sources)}
- So'nggi 5 ta post holati:
{recent_summary}
{unit_detail}
{reply_context}

Vazifangiz:
- Adminning postlar, ularning holati, sabablari (reklama, telefon shubhasi, ball pastligi) yoki tizim bo'yicha savollariga aniq tushuntirish berish.
- Agar admin buyruq bergisi kelsa, nima qilish kerakligini muloyim aytib bering.
"""
            resp = await ctx.llm.generate_text(system=system_prompt, user=raw)
            if resp:
                return resp
        except Exception as exc:
            log.exception("conversational_llm_failed")
            err_str = str(exc).lower()
            if "429" in err_str or "quota" in err_str:
                return (
                    "⚠️ Gemini AI bepul so'rovlar limiti (kvotasi) vaqtincha to'ldi. Odatda 1-2 daqiqada yangilanadi.\n\n"
                    "Lekin botning barcha asosiy buyruqlari (status, hisobot, dry-run, to'xtatish) odatdagidek ishlayveradi!"
                )
            return f"Savolingizni tushundim, lekin javob tayyorlashda xatolik yuz berdi: {exc}"

    return "Buyruqlar: /status, /report, /pause, /resume, /dryrun on|off, /sources, /last [N]\nYoki oddiy yozing: 'holat qanday', 'dry runni yoq', 'to'xtat', 'hisobot'."


def build_dispatcher(admin_id: int, ctx: AdminContext) -> Dispatcher:
    dp = Dispatcher()
    only_admin = F.from_user.id == admin_id

    @dp.message(only_admin)
    async def _admin_message(message: Message):
        text = message.text or message.caption or ""
        if not text:
            return
        reply_text = None
        if message.reply_to_message:
            reply_text = message.reply_to_message.text or message.reply_to_message.caption
        answer = await handle_message(text, ctx, reply_to_text=reply_text)
        if answer:
            for part in split_message(answer):
                await message.answer(part)

    @dp.message()
    async def _other(message: Message):
        if message.from_user and message.from_user.id != admin_id:
            log.warning("unauthorized_message", user_id=message.from_user.id)

    return dp
