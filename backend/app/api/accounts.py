import uuid
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_auth
from ..database import get_db
from ..models import SocialAccount
from ..models.enums import Platform
from ..schemas import AccountTelegramCreate, AccountOut, AccountUpdateTimes
from ..schemas.account import AccountInstagramCreate
from ..adapters.registry import registry

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut], dependencies=[Depends(require_auth)])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SocialAccount).where(SocialAccount.is_active == True).order_by(SocialAccount.created_at)
    )
    return result.scalars().all()


@router.post("/telegram", response_model=AccountOut, status_code=201, dependencies=[Depends(require_auth)])
async def add_telegram_account(data: AccountTelegramCreate, db: AsyncSession = Depends(get_db)):
    # Проверяем что токен рабочий через Telegram API
    adapter = registry.get("telegram")

    # Создаём временный объект для валидации
    temp_account = SocialAccount(
        platform="telegram",
        handle=data.handle,
        display_name=data.display_name,
        access_token=data.bot_token,
        platform_meta={"bot_token": data.bot_token, "chat_id": data.chat_id},
    )

    is_valid = await adapter.validate_account(temp_account)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid Telegram bot token")

    # Проверяем дубликаты
    existing = await db.execute(
        select(SocialAccount).where(
            SocialAccount.platform == "telegram",
            SocialAccount.handle == data.handle,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Telegram account @{data.handle} already connected")

    account = SocialAccount(
        platform="telegram",
        handle=data.handle,
        display_name=data.display_name,
        access_token=data.bot_token,
        platform_meta={"bot_token": data.bot_token, "chat_id": data.chat_id},
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.post("/instagram", response_model=AccountOut, status_code=201, dependencies=[Depends(require_auth)])
async def add_instagram_account(data: AccountInstagramCreate, db: AsyncSession = Depends(get_db)):
    adapter = registry.get("instagram")

    temp_account = SocialAccount(
        platform="instagram",
        handle=data.handle,
        display_name=data.display_name,
        access_token=data.access_token,
        platform_meta={
            "ig_user_id": data.ig_user_id,
            "facebook_page_id": data.facebook_page_id,
        },
    )

    is_valid = await adapter.validate_account(temp_account)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid Instagram access token or ig_user_id")

    existing = await db.execute(
        select(SocialAccount).where(
            SocialAccount.platform == "instagram",
            SocialAccount.handle == data.handle,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Instagram @{data.handle} already connected")

    from datetime import datetime, timezone, timedelta
    account = SocialAccount(
        platform="instagram",
        handle=data.handle,
        display_name=data.display_name,
        access_token=data.access_token,
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=60),
        platform_meta={
            "ig_user_id": data.ig_user_id,
            "facebook_page_id": data.facebook_page_id,
        },
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.patch("/{account_id}/posting-times", response_model=AccountOut, dependencies=[Depends(require_auth)])
async def update_posting_times(
    account_id: uuid.UUID,
    data: AccountUpdateTimes,
    db: AsyncSession = Depends(get_db),
):
    account = await db.get(SocialAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    account.optimal_posting_times = data.optimal_posting_times
    await db.commit()
    await db.refresh(account)
    return account


@router.post("/{account_id}/refresh-token", dependencies=[Depends(require_auth)])
async def refresh_account_token(account_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from ..tasks.accounts import refresh_token
    refresh_token.delay(str(account_id))
    return {"status": "queued", "account_id": str(account_id)}


@router.delete("/{account_id}", status_code=204, dependencies=[Depends(require_auth)])
async def delete_account(account_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    account = await db.get(SocialAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    account.is_active = False
    await db.commit()
