import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import Base
from .enums import PipelineStatus, Platform, ContentType

if TYPE_CHECKING:
    from .pillar import ContentPillar
    from .post import Post
    from .external_source import ExternalSource


class Idea(Base):
    __tablename__ = "ideas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    suggested_platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    suggested_content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    pillar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_pillars.id"), nullable=True
    )
    external_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_sources.id"), nullable=True
    )
    external_idea_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default=PipelineStatus.INBOX, nullable=False)
    rejected_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    pillar: Mapped["ContentPillar | None"] = relationship("ContentPillar", back_populates="ideas")
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="idea")
    external_source: Mapped["ExternalSource | None"] = relationship("ExternalSource")

    __table_args__ = (
        Index("idx_ideas_status", "status"),
        Index("idx_ideas_pillar_id", "pillar_id"),
        Index("idx_ideas_created_at", "created_at"),
    )
