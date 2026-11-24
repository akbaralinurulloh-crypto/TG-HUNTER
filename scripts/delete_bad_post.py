import asyncio
from aiogram import Bot
from app.config import get_settings

async def delete_msg():
    s = get_settings()
    bot = Bot(s.bot_token)
    try:
        await bot.delete_message(s.target_channel, 228)
        print("Message 228 deleted successfully from", s.target_channel)
    except Exception as exc:
        print("Could not delete message 228:", exc)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(delete_msg())
