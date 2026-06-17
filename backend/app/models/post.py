import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from .base import Base
from .enums import PipelineStatus, Platform, ContentType

if TYPE_CHECKING:
    from .idea import Idea
    from .account import SocialAccount
    from .pillar import ContentPillar
    from .repurpose import RepurposeJob


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    idea_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ideas.id"), nullable=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_accounts.id"), nullable=False
    )
    pillar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_pillars.id"), nullable=True
    )
    repurpose_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repurpose_jobs.id"), nullable=True
    )

    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hashtags: Mapped[list] = mapped_column(ARRAY(String), default=list, nullable=False)
    media_ids: Mapped[list] = mapped_column(ARRAY(String), default=list, nullable=False)
    platform_meta: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    status: Mapped[str] = mapped_column(String(50), default=PipelineStatus.DRAFT, nullable=False)

    # Content Score
    content_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_hook: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_structure: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_readability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_cta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_platform_fit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_issues: Mapped[list] = mapped_column(ARRAY(String), default=list, nullable=False)
    score_calculated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Scheduling & publishing
    scheduled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    external_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publish_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(nullable=True)

    body_history: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    author_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    idea: Mapped["Idea | None"] = relationship("Idea", back_populates="posts")
    account: Mapped["SocialAccount"] = relationship("SocialAccount", back_populates="posts")
    pillar: Mapped["ContentPillar | None"] = relationship("ContentPillar", back_populates="posts")
    repurpose_job: Mapped["RepurposeJob | None"] = relationship("RepurposeJob", back_populates="posts")

    __table_args__ = (
        Index("idx_posts_status", "status"),
        Index("idx_posts_scheduled_at", "scheduled_at"),
        Index("idx_posts_platform", "platform"),
        Index("idx_posts_pillar_id", "pillar_id"),
        Index("idx_posts_account_id", "account_id"),
    )
