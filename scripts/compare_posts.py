import sys
import asyncio

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from sqlalchemy import select
from app.database.session import get_db
from app.database.models import SourcePost, ContentItem, PublishedPost, Source


async def check():
    async with get_db() as session:
        pub_stmt = select(PublishedPost).order_by(PublishedPost.id.asc())
        published = (await session.execute(pub_stmt)).scalars().all()
        for p in published:
            ci = await session.get(ContentItem, p.content_item_id)
            sp = await session.get(SourcePost, ci.source_post_id) if ci else None
            src = await session.get(Source, sp.source_id) if sp else None
            src_name = src.telegram_identifier if src else "?"
            orig_id = sp.source_message_id if sp else "?"
            print(f"=== PUBLISHED POST #{p.id} (Telegram Msg #{p.telegram_message_id}) ===")
            print(f"MANBA: @{src_name} #{orig_id} (Media: {sp.media_type if sp else '?'})")
            print("--- ASL MATN (ORIGINAL TEXT): ---")
            print((sp.original_text or "[Matnsiz]").strip() if sp else "NONE")
            print("--- KANALGA CHIQARILGAN MATN (PUBLISHED): ---")
            print(ci.body if ci else "NONE")
            print("=" * 60)


if __name__ == "__main__":
    asyncio.run(check())
