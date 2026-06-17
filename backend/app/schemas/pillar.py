import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PillarCreate(BaseModel):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=100, pattern=r"^[a-z0-9-]+$")
    color: str = Field(default="#7a40ed", pattern=r"^#[0-9a-fA-F]{6}$")
    description: str | None = None
    sort_order: int = 0


class PillarUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    description: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class PillarOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    color: str
    description: str | None
    is_active: bool
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}
