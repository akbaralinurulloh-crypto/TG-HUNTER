"""Central pipeline coordinating ingestion, rights, deduplication, AI, and queuing (TZ Section 7)."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.logging_config import logger
from app.database.models import SourcePost, ContentItem, SystemLog, Source
from app.sources.manager import SourceManager
from app.moderation.deduplication import DeduplicationEngine
from app.moderation.quality import QualityControlService
from app.ai.analyzer import AIContentAnalyzer
from app.scheduler.queue_manager import QueueScheduler


class ContentPipelineService:
    """End-to-end pipeline processing raw source posts into scheduled publications."""

    def __init__(self, session: AsyncSession, bot=None):
        self.session = session
        self.source_manager = SourceManager(session)
        self.dedup_engine = DeduplicationEngine(session)
        self.ai_analyzer = AIContentAnalyzer()
        self.queue_scheduler = QueueScheduler(bot=bot)

    async def process_source_post(self, source_post: SourcePost) -> Optional[ContentItem]:
        """
        Process a SourcePost through all verification steps:
        1. Check legal usage rights of the source (TZ Section 6)
        2. Deduplication check (TZ Section 10)
        3. AI evaluation & Uzbek rewriting (TZ Section 7)
        4. Quality control & factual risk check (TZ Section 8)
        5. Enqueue for publication if approved (TZ Section 11)
        """
        logger.info(f"Pipeline boshlandi: SourcePost #{source_post.id} (Source #{source_post.source_id})")

        # Step 1: Check legal usage rights
        source = await self.session.get(Source, source_post.source_id)
        rights_check = await self.source_manager.check_usage_rights(source.telegram_identifier if source else "")
        if not rights_check["allowed"]:
            logger.warning(f"Post #{source_post.id} rad etildi: {rights_check['notes']}")
            item = ContentItem(
                source_post_id=source_post.id,
                headline="Rad etilgan: Huquq mavjud emas",
                body=source_post.original_text or "",
                topic="Boshqa",
                quality_score=0,
                factual_risk="HIGH",
                rights_status=rights_check["status"],
                publish_decision="REJECT",
                rejection_reason=rights_check["notes"],
                status="REJECTED",
            )
            self.session.add(item)
            await self.session.commit()
            return item

        # Step 2: Deduplication check
        is_dup, dup_reason, dup_id = await self.dedup_engine.is_duplicate(
            content_hash=source_post.content_hash,
            text_content=source_post.original_text,
            current_post_id=source_post.id,
        )
        if is_dup:
            logger.warning(f"Post #{source_post.id} dublikat deb topildi: {dup_reason}")
            item = ContentItem(
                source_post_id=source_post.id,
                headline="Takroriy post",
                body=source_post.original_text or "",
                topic="Boshqa",
                quality_score=0,
                factual_risk="NONE",
                rights_status="VERIFIED",
                publish_decision="REJECT",
                rejection_reason=dup_reason,
                status="REJECTED",
            )
            self.session.add(item)
            log = SystemLog(
                event_type="DUPLICATE_BLOCKED",
                severity="WARNING",
                message=f"Dublikat bloklandi: Post #{source_post.id}. Sabab: {dup_reason}",
            )
            self.session.add(log)
            await self.session.commit()
            return item

        # Step 3: AI analysis and Uzbek rewriting
        source_title = source.title if source else "Muhtasham"
        ai_res = await self.ai_analyzer.analyze_and_rewrite(
            raw_text=source_post.original_text,
            media_type=source_post.media_type,
            media_reference=source_post.media_reference,
            source_title=source_title,
            source_rights_status=source.rights_status if source else "VERIFIED",
        )

        # Step 4: Quality control inspection
        is_quality_ok, quality_fail_reason = QualityControlService.inspect_content(ai_res)
        if not is_quality_ok:
            decision = "REJECT"
            status = "REJECTED"
            final_reason = quality_fail_reason
        else:
            decision = ai_res.publish_decision
            status = "APPROVED" if decision == "AUTO_PUBLISH" else "REJECTED"
            final_reason = ai_res.rejection_reason

        # Create ContentItem
        content_item = ContentItem(
            source_post_id=source_post.id,
            headline=ai_res.headline,
            body=ai_res.body,
            topic=ai_res.topic,
            quality_score=ai_res.quality_score,
            factual_risk=ai_res.factual_risk,
            rights_status=ai_res.rights_status,
            publish_decision=decision,
            rejection_reason=final_reason,
            status=status,
        )
        self.session.add(content_item)
        await self.session.commit()

        # Step 5: Enqueue if approved for auto publish
        if decision == "AUTO_PUBLISH" and status == "APPROVED":
            await self.queue_scheduler.enqueue_content_item(self.session, content_item.id)
            logger.info(f"Post #{content_item.id} muvaffaqiyatli navbatga qo'yildi.")

        return content_item
