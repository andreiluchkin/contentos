import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_auth
from ..database import get_db
from ..models import Post, BrandVoice
from ..models.enums import PipelineStatus
from ..ai.generation import GenerationService
from ..ai.scoring import ScoringService
from ..schemas.post import ContentScoreOut

router = APIRouter(prefix="/ai", tags=["ai"])
generation_service = GenerationService()
scoring_service = ScoringService()


class GeneratePostRequest(BaseModel):
    topic: str
    platform: str
    content_type: str
    pillar_id: uuid.UUID | None = None
    context: str | None = None
    source_url: str | None = None


class ImprovePostRequest(BaseModel):
    post_id: uuid.UUID
    score_issues: list[str] | None = None


class ImprovePostResult(BaseModel):
    body: str
    changes_queued: bool


async def _get_brand_voice_prompt(db: AsyncSession) -> str:
    result = await db.execute(select(BrandVoice).limit(1))
    bv = result.scalar_one_or_none()
    if not bv:
        return ""
    if bv.system_prompt_cache:
        return bv.system_prompt_cache
    return generation_service.build_brand_voice_prompt(bv)


@router.post("/generate-post", dependencies=[Depends(require_auth)])
async def generate_post_direct(data: GeneratePostRequest, db: AsyncSession = Depends(get_db)):
    """Прямая генерация без создания поста в БД — для превью."""
    brand_voice_prompt = await _get_brand_voice_prompt(db)

    source_context = data.context or ""
    if data.source_url:
        source_context += f"\nИсточник: {data.source_url}"

    try:
        result = await generation_service.generate_post(
            topic=data.topic,
            platform=data.platform,
            content_type=data.content_type,
            brand_voice_prompt=brand_voice_prompt,
            source_context=source_context,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {e}")

    return {
        "body": result.body,
        "hashtags": result.hashtags,
        "platform_meta": result.platform_meta,
    }


@router.post("/posts/{post_id}/generate", dependencies=[Depends(require_auth)])
async def generate_for_post(post_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Запускает генерацию для существующего поста через Celery."""
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status not in (PipelineStatus.IDEA_APPROVED, PipelineStatus.DRAFT):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot generate for post in status '{post.status}'",
        )

    from ..tasks.generation import generate_post
    generate_post.delay(str(post_id))
    return {"status": "queued", "post_id": str(post_id)}


@router.post("/posts/{post_id}/score", response_model=ContentScoreOut, dependencies=[Depends(require_auth)])
async def score_post(post_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Синхронно рассчитывает Content Score и сохраняет в пост."""
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not post.body:
        raise HTTPException(status_code=400, detail="Post body is empty")

    try:
        score = await scoring_service.calculate_score(post.body, post.platform)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scoring failed: {e}")

    post.content_score = score.content_score
    post.score_hook = score.hook
    post.score_structure = score.structure
    post.score_readability = score.readability
    post.score_cta = score.cta
    post.score_platform_fit = score.platform_fit
    post.score_issues = score.issues
    post.score_calculated_at = datetime.now(timezone.utc)
    await db.commit()

    return ContentScoreOut(
        content_score=score.content_score,
        score_hook=score.hook,
        score_structure=score.structure,
        score_readability=score.readability,
        score_cta=score.cta,
        score_platform_fit=score.platform_fit,
        score_issues=score.issues,
    )


@router.post("/posts/{post_id}/improve", dependencies=[Depends(require_auth)])
async def improve_post(post_id: uuid.UUID, data: ImprovePostRequest, db: AsyncSession = Depends(get_db)):
    """Запускает AI-улучшение поста через Celery."""
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    from ..tasks.generation import improve_post as improve_task
    improve_task.delay(str(post_id), data.score_issues)
    return {"status": "queued", "post_id": str(post_id), "issues_count": len(data.score_issues or [])}


@router.post("/score", response_model=ContentScoreOut, dependencies=[Depends(require_auth)])
async def score_text(body: dict, db: AsyncSession = Depends(get_db)):
    """Рассчитывает Score для произвольного текста (без сохранения)."""
    text = body.get("body", "")
    platform = body.get("platform", "telegram")
    if not text:
        raise HTTPException(status_code=400, detail="body is required")

    try:
        score = await scoring_service.calculate_score(text, platform)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scoring failed: {e}")

    return ContentScoreOut(
        content_score=score.content_score,
        score_hook=score.hook,
        score_structure=score.structure,
        score_readability=score.readability,
        score_cta=score.cta,
        score_platform_fit=score.platform_fit,
        score_issues=score.issues,
    )
