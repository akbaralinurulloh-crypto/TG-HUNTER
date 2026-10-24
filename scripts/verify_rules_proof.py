import sys
import asyncio

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from app.ai.analyzer import AIContentAnalyzer
from app.publisher.telegram_publisher import TelegramPublisher
from app.database.session import get_db
from app.database.models import ContentItem, SourcePost


async def demonstrate_proof():
    analyzer = AIContentAnalyzer()
    print("=" * 60)
    print("ISBOT 1: HADIS KELSA NIMA BO'LADI?")
    print("=" * 60)
    hadith_sample = (
        "Rasululloh sollallohu alayhi vasallam marhamat qildilar: "
        "«Umra keyingi Umragacha bo'lgan gunohlarga kafforatdir» (Imom Buxoriy rivoyati)."
    )
    print("KIRUVCHI MATN:")
    print(hadith_sample)
    res1 = await analyzer.analyze_and_rewrite(hadith_sample, source_rights_status="VERIFIED")
    print("\nNATIJA:")
    print(f"Qaror (Decision): {res1.publish_decision}")
    print(f"Rad etish sababi: {res1.rejection_reason}")
    print(f"Kanalga chiqariladimi?: {'YOQ, BLOKLANDI' if res1.publish_decision == 'REJECT' else 'HA'}")

    print("\n" + "=" * 60)
    print("ISBOT 2: MATNSIZ RASM KELSA NIMA BO'LADI? (TO'QILADIMI?)")
    print("=" * 60)
    empty_sample = ""
    print("KIRUVCHI MATN: [Matnsiz rasm yoki bo'sh post]")
    res2 = await analyzer.analyze_and_rewrite(empty_sample, media_type="PHOTO", source_rights_status="VERIFIED")
    print("\nNATIJA:")
    print(f"Qaror (Decision): {res2.publish_decision}")
    print(f"Rad etish sababi: {res2.rejection_reason}")
    print(f"Birorta so'z to'qildimi?: {'YOQ, BIRORTA SOZ TOQILMADI' if not res2.body else 'HA'}")

    print("\n" + "=" * 60)
    print("ISBOT 3: KANALGA TUSHGAN HAQIQIY UMRA POSTI QANDAY ISHLANADI?")
    print("=" * 60)
    real_sample = """
🕋 SAFAR OLDI SUHBAT!
Muborak Makka va Madina sari safaringizni rejalashtiring.
✈️ 05-Noyabr — TASH → MAD
✈️ 12-Noyabr — TASH → MAD
✈️ 19-Noyabr — TASH → MAD
💰 Narxi: 1250$
🏨 Mehmonxonalarimiz: 4 yulduzli, Haramga yaqin.

📞 Batafsil va band qilish
📞 +99891-233-77-77
📞 +99897-250-77-70
📲 @Muhtashamadmin
📱 Telegram | Instagram | YouTube
📌 Manba: Nurli Safar
"""
    print("ASL KANAL MATNI (Raqobatchi raqamlari va manba bilan):")
    print(real_sample.strip())
    res3 = await analyzer.analyze_and_rewrite(real_sample, source_title="Nurli Safar", source_rights_status="VERIFIED")
    print("\nAGENT ISHLAB CHIQARGAN TAYYOR POST (Kanalga chiqadigan ko'rinish):")
    print("-" * 40)
    print(f"SARLAVHA: {res3.headline}")
    print(res3.body)
    print("-" * 40)
    print(f"Qaror: {res3.publish_decision}")
    print(f"Begona raqamlar qoldimi?: {'HA' if '+99891' in res3.body else 'YOQ, TOZALANDI'}")
    print(f"Begona @admin yoki instagram qoldimi?: {'HA' if '@Muhtashamadmin' in res3.body or 'Instagram' in res3.body else 'YOQ, TOZALANDI'}")
    print(f"Manba nomi ko'rsatildimi?: {'HA' if 'Nurli Safar' in res3.body else 'YOQ, TOZALANDI'}")
    print(f"Sizning 888327700 raqamingiz qo'yildimi?: {'HA' if '+998 88 832 77 00' in res3.body else 'YOQ'}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demonstrate_proof())
