import sys
import asyncio

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from aiogram import Bot
from app.config import settings
from app.database.session import get_db
from app.database.models import ContentItem
from app.publisher.telegram_publisher import TelegramPublisher


async def test_post():
    bot = Bot(token=settings.BOT_TOKEN)
    pub = TelegramPublisher(bot=bot)
    async with get_db() as session:
        ci = ContentItem(
            source_post_id=1,
            headline="Umra Ziyoratining Fazilatlari",
            body=(
                "Rasululloh sollallohu alayhi vasallam marhamat qildilar: "
                "«Umra keyingi Umragacha bo'lgan gunohlarga kafforatdir. "
                "Qabul bo'lgan hajning mukofoti esa faqat jannatdir» (Imom Buxoriy rivoyati).\n\n"
                "Alloh taolo barchamizga Baytulloh ziyoratini nasib aylasin!"
            ),
            topic="Umrah",
            quality_score=10,
            factual_risk="NONE",
            rights_status="VERIFIED",
            publish_decision="AUTO_PUBLISH",
            status="QUEUED",
        )
        session.add(ci)
        await session.commit()
        await session.refresh(ci)

        ok = await pub.publish_content_item(session, ci.id)
        print("Published clean post result:", ok)
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(test_post())
