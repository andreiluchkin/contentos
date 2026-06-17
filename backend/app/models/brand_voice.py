import uuid
from datetime import datetime

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy import String

from .base import Base


class BrandVoice(Base):
    __tablename__ = "brand_voice"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tone: Mapped[str] = mapped_column(Text, nullable=False, default="")
    length_preferences: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    forbidden_words: Mapped[list] = mapped_column(ARRAY(String), default=list, nullable=False)
    preferred_patterns: Mapped[list] = mapped_column(ARRAY(String), default=list, nullable=False)
    example_posts: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Кэш system prompt — обновляется при изменении настроек
    system_prompt_cache: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
