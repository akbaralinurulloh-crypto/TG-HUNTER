"""Main application entrypoint for Telegram Umrah Content Agent."""
import sys
import asyncio
import signal
from datetime import datetime
from aiogram import Bot
from app.config import settings
from app.logging_config import logger, setup_logging
from app.database.session import init_database, get_db, engine
from app.database.models import SystemState
from app.sources.manager import SourceManager
from app.bot import setup_dispatcher
from app.publisher.channel_tester import run_channel_diagnostic
from app.scheduler.queue_manager import QueueScheduler
from app.scheduler.daily_report import send_daily_report_to_admins


class UmrahContentAgent:
    """Coordinates Telegram Bot, Queue Scheduler, and Database operations."""

    def __init__(self):
        self.bot: Bot = None
        self.dp = None
        self.is_running = True
        self.scheduler: QueueScheduler = None

    async def start(self):
        setup_logging(settings.LOG_LEVEL)
        logger.info("================================================================")
        logger.info("   TELEGRAM UMRAH CONTENT AGENT (Muhtasham Travel) v2.0         ")
        logger.info("================================================================")

        # 1. Initialize Database & Seed
        try:
            await init_database()
            async with get_db() as session:
                source_mgr = SourceManager(session)
                await source_mgr.seed_initial_sources()
                # Ensure is_paused flag exists
                pause_state = await session.get(SystemState, "is_paused")
                if not pause_state:
                    session.add(SystemState(key="is_paused", value="false"))
                await session.commit()
            logger.info("Database initialized and verified.")
        except Exception as e:
            logger.critical(f"Database initialization error: {e}")
            sys.exit(1)

        # 2. Check Bot & Channel Configuration
        missing = settings.validate_required_settings()
        if missing:
            logger.warning(f"Diqqat: Quyidagi majburiy sozlamalar yo'q: {', '.join(missing)}")
            logger.warning(".env faylida ushbu parametrlarni to'ldiring. Bot mock rejimida ishlaydi.")
            self.bot = None
        else:
            self.bot = Bot(token=settings.BOT_TOKEN)
            self.dp = setup_dispatcher()
            self.scheduler = QueueScheduler(bot=self.bot)

            # Run Channel Diagnostic (TZ Section 17)
            logger.info("Running channel connectivity diagnostic...")
            await run_channel_diagnostic(self.bot)

        # 3. Start Background Loops
        tasks = []
        if self.bot and self.dp:
            tasks.append(asyncio.create_task(self.dp.start_polling(self.bot)))
            tasks.append(asyncio.create_task(self._queue_worker_loop()))
            tasks.append(asyncio.create_task(self._daily_report_loop()))
            logger.info(f"Bot and Scheduler active. Target channel: {settings.TARGET_CHANNEL}")

        try:
            if tasks:
                await asyncio.gather(*tasks)
            else:
                while self.is_running:
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Application loop cancellation received.")
        finally:
            await self.shutdown()

    async def _queue_worker_loop(self):
        """Periodically inspect publish_queue and publish due posts."""
        logger.info("Queue processor loop started (interval: 30s).")
        while self.is_running:
            try:
                async with get_db() as session:
                    published = await self.scheduler.process_due_items(session)
                    if published > 0:
                        logger.info(f"Navbatdagi {published} ta post muvaffaqiyatli kanalga joylandi.")
            except Exception as e:
                logger.error(f"Queue worker loop error: {e}")
            await asyncio.sleep(30)

    async def _daily_report_loop(self):
        """Send daily reports at configured hours (e.g. 08:00, 13:00, 20:00 Tashkent time)."""
        logger.info(f"Daily report loop started. Report hours: {settings.report_hours_list}")
        last_sent_hour = -1
        import pytz
        tz = pytz.timezone(settings.TIMEZONE)

        while self.is_running:
            try:
                now_tz = datetime.now(tz)
                current_hour = now_tz.hour
                current_minute = now_tz.minute

                if current_hour in settings.report_hours_list and current_hour != last_sent_hour and current_minute == 0:
                    async with get_db() as session:
                        await send_daily_report_to_admins(self.bot, session)
                    last_sent_hour = current_hour
                elif current_hour not in settings.report_hours_list:
                    last_sent_hour = -1
            except Exception as e:
                logger.error(f"Daily report loop error: {e}")
            await asyncio.sleep(45)

    async def shutdown(self):
        logger.info("Shutting down Umrah Content Agent gracefully...")
        self.is_running = False
        if self.bot:
            await self.bot.session.close()
        await engine.dispose()
        logger.info("Shutdown complete.")


async def main():
    agent = UmrahContentAgent()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(agent.shutdown()))
        except NotImplementedError:
            pass
    await agent.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Agent process terminated.")
