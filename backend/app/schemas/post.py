import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    account_id: uuid.UUID
    platform: str
    content_type: str
    body: str = ""
    pillar_id: uuid.UUID | None = None
    idea_id: uuid.UUID | None = None
    hashtags: list[str] = []
    platform_meta: dict = {}
    author_notes: str | None = None


class PostUpdate(BaseModel):
    body: str | None = None
    hashtags: list[str] | None = None
    platform_meta: dict | None = None
    pillar_id: uuid.UUID | None = None
    author_notes: str | None = None


class PostStatusUpdate(BaseModel):
    status: str

    model_config = {"use_enum_values": True}


class PostSchedule(BaseModel):
    scheduled_at: datetime


class PostGenerateRequest(BaseModel):
    account_id: uuid.UUID
    platform: str
    content_type: str
    idea_id: uuid.UUID | None = None
    topic: str | None = None
    pillar_id: uuid.UUID | None = None
    context: str | None = None
    source_url: str | None = None


class BatchGenerateRequest(BaseModel):
    idea_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)


class ContentScoreOut(BaseModel):
    content_score: int
    score_hook: int
    score_structure: int
    score_readability: int
    score_cta: int
    score_platform_fit: int
    score_issues: list[str]


class PostOut(BaseModel):
    id: uuid.UUID
    idea_id: uuid.UUID | None
    account_id: uuid.UUID
    pillar_id: uuid.UUID | None
    platform: str
    content_type: str
    body: str
    hashtags: list[str]
    media_ids: list[str]
    platform_meta: dict
    status: str
    content_score: int | None
    score_hook: int | None
    score_structure: int | None
    score_readability: int | None
    score_cta: int | None
    score_platform_fit: int | None
    score_issues: list[str]
    score_calculated_at: datetime | None
    scheduled_at: datetime | None
    published_at: datetime | None
    external_post_id: str | None
    publish_error: str | None
    publish_attempts: int
    author_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
