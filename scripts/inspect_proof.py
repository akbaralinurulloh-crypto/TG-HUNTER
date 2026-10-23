import sys
import asyncio

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from sqlalchemy import select
from app.database.session import get_db
from app.database.models import SourcePost, ContentItem, PublishedPost, Source


async def inspect():
    async with get_db() as session:
        pub_stmt = select(PublishedPost).order_by(PublishedPost.id.desc())
        published = (await session.execute(pub_stmt)).scalars().all()
        print("=== JONLI KANALGA JOYLANGAN POSTLAR ===")
        for p in published:
            ci = await session.get(ContentItem, p.content_item_id)
            sp = await session.get(SourcePost, ci.source_post_id) if ci else None
            src = await session.get(Source, sp.source_id) if sp else None
            src_name = src.telegram_identifier if src else "?"
            orig_id = sp.source_message_id if sp else "?"
            media_type = sp.media_type if sp else "?"
            headline = ci.headline if ci else "?"
            print(f"Post ID: {p.id} | Kanal Msg ID: {p.telegram_message_id}")
            print(f"  Asl manba: @{src_name} (Post #{orig_id}, Media: {media_type})")
            print(f"  Sarlavha: {headline}")
            print(f"  Nashr vaqti: {p.published_at}")
            print("-" * 50)

        # SourcePosts
        sp_all = (await session.execute(select(SourcePost))).scalars().all()
        ci_all = (await session.execute(select(ContentItem))).scalars().all()
        print(f"\nHUNTING STATISTIKASI:")
        print(f"  Manbalardan ushlangan jami postlar: {len(sp_all)} ta")
        print(f"  AI tahlilidan o'tganlar: {len(ci_all)} ta")
        print(f"  Kanalga chiqqanlar: {len(published)} ta")

        print("\nOXIRGI 5 TA USHLANGAN POST (HUNTED):")
        for sp in sp_all[-5:]:
            src = await session.get(Source, sp.source_id)
            src_name = src.telegram_identifier if src else "?"
            preview = (sp.original_text or "")[:60].replace("\n", " ")
            print(f"  • SourcePost #{sp.id} <- @{src_name} #{sp.source_message_id} [{sp.media_type}]: \"{preview}...\"")


if __name__ == "__main__":
    asyncio.run(inspect())
