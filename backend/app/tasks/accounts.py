import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_

from .celery_app import app
from ..database import AsyncSessionLocal
from ..models import SocialAccount
from ..adapters.registry import registry

logger = logging.getLogger(__name__)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(name="app.tasks.accounts.refresh_expiring_tokens")
def refresh_expiring_tokens():
    return run_async(_refresh_expiring_tokens())


async def _refresh_expiring_tokens():
    soon = datetime.now(timezone.utc) + timedelta(hours=24)
    refreshed = []
    errors = []

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SocialAccount).where(
                and_(
                    SocialAccount.is_active == True,
                    SocialAccount.token_expires_at != None,
                    SocialAccount.token_expires_at < soon,
                )
            )
        )
        accounts = result.scalars().all()

    for account in accounts:
        try:
            adapter = registry.get(account.platform)
            updated = await adapter.refresh_token(account)
            async with AsyncSessionLocal() as session:
                acc = await session.get(SocialAccount, account.id)
                acc.access_token = updated.access_token
                acc.refresh_token = updated.refresh_token
                acc.token_expires_at = updated.token_expires_at
                acc.last_token_refresh = datetime.now(timezone.utc)
                await session.commit()
            refreshed.append(str(account.id))
        except Exception as e:
            logger.error("Failed to refresh token for account %s: %s", account.id, e)
            errors.append({"account_id": str(account.id), "error": str(e)})

    return {"refreshed": refreshed, "errors": errors}


@app.task(name="app.tasks.accounts.refresh_token")
def refresh_token(account_id: str):
    return run_async(_refresh_token(account_id))


async def _refresh_token(account_id: str):
    async with AsyncSessionLocal() as session:
        account = await session.get(SocialAccount, account_id)
        if not account:
            return {"error": "account not found"}

    try:
        adapter = registry.get(account.platform)
        updated = await adapter.refresh_token(account)
        async with AsyncSessionLocal() as session:
            acc = await session.get(SocialAccount, account_id)
            acc.access_token = updated.access_token
            acc.refresh_token = updated.refresh_token
            acc.token_expires_at = updated.token_expires_at
            acc.last_token_refresh = datetime.now(timezone.utc)
            await session.commit()
        return {"success": True}
    except Exception as e:
        logger.error("refresh_token failed for %s: %s", account_id, e)
        return {"error": str(e)}
