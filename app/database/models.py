"""SQLAlchemy database models strictly matching Section 14 of the TZ."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from sqlalchemy import (
    String,
    BigInteger,
    Integer,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Source(Base):
    """Monitored content sources and verified usage rights (TZ Section 14 & 6)."""
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_identifier: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rights_status: Mapped[str] = mapped_column(String(50), default="VERIFIED", nullable=False)  # VERIFIED, UNVERIFIED, REVOKED
    rights_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    posts: Mapped[List["SourcePost"]] = relationship("SourcePost", back_populates="source", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Source(id={self.id}, ident='{self.telegram_identifier}', active={self.active}, rights='{self.rights_status}')>"


class SourcePost(Base):
    """Raw posts ingested from source channels (TZ Section 14)."""
    __tablename__ = "source_posts"
    __table_args__ = (
        UniqueConstraint("source_id", "source_message_id", name="uq_source_post"),
        Index("idx_post_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    source_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    media_type: Mapped[str] = mapped_column(String(30), default="TEXT", nullable=False)  # TEXT, PHOTO, VIDEO, ALBUM
    media_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # File paths or IDs
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="posts")
    content_items: Mapped[List["ContentItem"]] = relationship("ContentItem", back_populates="source_post", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SourcePost(id={self.id}, src_id={self.source_id}, msg_id={self.source_message_id})>"


class ContentItem(Base):
    """AI evaluated, rewritten, and moderated content items (TZ Section 14 & 7)."""
    __tablename__ = "content_items"
    __table_args__ = (
        Index("idx_content_item_status", "status"),
        Index("idx_content_item_decision", "publish_decision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_post_id: Mapped[int] = mapped_column(ForeignKey("source_posts.id", ondelete="CASCADE"), nullable=False)
    headline: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(100), default="Umrah", nullable=False)
    quality_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0-10
    factual_risk: Mapped[str] = mapped_column(String(100), default="NONE", nullable=False)  # NONE, SUSPICIOUS, HIGH
    rights_status: Mapped[str] = mapped_column(String(50), default="VERIFIED", nullable=False)
    publish_decision: Mapped[str] = mapped_column(String(50), default="AUTO_PUBLISH", nullable=False)  # AUTO_PUBLISH, REJECT, PENDING_APPROVAL
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="NEW", nullable=False)  # NEW, QUEUED, PUBLISHED, REJECTED, FAILED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    source_post: Mapped["SourcePost"] = relationship("SourcePost", back_populates="content_items")
    queue_entries: Mapped[List["PublishQueue"]] = relationship("PublishQueue", back_populates="content_item", cascade="all, delete-orphan")
    published_post: Mapped[Optional["PublishedPost"]] = relationship("PublishedPost", back_populates="content_item", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ContentItem(id={self.id}, topic='{self.topic}', score={self.quality_score}, decision='{self.publish_decision}')>"


class PublishQueue(Base):
    """Scheduled queue for distributing posts across the day (TZ Section 14 & 11)."""
    __tablename__ = "publish_queue"
    __table_args__ = (
        Index("idx_queue_status_sched", "status", "scheduled_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content_item_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)  # PENDING, PROCESSING, PUBLISHED, FAILED
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    content_item: Mapped["ContentItem"] = relationship("ContentItem", back_populates="queue_entries")

    def __repr__(self) -> str:
        return f"<PublishQueue(id={self.id}, item_id={self.content_item_id}, sched='{self.scheduled_at}', status='{self.status}')>"


class PublishedPost(Base):
    """Permanent record of published posts in the target channel (TZ Section 14)."""
    __tablename__ = "published_posts"
    __table_args__ = (
        Index("idx_pub_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content_item_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), unique=True, nullable=False)
    target_channel: Mapped[str] = mapped_column(String(100), nullable=False)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Relationships
    content_item: Mapped["ContentItem"] = relationship("ContentItem", back_populates="published_post")

    def __repr__(self) -> str:
        return f"<PublishedPost(id={self.id}, target='{self.target_channel}', msg_id={self.telegram_message_id})>"


class SystemLog(Base):
    """System events and error logs (TZ Section 14)."""
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="INFO", nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    def __repr__(self) -> str:
        return f"<SystemLog(id={self.id}, event='{self.event_type}', sev='{self.severity}')>"


class SystemState(Base):
    """Runtime flags (such as pause/resume) and configuration checkpoints."""
    __tablename__ = "system_states"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    def __repr__(self) -> str:
        return f"<SystemState(key='{self.key}', value='{self.value}')>"
