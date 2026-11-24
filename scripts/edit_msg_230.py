import asyncio
from aiogram import Bot
from app.config import get_settings

async def update_msg_230():
    s = get_settings()
    bot = Bot(s.bot_token)
    new_caption = (
        "Бугун дастурхонда ҳақиқий байрам! 😍🍽️\n\n"
        "Самса, гўшт қовурдоқ, мошкичири, шўрва, турли салатлар, ичимликлар ва мевалар… 🤤\n\n"
        "Буни ўқиб ҳам қорнингиз очиб кетдими? Унда тасаввур қилинг, ҳожиларимизнинг кайфияти қандай! 😂❤️\n\n"
        "Келинг, сиз ҳам биз билан сафарга чиқинг! Зиёрат ҳам, мазали таомlar ҳам сизни кутмоқда! 🤗\n\n"
        "“Muhtasham Travel — xotirjam \n"
        "ibodatni xohlovchilar uchun!”\n\n"
        "📱 Telegram  😎 <a href=\"https://www.instagram.com/muhtasham_travel/\">Instagram</a>\n"
        "😎YouTube     📱 Facebook\n\n"
        "Muqaddas safarlardagi har bir lahza o'zgacha shukuh va quvonchga to'la. Ziyoratdan qaytgach, samimiy dasturxon atrofida jam bo'lish qalbga iliqlik bag'ishlaydi. Bu go'zal damlar insonni yanada ezgulikka undaydi."
    )
    try:
        await bot.edit_message_caption(
            chat_id=s.target_channel,
            message_id=230,
            caption=new_caption,
            parse_mode="HTML"
        )
        print("SUCCESS: Message 230 updated with HTML link!")
    except Exception as exc:
        print("Failed to update message 230:", exc)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(update_msg_230())
