import pytest

from app.bot_admin import AdminContext, handle_command, handle_message, is_dry_run, is_paused
from app.db.repository import NormalizedUnit
from datetime import datetime, timezone


@pytest.fixture
def ctx(repo):
    async def status():
        return "status-ok"

    return AdminContext(repo, ["@a", "@b"], "@target", status)


async def test_pause_resume(ctx):
    assert not await is_paused(ctx.repo)
    assert "Pauza" in await handle_command("/pause", [], ctx)
    assert await is_paused(ctx.repo)
    await ctx.repo.set_kv("consecutive_errors", "4")
    await handle_command("/resume", [], ctx)
    assert not await is_paused(ctx.repo) and await ctx.repo.get_kv("consecutive_errors") == "0"


async def test_dryrun_defaults_on_and_toggles(ctx):
    assert await is_dry_run(ctx.repo, default=True)
    out = await handle_command("/dryrun", ["off"], ctx)
    assert "JONLI" in out and not await is_dry_run(ctx.repo)
    await handle_command("/dryrun", ["on"], ctx)
    assert await is_dry_run(ctx.repo, default=False)
    assert "Foydalanish" in await handle_command("/dryrun", ["maybe"], ctx)


async def test_sources_status_help_unknown(ctx):
    assert "@a" in await handle_command("/sources", [], ctx) and "@target" in await handle_command("/sources", [], ctx)
    assert await handle_command("/status", [], ctx) == "status-ok"
    assert "/pause" in await handle_command("/help", [], ctx)
    assert "Noma'lum" in await handle_command("/xyz", [], ctx)
    assert await handle_command("/status@my_bot", [], ctx) == "status-ok"


async def test_last(ctx):
    assert "yo'q" in await handle_command("/last", ["5"], ctx)
    u, _ = await ctx.repo.add_unit(NormalizedUnit(-1, "Src", [1], None, "Salom dunyo", [], datetime(2026, 1, 1, tzinfo=timezone.utc)))
    await ctx.repo.record_decision(u.id, "rejected", "low_score", score=5.5)
    out = await handle_command("/last", [], ctx)
    assert "rejected/low_score" in out and "ball=5.5" in out


async def test_report_command_returns_report_text(repo):
    async def status():
        return "s"

    async def report():
        return "📊 HISOBOT ..."

    ctx = AdminContext(repo, ["@a"], "@t", status, report_fn=report)
    assert await handle_command("/report", [], ctx) == "📊 HISOBOT ..."
    assert "/report" in await handle_command("/help", [], ctx)
    ctx2 = AdminContext(repo, ["@a"], "@t", status)
    assert "ulanmagan" in await handle_command("/report", [], ctx2)


async def test_sources_command_uses_descriptions_when_available(repo):
    async def status():
        return "s"

    ctx = AdminContext(repo, ["@a"], "@t", status, sources_fn=lambda: ["• Kanal — kanal", "• Guruh — guruh — O'TKAZIB YUBORILADI"])
    out = await handle_command("/sources", [], ctx)
    assert "Kanal — kanal" in out and "O'TKAZIB YUBORILADI" in out and "@t" in out


async def test_natural_language_and_chat(repo):
    from tests.fakes import FakeLLM
    async def status():
        return "status-running"

    llm = FakeLLM()
    ctx = AdminContext(repo, ["@src"], "@t", status, llm=llm)

    # natural commands
    assert "DRY-RUN yoqildi" in await handle_message("dry runni yoq", ctx)
    assert "JONLI rejim" in await handle_message("jonli rejimga o't", ctx)
    assert "Pauza" in await handle_message("to'xtat", ctx)
    assert "Davom etdi" in await handle_message("davom ettir", ctx)
    assert "status-running" in await handle_message("holat qanday?", ctx)
    # filler words prefix like 'hop hisobot ber'
    async def report():
        return "📊 TEST HISOBOT"
    ctx.report_fn = report
    assert "TEST HISOBOT" in await handle_message("hop hisobot ber", ctx)

    # publish command
    async def pub(uid):
        return f"PUBLISHED #{uid}"
    ctx.publish_fn = pub
    assert "PUBLISHED #10" in await handle_message("mana shuni qoy kanalga", ctx, reply_to_text="#10 Madina")
    assert "PUBLISHED #15" in await handle_message("15-postni joyla", ctx)

    # conversational query
    chat_resp = await handle_message("bu post haqida aytib ber", ctx, reply_to_text="Post #1 matni")
    assert "fake-response" in chat_resp
