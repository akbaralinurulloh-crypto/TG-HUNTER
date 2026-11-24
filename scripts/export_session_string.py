"""
Mavjud hunter.session faylidan TG_SESSION_STRING generatsiya qilish.
Railway / Render kabi platformalarda fayl o'rniga STRING ishlatiladi.

Ishlatish:
    python scripts/export_session_string.py
"""
import asyncio
import os
import sys

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    print("XATO: telethon o'rnatilmagan. pip install telethon")
    sys.exit(1)


async def main():
    api_id = os.getenv("TG_API_ID") or input("TG_API_ID: ").strip()
    api_hash = os.getenv("TG_API_HASH") or input("TG_API_HASH: ").strip()
    session_path = os.getenv("TG_SESSION_PATH", "data/hunter.session")

    if not os.path.exists(session_path):
        print(f"XATO: Session fayl topilmadi: {session_path}")
        sys.exit(1)

    # Mavjud fayl-sessiyadan StringSession yaratish
    from telethon.sessions import SQLiteSession
    client = TelegramClient(session_path.replace(".session", ""), int(api_id), api_hash)

    async with client:
        ss = StringSession.save(client.session)

    print("\n" + "=" * 60)
    print("TG_SESSION_STRING (Railway/Render Environment ga kiriting):")
    print("=" * 60)
    print(ss)
    print("=" * 60)
    print("\nBu qatorni Railway -> Variables bo'limida TG_SESSION_STRING kaliti bilan saqlang.")


if __name__ == "__main__":
    asyncio.run(main())
