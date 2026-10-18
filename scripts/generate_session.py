"""Telethon session generator for headless servers."""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession


async def main():
    print("=========================================================")
    print("   TELETHON STRING SESSION GENERATOR (VPS UCHUN)        ")
    print("=========================================================")
    print("Ushbu skript my.telegram.org ma'lumotlari orqali")
    print("TELETHON_SESSION_STRING maxfiy kalitini yaratib beradi.\n")

    api_id_input = input("Telegram API ID ni kiriting: ").strip()
    api_hash_input = input("Telegram API HASH ni kiriting: ").strip()

    if not api_id_input.isdigit() or not api_hash_input:
        print("Xatolik: API ID va API Hash to'g'ri kiritilishi shart!")
        return

    api_id = int(api_id_input)
    api_hash = api_hash_input

    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_str = client.session.save()
        user = await client.get_me()

        print("\n" + "=" * 55)
        print(f"Muvaffaqiyatli ulandi: {user.first_name} (@{user.username or user.id})")
        print("=" * 55)
        print("\nQuyidagi qatorni nusxalang va .env faylidagi TELETHON_SESSION_STRING ga qo'ying:")
        print(f"\nTELETHON_SESSION_STRING={session_str}\n")
        print("DIQQAT: Ushbu satrni hech kimga ko'rsatmang va GitHubga yuklamang!")
        print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
