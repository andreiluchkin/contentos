from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_auth
from ..database import get_db
from ..models import BrandVoice
from ..ai.generation import GenerationService

router = APIRouter(prefix="/brand-voice", tags=["brand-voice"])
generation_service = GenerationService()


class BrandVoiceUpdate(BaseModel):
    tone: str | None = None
    length_preferences: dict | None = None
    forbidden_words: list[str] | None = None
    preferred_patterns: list[str] | None = None


class ExamplePostAdd(BaseModel):
    text: str
    platform: str


class BrandVoiceOut(BaseModel):
    tone: str
    length_preferences: dict
    forbidden_words: list[str]
    preferred_patterns: list[str]
    example_posts: list[dict]
    system_prompt_cache: str | None
    system_prompt_updated_at: datetime | None

    model_config = {"from_attributes": True}


async def _get_or_create(db: AsyncSession) -> BrandVoice:
    result = await db.execute(select(BrandVoice).limit(1))
    bv = result.scalar_one_or_none()
    if not bv:
        bv = BrandVoice()
        db.add(bv)
        await db.commit()
        await db.refresh(bv)
    return bv


@router.get("", response_model=BrandVoiceOut, dependencies=[Depends(require_auth)])
async def get_brand_voice(db: AsyncSession = Depends(get_db)):
    return await _get_or_create(db)


@router.put("", response_model=BrandVoiceOut, dependencies=[Depends(require_auth)])
async def update_brand_voice(data: BrandVoiceUpdate, db: AsyncSession = Depends(get_db)):
    bv = await _get_or_create(db)

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(bv, field, value)

    # Инвалидируем кэш system prompt
    bv.system_prompt_cache = None
    bv.system_prompt_updated_at = None
    bv.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(bv)
    return bv


@router.post("/example-posts", response_model=BrandVoiceOut, dependencies=[Depends(require_auth)])
async def add_example_post(data: ExamplePostAdd, db: AsyncSession = Depends(get_db)):
    bv = await _get_or_create(db)
    examples = list(bv.example_posts or [])
    examples.append({
        "text": data.text,
        "platform": data.platform,
        "added_at": datetime.now(timezone.utc).isoformat(),
    })
    bv.example_posts = examples
    bv.system_prompt_cache = None
    await db.commit()
    await db.refresh(bv)
    return bv


@router.delete("/example-posts/{index}", response_model=BrandVoiceOut, dependencies=[Depends(require_auth)])
async def delete_example_post(index: int, db: AsyncSession = Depends(get_db)):
    bv = await _get_or_create(db)
    examples = list(bv.example_posts or [])
    if index < 0 or index >= len(examples):
        raise HTTPException(status_code=404, detail="Example post index out of range")
    examples.pop(index)
    bv.example_posts = examples
    bv.system_prompt_cache = None
    await db.commit()
    await db.refresh(bv)
    return bv


@router.post("/regenerate-prompt", dependencies=[Depends(require_auth)])
async def regenerate_prompt(db: AsyncSession = Depends(get_db)):
    bv = await _get_or_create(db)
    prompt = generation_service.build_brand_voice_prompt(bv)
    bv.system_prompt_cache = prompt
    bv.system_prompt_updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True, "prompt_length": len(prompt)}
