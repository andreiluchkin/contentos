import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class IdeaCreate(BaseModel):
    title: str = Field(..., max_length=500)
    context: str | None = None
    source_url: str | None = None
    source_name: str | None = None
    suggested_platform: str | None = None
    suggested_content_type: str | None = None
    relevance_score: float | None = Field(None, ge=0.0, le=1.0)
    pillar: str | None = Field(None, description="Slug пиллара")
    external_idea_id: str | None = None


class IdeaOut(BaseModel):
    id: uuid.UUID
    title: str
    context: str | None
    source_url: str | None
    source_name: str | None
    suggested_platform: str | None
    suggested_content_type: str | None
    relevance_score: float | None
    pillar_id: uuid.UUID | None
    status: str
    rejected_at: datetime | None
    rejection_reason: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IdeaApprove(BaseModel):
    pass


class IdeaReject(BaseModel):
    reason: str | None = None


class BatchApprove(BaseModel):
    idea_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)
