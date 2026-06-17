import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from ..models.enums import Platform


class AccountTelegramCreate(BaseModel):
    handle: str = Field(..., description="Telegram channel username (без @) или числовой chat_id")
    display_name: str
    bot_token: str = Field(..., description="Telegram Bot API токен")
    chat_id: str = Field(..., description="ID канала/чата куда публиковать")


class AccountInstagramCreate(BaseModel):
    handle: str = Field(..., description="Instagram username (без @)")
    display_name: str
    access_token: str = Field(..., description="Long-lived Instagram User Access Token")
    ig_user_id: str = Field(..., description="Instagram User ID (числовой)")
    facebook_page_id: str | None = Field(None, description="Facebook Page ID (опционально, для расширенных метрик)")


class AccountTikTokCreate(BaseModel):
    handle: str = Field(..., description="TikTok username (без @)")
    display_name: str
    access_token: str = Field(..., description="TikTok OAuth2 Access Token")
    refresh_token: str = Field(..., description="TikTok OAuth2 Refresh Token")
    open_id: str = Field(..., description="TikTok Open ID пользователя")


class AccountYouTubeCreate(BaseModel):
    handle: str = Field(..., description="YouTube channel handle или ID")
    display_name: str
    access_token: str = Field(..., description="Google OAuth2 Access Token")
    refresh_token: str = Field(..., description="Google OAuth2 Refresh Token")
    channel_id: str = Field(..., description="YouTube Channel ID (UC...)")


class AccountLinkedInCreate(BaseModel):
    handle: str = Field(..., description="LinkedIn profile slug или company page")
    display_name: str
    access_token: str = Field(..., description="LinkedIn OAuth2 Access Token")
    refresh_token: str = Field(default="", description="LinkedIn OAuth2 Refresh Token (если есть)")
    person_urn: str = Field(..., description="urn:li:person:XXXX или urn:li:organization:XXXX")


class AccountXCreate(BaseModel):
    handle: str = Field(..., description="X username (без @)")
    display_name: str
    access_token: str = Field(..., description="X OAuth2 Access Token")
    refresh_token: str = Field(..., description="X OAuth2 Refresh Token")
    user_id: str = Field(..., description="X numeric User ID")


class AccountUpdateTimes(BaseModel):
    optimal_posting_times: dict[str, str] = Field(
        ...,
        description='{"mon": "09:00", "tue": "09:00", ...}',
    )


class AccountOut(BaseModel):
    id: uuid.UUID
    platform: str
    handle: str
    display_name: str
    avatar_url: str | None
    is_active: bool
    token_expires_at: datetime | None
    optimal_posting_times: dict
    created_at: datetime

    model_config = {"from_attributes": True}
