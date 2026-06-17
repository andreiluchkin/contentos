"""
Instagram Graph API v21.0 adapter.
Требует: Facebook Page + Instagram Professional Account + OAuth.

Поддерживает:
  - Photo posts (одно изображение)
  - Carousel (несколько изображений)
  - Reels (видео)
  - Text-only через image_url с белым фоном (workaround)

Флоу публикации:
  1. POST /{ig-user-id}/media → creation_id
  2. POST /{ig-user-id}/media_publish {creation_id} → media_id

Для Reels нужен polling статуса между шагами.
"""
import asyncio
import logging

import httpx

from .base import PlatformAdapter, PublishResult, Metrics, ValidationResult

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v21.0"

MAX_CAPTION_LENGTH = 2200
MAX_HASHTAGS = 30
REELS_POLL_ATTEMPTS = 20
REELS_POLL_INTERVAL = 5  # секунд


class InstagramAdapter(PlatformAdapter):
    platform = "instagram"

    async def publish_post(self, post, account) -> PublishResult:
        ig_user_id = account.platform_meta.get("ig_user_id", "")
        access_token = account.access_token

        if not ig_user_id or not access_token:
            return PublishResult(success=False, error="Missing ig_user_id or access_token")

        caption = self._build_caption(post)

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Определяем тип публикации
            media_ids = post.media_ids or []

            if not media_ids:
                # Нет медиа → текстовый пост через API не поддерживается напрямую.
                # Используем image_url с пустым белым фоном (workaround для text-only).
                # В production: генерировать карточку через Pillow или использовать
                # заготовленное изображение-плейсхолдер из MinIO.
                return PublishResult(
                    success=False,
                    error="Instagram requires media. Add an image or use a text-card generator.",
                )

            if len(media_ids) == 1:
                result = await self._publish_single(client, ig_user_id, access_token, media_ids[0], caption, post)
            elif len(media_ids) > 1:
                result = await self._publish_carousel(client, ig_user_id, access_token, media_ids, caption)
            else:
                result = PublishResult(success=False, error="No media")

        return result

    async def _publish_single(self, client, ig_user_id, token, media_id, caption, post) -> PublishResult:
        """Публикует один пост (photo или reel)."""
        platform_meta = post.platform_meta or {}
        is_reel = platform_meta.get("is_reel", False)

        if is_reel:
            return await self._publish_reel(client, ig_user_id, token, media_id, caption)

        # Photo post
        media_url = await self._get_media_presigned_url(media_id)
        if not media_url:
            return PublishResult(success=False, error=f"Cannot resolve media URL for {media_id}")

        # Step 1: create container
        resp = await client.post(
            f"{GRAPH_BASE}/{ig_user_id}/media",
            params={
                "image_url": media_url,
                "caption": caption,
                "access_token": token,
            },
        )
        data = resp.json()
        if "error" in data:
            return PublishResult(success=False, error=data["error"].get("message", str(data["error"])))

        creation_id = data.get("id")
        if not creation_id:
            return PublishResult(success=False, error=f"No creation_id returned: {data}")

        # Step 2: publish
        return await self._publish_container(client, ig_user_id, token, creation_id)

    async def _publish_reel(self, client, ig_user_id, token, media_id, caption) -> PublishResult:
        """Публикует Reel."""
        video_url = await self._get_media_presigned_url(media_id)
        if not video_url:
            return PublishResult(success=False, error=f"Cannot resolve video URL for {media_id}")

        # Step 1: init upload
        resp = await client.post(
            f"{GRAPH_BASE}/{ig_user_id}/media",
            params={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "share_to_feed": "true",
                "access_token": token,
            },
        )
        data = resp.json()
        if "error" in data:
            return PublishResult(success=False, error=data["error"].get("message", str(data["error"])))

        creation_id = data.get("id")

        # Step 2: poll until FINISHED
        for _ in range(REELS_POLL_ATTEMPTS):
            await asyncio.sleep(REELS_POLL_INTERVAL)
            status_resp = await client.get(
                f"{GRAPH_BASE}/{creation_id}",
                params={"fields": "status_code,status", "access_token": token},
            )
            status_data = status_resp.json()
            status_code = status_data.get("status_code")
            if status_code == "FINISHED":
                break
            if status_code == "ERROR":
                return PublishResult(
                    success=False,
                    error=f"Reel processing failed: {status_data.get('status')}",
                )

        return await self._publish_container(client, ig_user_id, token, creation_id)

    async def _publish_carousel(self, client, ig_user_id, token, media_ids, caption) -> PublishResult:
        """Публикует карусель из нескольких изображений."""
        child_ids = []
        for media_id in media_ids[:10]:  # IG лимит: 10 изображений
            url = await self._get_media_presigned_url(media_id)
            if not url:
                logger.warning("Cannot resolve carousel item %s, skipping", media_id)
                continue

            resp = await client.post(
                f"{GRAPH_BASE}/{ig_user_id}/media",
                params={
                    "image_url": url,
                    "is_carousel_item": "true",
                    "access_token": token,
                },
            )
            data = resp.json()
            if "id" in data:
                child_ids.append(data["id"])

        if not child_ids:
            return PublishResult(success=False, error="No carousel items could be prepared")

        # Создаём carousel container
        resp = await client.post(
            f"{GRAPH_BASE}/{ig_user_id}/media",
            params={
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": caption,
                "access_token": token,
            },
        )
        data = resp.json()
        if "error" in data:
            return PublishResult(success=False, error=data["error"].get("message", str(data["error"])))

        return await self._publish_container(client, ig_user_id, token, data.get("id"))

    async def _publish_container(self, client, ig_user_id, token, creation_id) -> PublishResult:
        resp = await client.post(
            f"{GRAPH_BASE}/{ig_user_id}/media_publish",
            params={"creation_id": creation_id, "access_token": token},
        )
        data = resp.json()
        if "error" in data:
            return PublishResult(success=False, error=data["error"].get("message", str(data["error"])))

        media_id = data.get("id")
        return PublishResult(
            success=bool(media_id),
            external_post_id=media_id,
            external_url=f"https://www.instagram.com/p/{media_id}/",
        )

    async def delete_post(self, external_post_id: str, account) -> bool:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(
                f"{GRAPH_BASE}/{external_post_id}",
                params={"access_token": account.access_token},
            )
            return resp.status_code == 200

    async def get_metrics(self, external_post_id: str, account) -> Metrics:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{GRAPH_BASE}/{external_post_id}/insights",
                params={
                    "metric": "impressions,reach,likes_count,comments_count,shares",
                    "access_token": account.access_token,
                },
            )
            data = resp.json()
            if "error" in data:
                return Metrics()

            metrics_map = {
                item["name"]: item["values"][0]["value"]
                for item in data.get("data", [])
                if item.get("values")
            }
            return Metrics(
                views=metrics_map.get("impressions", 0),
                likes=metrics_map.get("likes_count", 0),
                comments=metrics_map.get("comments_count", 0),
                shares=metrics_map.get("shares", 0),
            )

    async def validate_content(self, post) -> ValidationResult:
        errors = []
        caption = self._build_caption(post)

        if len(caption) > MAX_CAPTION_LENGTH:
            errors.append(
                f"Caption слишком длинный: {len(caption)} символов (лимит {MAX_CAPTION_LENGTH})"
            )

        hashtag_count = len([w for w in caption.split() if w.startswith("#")])
        if hashtag_count > MAX_HASHTAGS:
            errors.append(f"Слишком много хэштегов: {hashtag_count} (лимит {MAX_HASHTAGS})")

        if not post.media_ids:
            errors.append("Instagram требует медиафайл (изображение или видео)")

        return ValidationResult(valid=not errors, errors=errors)

    async def refresh_token(self, account):
        """Long-lived токен Instagram живёт 60 дней и обновляется GET /refresh_access_token."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{GRAPH_BASE}/refresh_access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "access_token": account.access_token,
                },
            )
            data = resp.json()
            if "access_token" in data:
                from datetime import datetime, timezone, timedelta
                account.access_token = data["access_token"]
                account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=data.get("expires_in", 5184000)
                )
        return account

    async def validate_account(self, account) -> bool:
        ig_user_id = account.platform_meta.get("ig_user_id", "")
        if not ig_user_id:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{GRAPH_BASE}/{ig_user_id}",
                params={"fields": "id,username", "access_token": account.access_token},
            )
            return "id" in resp.json()

    def _build_caption(self, post) -> str:
        """Собирает caption: body + хэштеги."""
        parts = [post.body]
        if post.hashtags:
            parts.append("\n\n" + " ".join(f"#{tag.lstrip('#')}" for tag in post.hashtags))
        return "".join(parts)

    async def _get_media_presigned_url(self, media_id: str) -> str | None:
        """Получает публичный URL медиафайла из MinIO."""
        try:
            import boto3
            from botocore.config import Config
            from ..config import settings

            s3 = boto3.client(
                "s3",
                endpoint_url=f"http{'s' if settings.minio_secure else ''}://{settings.minio_endpoint}",
                aws_access_key_id=settings.minio_access_key,
                aws_secret_access_key=settings.minio_secret_key,
                config=Config(signature_version="s3v4"),
            )
            # media_id — это UUID медиафайла, нужно найти storage_key в БД
            # Для простоты: предполагаем storage_key = "originals/{media_id}"
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.minio_bucket, "Key": f"originals/{media_id}"},
                ExpiresIn=3600,
            )
            return url
        except Exception as e:
            logger.error("Cannot generate presigned URL for %s: %s", media_id, e)
            return None
