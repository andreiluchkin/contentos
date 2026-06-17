import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base
from .enums import RepurposeSourceType

if TYPE_CHECKING:
    from .media import MediaFile
    from .post import Post


class RepurposeJob(Base):
    __tablename__ = "repurpose_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)

    source_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files.id"), nullable=True
    )
    source_youtube_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_ideas: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    source_media: Mapped["MediaFile | None"] = relationship("MediaFile", foreign_keys=[source_media_id])
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="repurpose_job")
