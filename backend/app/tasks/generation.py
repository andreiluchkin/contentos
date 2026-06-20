import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from .celery_app import app
from ..database import AsyncSessionLocal
from ..models import Post, Idea, BrandVoice, KnowledgeBaseItem
from ..models.enums import PipelineStatus
from ..ai.generation import GenerationService
from ..ai.scoring import ScoringService

logger = logging.getLogger(__name__)

generation_service = GenerationService()
scoring_service = ScoringService()


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(name="app.tasks.generation.generate_post")
def generate_post(post_id: str):
    return run_async(_generate_post(post_id))


async def _generate_post(post_id: str):
    async with AsyncSessionLocal() as session:
        post = await session.get(Post, post_id)
        if not post:
            logger.error("generate_post: post %s not found", post_id)
            return {"error": "post not found"}

        idea = await session.get(Idea, post.idea_id) if post.idea_id else None

        # Берём Brand Voice (singleton — берём первую запись)
        bv_result = await session.execute(select(BrandVoice).limit(1))
        brand_voice = bv_result.scalar_one_or_none()

        # KB поиск по теме
        topic = idea.title if idea else (post.body[:200] if post.body else "")
        kb_context = await _search_kb(session, topic)

    brand_voice_prompt = ""
    if brand_voice:
        if brand_voice.system_prompt_cache:
            brand_voice_prompt = brand_voice.system_prompt_cache
        else:
            brand_voice_prompt = generation_service.build_brand_voice_prompt(brand_voice)

    source_context = ""
    if idea:
        source_context = idea.context or ""
        if idea.source_url:
            source_context += f"\nИсточник: {idea.source_url}"

    try:
        result = await generation_service.generate_post(
            topic=topic,
            platform=post.platform,
            content_type=post.content_type,
            brand_voice_prompt=brand_voice_prompt,
            kb_context=kb_context,
            source_context=source_context,
        )
    except Exception as e:
        logger.error("generate_post: AI error for %s: %s", post_id, e)
        async with AsyncSessionLocal() as session:
            p = await session.get(Post, post_id)
            if p:
                p.publish_error = f"Generation failed: {e}"
                await session.commit()
        return {"error": str(e)}

    async with AsyncSessionLocal() as session:
        p = await session.get(Post, post_id)
        if p:
            p.body = result.body
            p.hashtags = result.hashtags
            if result.platform_meta:
                p.platform_meta = {**p.platform_meta, **result.platform_meta}
            p.status = PipelineStatus.DRAFT
            p.updated_at = datetime.now(timezone.utc)
            await session.commit()

    # Сразу рассчитываем Score
    calculate_content_score.delay(post_id)
    logger.info("generate_post: done for %s, score queued", post_id)
    return {"success": True, "post_id": post_id}


@app.task(name="app.tasks.generation.batch_generate")
def batch_generate(idea_ids: list[str]):
    return run_async(_batch_generate(idea_ids))


async def _batch_generate(idea_ids: list[str]):
    created = []
    errors = []

    async with AsyncSessionLocal() as session:
        for idea_id in idea_ids:
            idea = await session.get(Idea, idea_id)
            if not idea or idea.status != PipelineStatus.IDEA_APPROVED:
                errors.append({"idea_id": idea_id, "error": "not found or not approved"})
                continue

            # Для каждой идеи нужен account_id — берём из suggested_platform
            # или создаём заглушку (account_id должен передаваться в запросе)
            errors.append({"idea_id": idea_id, "error": "account_id required — use /posts/batch-generate endpoint"})

    return {"created": created, "errors": errors}


@app.task(name="app.tasks.generation.calculate_content_score")
def calculate_content_score(post_id: str):
    return run_async(_calculate_content_score(post_id))


async def _calculate_content_score(post_id: str):
    async with AsyncSessionLocal() as session:
        post = await session.get(Post, post_id)
        if not post or not post.body:
            return {"error": "post not found or empty"}

    try:
        score = await scoring_service.calculate_score(post.body, post.platform)
    except Exception as e:
        logger.error("calculate_content_score: scoring failed for %s: %s", post_id, e)
        return {"error": str(e)}

    async with AsyncSessionLocal() as session:
        p = await session.get(Post, post_id)
        if p:
            p.content_score = score.content_score
            p.score_hook = score.hook
            p.score_structure = score.structure
            p.score_readability = score.readability
            p.score_cta = score.cta
            p.score_platform_fit = score.platform_fit
            p.score_issues = score.issues
            p.score_calculated_at = datetime.now(timezone.utc)
            # Переводим в REVIEW если был DRAFT
            if p.status == PipelineStatus.DRAFT:
                p.status = PipelineStatus.REVIEW
            await session.commit()

    logger.info("calculate_content_score: %s → score=%d", post_id, score.content_score)
    return {
        "content_score": score.content_score,
        "hook": score.hook,
        "structure": score.structure,
        "readability": score.readability,
        "cta": score.cta,
        "platform_fit": score.platform_fit,
        "issues": score.issues,
    }


@app.task(name="app.tasks.generation.improve_post")
def improve_post(post_id: str, issue_keys: list[str] | None = None):
    return run_async(_improve_post(post_id, issue_keys or []))


async def _improve_post(post_id: str, issues_to_fix: list[str]):
    async with AsyncSessionLocal() as session:
        post = await session.get(Post, post_id)
        if not post:
            return {"error": "post not found"}

        bv_result = await session.execute(select(BrandVoice).limit(1))
        brand_voice = bv_result.scalar_one_or_none()

    brand_voice_prompt = ""
    if brand_voice and brand_voice.system_prompt_cache:
        brand_voice_prompt = brand_voice.system_prompt_cache

    issues_text = "\n".join(f"• {issue}" for issue in (issues_to_fix or post.score_issues or []))

    improve_prompt = f"""Улучши этот пост, исправив конкретные проблемы.

Текущий пост:
---
{post.body}
---

Проблемы которые нужно исправить:
{issues_text}

Требования:
- Сохрани голос и стиль автора
- Исправляй только то, что указано в проблемах
- Не переписывай пост полностью без необходимости
- Верни только улучшенный текст поста, без пояснений"""

    try:
        from ..ai.generation import GenerationService
        from ..config import settings as _settings
        svc = GenerationService()
        response = svc.client.chat.completions.create(
            model=_settings.openrouter_model,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": brand_voice_prompt or "Ты профессиональный редактор контента."},
                {"role": "user", "content": improve_prompt},
            ],
        )
        new_body = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("improve_post: AI error for %s: %s", post_id, e)
        return {"error": str(e)}

    async with AsyncSessionLocal() as session:
        p = await session.get(Post, post_id)
        if p:
            history = list(p.body_history or [])
            history.append({
                "body": p.body,
                "edited_at": datetime.now(timezone.utc).isoformat(),
                "score": p.content_score,
                "reason": "ai_improve",
            })
            p.body_history = history
            p.body = new_body
            p.updated_at = datetime.now(timezone.utc)
            await session.commit()

    # Пересчитываем Score
    calculate_content_score.delay(post_id)
    logger.info("improve_post: done for %s, rescoring queued", post_id)
    return {"success": True, "post_id": post_id}


async def _search_kb(session, topic: str, limit: int = 3) -> str:
    """Полнотекстовый поиск в KB по теме."""
    if not topic:
        return ""
    words = topic.lower().split()[:5]
    result = await session.execute(
        select(KnowledgeBaseItem)
        .where(KnowledgeBaseItem.is_active == True)
        .limit(limit * 3)
    )
    items = result.scalars().all()

    # Простой scoring по совпадению слов
    scored = []
    for item in items:
        text_lower = (item.title + " " + item.body).lower()
        score = sum(1 for w in words if w in text_lower)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [item for _, item in scored[:limit]]

    if not top:
        return ""

    return "\n\n".join(
        f"[{item.item_type}] {item.title}:\n{item.body[:500]}" for item in top
    )
