"""Deduplication engine checking content hashes, pHash, and semantic similarity (TZ Section 10)."""
import re
import difflib
from typing import Optional, Tuple, List
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database.models import SourcePost, ContentItem, PublishedPost, SystemLog
from app.logging_config import logger


def normalize_clean_text(text: Optional[str]) -> str:
    """Normalize text by stripping URLs, hashtags, punctuation and extra whitespace."""
    if not text:
        return ""
    text = re.sub(r"https?://\S+|t\.me/\S+", "", text)
    text = re.sub(r"[@#]\w+", "", text)
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def calculate_semantic_similarity(text1: str, text2: str) -> float:
    """Calculate semantic/textual similarity using word stem overlap and SequenceMatcher."""
    norm1 = normalize_clean_text(text1)
    norm2 = normalize_clean_text(text2)
    if not norm1 or not norm2:
        return 0.0
    if norm1 == norm2:
        return 1.0

    # Substring contiguous alignment ratio
    seq_ratio = difflib.SequenceMatcher(None, norm1, norm2).ratio()

    # Stem Jaccard (5-character stems for agglutinative Uzbek morphology)
    stems1 = set([w[:5] for w in norm1.split() if len(w) >= 3])
    stems2 = set([w[:5] for w in norm2.split() if len(w) >= 3])
    intersection = len(stems1.intersection(stems2))
    union = len(stems1.union(stems2))
    stem_jaccard = (intersection / union) if union > 0 else 0.0

    return round(max(seq_ratio, (0.4 * stem_jaccard + 0.6 * seq_ratio)), 4)


class DeduplicationEngine:
    """Multi-stage deduplication checking database constraints, hashes, and semantic text overlap."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.threshold = settings.SEMANTIC_THRESHOLD

    async def is_duplicate(
        self,
        content_hash: str,
        text_content: Optional[str],
        current_post_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Check if post is duplicate:
        1. Exact content_hash match in published_posts
        2. Exact content_hash match in existing source_posts
        3. Semantic similarity against published posts from the last 14 days
        """
        # 1. Exact hash in published posts
        pub_stmt = select(PublishedPost).where(PublishedPost.content_hash == content_hash)
        published = (await self.session.execute(pub_stmt)).scalars().first()
        if published:
            reason = f"Aynan bir xil kontent xeshi allaqachon kanalga joylangan (PublishedPost #{published.id})"
            logger.warning(reason)
            return True, reason, published.id

        # 2. Exact hash in previous source posts
        post_stmt = select(SourcePost).where(
            and_(
                SourcePost.content_hash == content_hash,
                SourcePost.id != current_post_id if current_post_id else True,
            )
        )
        existing_post = (await self.session.execute(post_stmt)).scalars().first()
        if existing_post:
            reason = f"Aynan bir xil kontent xeshi oldin kelgan (SourcePost #{existing_post.id})"
            logger.warning(reason)
            return True, reason, existing_post.id

        # 3. Semantic similarity against recently published posts
        if text_content and len(text_content.strip()) >= 30:
            since = datetime.now(timezone.utc) - timedelta(days=14)
            recent_stmt = (
                select(ContentItem)
                .where(
                    and_(
                        ContentItem.created_at >= since,
                        ContentItem.status == "PUBLISHED",
                    )
                )
                .order_by(ContentItem.id.desc())
                .limit(100)
            )
            recent_items = (await self.session.execute(recent_stmt)).scalars().all()

            for item in recent_items:
                sim = calculate_semantic_similarity(text_content, item.body)
                if sim >= self.threshold:
                    reason = f"Semantik o'xshashlik {sim:.2f} >= chegara {self.threshold} (ContentItem #{item.id} bilan)"
                    logger.warning(reason)
                    return True, reason, item.id

        return False, None, None
