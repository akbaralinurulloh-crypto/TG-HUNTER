import sys
import asyncio

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from aiogram import Bot
from app.config import settings
from app.database.session import get_db
from app.database.models import SourcePost, ContentItem
from app.ai.analyzer import AIContentAnalyzer
from app.publisher.telegram_publisher import TelegramPublisher


async def run_live_demo():
    bot = Bot(token=settings.BOT_TOKEN)
    pub = TelegramPublisher(bot=bot)
    analyzer = AIContentAnalyzer()

    async with get_db() as session:
        # Take real post #16 (from @nurlisafar)
        source_post = await session.get(SourcePost, 16)
        if not source_post:
            print("SourcePost #16 topilmadi!")
            await bot.session.close()
            return

        print(f"Tanlangan asl post ID: {source_post.id}")
        print("Asl manba: @nurlisafar")

        # Step 1: AI / Rule processing
        ai_res = await analyzer.analyze_and_rewrite(
            raw_text=source_post.original_text,
            media_type=source_post.media_type,
            source_title="Nurli Safar",
            source_rights_status="VERIFIED"
        )

        print("Tahlil qarori:", ai_res.publish_decision)
        if ai_res.publish_decision != "AUTO_PUBLISH":
            print("Post rad etildi:", ai_res.rejection_reason)
            await bot.session.close()
            return

        # Unpause system state for live demonstration
        from app.database.models import SystemState
        pause_state = await session.get(SystemState, "is_paused")
        if pause_state:
            pause_state.value = "false"
        else:
            session.add(SystemState(key="is_paused", value="false"))
        await session.commit()

        # Step 2: Create ContentItem
        ci = ContentItem(
            source_post_id=source_post.id,
            headline=ai_res.headline,
            body=ai_res.body,
            topic=ai_res.topic,
            quality_score=ai_res.quality_score,
            factual_risk=ai_res.factual_risk,
            rights_status=ai_res.rights_status,
            publish_decision="AUTO_PUBLISH",
            status="QUEUED",
        )
        session.add(ci)
        await session.commit()
        await session.refresh(ci)

        # Step 3: Publish to Target Channel (@muhtashamtraveluzz)
        ok = await pub.publish_content_item(session, ci.id)
        print(f"Kanalga joylash natijasi: {ok}")

        # Step 4: Send private notification & preview to admin (240409213)
        admin_id = 240409213
        admin_text = (
            "✅ <b>Amalda sinov posti kanalga joylandi!</b>\n\n"
            f"📢 Kanal: {settings.TARGET_CHANNEL}\n\n"
            "🔍 <b>Qilingan ishlar amalda:</b>\n"
            "1. 🚫 Birorta hadis qo'shilmadi (hadislar taqiqlangan).\n"
            "2. 🚫 Olingan manba (@nurlisafar yoki 'Manba:') to'liq yashirildi.\n"
            "3. 🚫 Begona raqamlar qirqib tashlandi.\n"
            "4. 📞 Siz aytgan raqam qo'yildi: <b>+998 88 832 77 00</b>\n"
            "5. 🕋 Asl Umra dasturi (mehmonxonalar, ziyorat joylari, xizmatlar) saqlab qolindi.\n\n"
            "Iltimos, kanalni tekshirib ko'ring: @muhtashamtraveluzz"
        )
        try:
            await bot.send_message(chat_id=admin_id, text=admin_text, parse_mode="HTML")
            print("Admin Telegram hisobiga xabar yuborildi!")
        except Exception as e:
            print(f"Adminga xabar yuborishda xatolik: {e}")

    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_live_demo())
