"""Post collection and ingestion from monitored sources (TZ Section 5)."""
import hashlib
from typing import Optional, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Source, SourcePost, SystemLog
from app.logging_config import logger


def calculate_content_hash(text: Optional[str], media_ref: Optional[str] = None) -> str:
    """Generate SHA-256 hash of normalized text and media reference."""
    clean_text = " ".join((text or "").lower().split())
    data = f"{clean_text}|{media_ref or ''}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class ContentCollector:
    """Ingests raw posts from sources into the source_posts table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def ingest_post(
        self,
        source_identifier: str,
        source_message_id: int,
        original_text: Optional[str],
        media_type: str = "TEXT",
        media_reference: Optional[str] = None,
    ) -> Optional[SourcePost]:
        """
        Ingest a post from a source channel.
        Checks for uniqueness of (source_id, source_message_id).
        """
        clean_ident = source_identifier.replace("https://t.me/", "").replace("@", "").split("?")[0].strip()
        stmt = select(Source).where(Source.telegram_identifier == clean_ident)
        source = (await self.session.execute(stmt)).scalars().first()

        if not source:
            logger.warning(f"Post rad etildi: Manba @{clean_ident} bazada mavjud emas.")
            log = SystemLog(
                event_type="INGEST_SKIPPED",
                severity="WARNING",
                message=f"Noma'lum manbadan post keldi: @{clean_ident} #{source_message_id}",
            )
            self.session.add(log)
            await self.session.commit()
            return None

        # Check existing (source_id, source_message_id)
        exist_stmt = select(SourcePost).where(
            and_(
                SourcePost.source_id == source.id,
                SourcePost.source_message_id == source_message_id,
            )
        )
        if (await self.session.execute(exist_stmt)).scalars().first():
            logger.info(f"Post @{clean_ident} #{source_message_id} allaqachon mavjud. O'tkazib yuborildi.")
            return None

        content_hash = calculate_content_hash(original_text, media_reference)

        post = SourcePost(
            source_id=source.id,
            source_message_id=source_message_id,
            original_text=original_text,
            media_type=media_type.upper(),
            media_reference=media_reference,
            content_hash=content_hash,
        )
        self.session.add(post)

        sys_log = SystemLog(
            event_type="POST_INGESTED",
            severity="INFO",
            message=f"Yangi post qabul qilindi: @{clean_ident} #{source_message_id} ({media_type})",
        )
        self.session.add(sys_log)
        await self.session.commit()
        logger.info(f"Yangi post bazaga saqlandi: ID={post.id} (@{clean_ident} #{source_message_id})")
        return post
