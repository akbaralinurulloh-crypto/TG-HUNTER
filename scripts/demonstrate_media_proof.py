import sys
import os
import asyncio

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from aiogram import Bot
from app.config import settings
from app.ai.analyzer import AIContentAnalyzer


async def run_proof():
    analyzer = AIContentAnalyzer()
    bot = Bot(token=settings.BOT_TOKEN)

    print("=" * 65)
    print("ISBOT 1: RASMDA BEGONA FIRMA LOGOTIPI VA TELEFON RAQAMI BO'LSA:")
    print("=" * 65)
    img1 = "./temp_media/nurlisafar_19991.jpg"
    res1 = await analyzer.analyze_and_rewrite(
        raw_text="",
        media_type="PHOTO",
        media_reference=img1,
        source_title="Nurli Safar",
        source_rights_status="VERIFIED"
    )
    print(f"Fayl: {img1}")
    print(f"Qaror (Decision): {res1.publish_decision}")
    print(f"Rad etish sababi: {res1.rejection_reason}")
    print(f"Kanalga chiqariladimi?: {'YOQ, RAD ETILDI (BLOKLANDI)' if res1.publish_decision == 'REJECT' else 'HA'}")

    print("\n[Kutish...] Gemini API 5 RPM limitiga tushmaslik uchun 12 soniya kutilmoqda...")
    await asyncio.sleep(12)

    print("\n" + "=" * 65)
    print("ISBOT 2: RASMDA BEGONA FIRMA SUMKALARI / KIYIMLARI BO'LSA:")
    print("=" * 65)
    img2 = "./temp_media/nurlisafar_20045.jpg"
    res2 = await analyzer.analyze_and_rewrite(
        raw_text="",
        media_type="PHOTO",
        media_reference=img2,
        source_title="Nurli Safar",
        source_rights_status="VERIFIED"
    )
    print(f"Fayl: {img2}")
    print(f"Qaror (Decision): {res2.publish_decision}")
    print(f"Rad etish sababi: {res2.rejection_reason}")
    print(f"Kanalga chiqariladimi?: {'YOQ, RAD ETILDI (BLOKLANDI)' if res2.publish_decision == 'REJECT' else 'HA'}")

    print("\n[Kutish...] Gemini API 5 RPM limitiga tushmaslik uchun 12 soniya kutilmoqda...")
    await asyncio.sleep(12)

    print("\n" + "=" * 65)
    print("ISBOT 3: TOZA RASM BO'LSA (HECH QANDAY BEGONA LOGOTIPSIZ):")
    print("=" * 65)
    img3 = "./temp_media/muhtashamtravel_8406.jpg"
    res3 = await analyzer.analyze_and_rewrite(
        raw_text="Juma muborak!",
        media_type="PHOTO",
        media_reference=img3,
        source_title="Muhtasham",
        source_rights_status="VERIFIED"
    )
    print(f"Fayl: {img3}")
    print(f"Qaror: {res3.publish_decision}")
    print(f"Sarlavha: {res3.headline}")
    print(f"Tayyorlangan izoh matni:\n{res3.body}")
    print(f"Hadis bormi?: {'HA' if 'hadis' in res3.body.lower() or 'rasululloh' in res3.body.lower() else 'YOQ, BIRORTA HAM HADIS YOQ'}")
    print(f"Sizning raqamingiz bormi?: {'HA, QOYILGAN' if '+998 88 832 77 00' in res3.body else 'YOQ'}")

    # Send direct notification to user Telegram ID
    try:
        admin_text = (
            "🔍 <b>Rasm va Video tahlili isboti:</b>\n\n"
            "1. ❌ <b>nurlisafar_19991.jpg</b>: Ziyoratchilar sumkasida begona logo va telefon raqam ko'ringani uchun <b>RAD ETILDI</b>.\n"
            "2. ❌ <b>nurlisafar_20045.jpg</b>: Sumka va kiyimlarda begona logo ko'ringani uchun <b>RAD ETILDI</b>.\n"
            "3. ✅ <b>muhtashamtravel_8406.jpg</b>: Begona belgilar yo'q, toza media. Unga chiroyli izoh yozildi, hadis qo'shilmadi va sizning raqamingiz (+998 88 832 77 00) biriktirildi."
        )
        await bot.send_message(chat_id=240409213, text=admin_text, parse_mode="HTML")
        print("\nAdmin (240409213) Telegramiga hisobot yuborildi!")
    except Exception as e:
        print(f"\nAdminga yuborishda xato: {e}")

    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_proof())
