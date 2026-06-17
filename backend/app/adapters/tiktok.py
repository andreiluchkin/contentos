"""
TikTok for Business API v2 adapter.

Флоу публикации видео:
  1. POST /v2/post/publish/video/init/  → upload_url + publish_id
  2. PUT upload_url (chunk upload)       → загрузка файла
  3. GET /v2/post/publish/status/fetch/ → polling PROCESSING_UPLOAD → PUBLISH_COMPLETE

Флоу публикации фото (Photo Post / Carousel):
  1. POST /v2/post/publish/content/init/ с media_type=PHOTO_POST
  2. PUT каждого upload_url
  3. POST /v2/post/publish/content/publish/

Direct Post (только видео, без upload — только TikTok Creator Portal):
  Мы используем FILE UPLOAD флоу для полного контроля.

Ограничения:
  - description: ≤ 2200 символов
  - hashtags: ≤ 30 штук в description
  - видео: 3с–10мин, ≤ 4 GB
  - фото: ≤ 35 изображений в карусели

Требует scopes: video.publish, video.upload (user-level OAuth).
"""
import asyncio
import logging

import httpx

from .base import PlatformAdapter, PublishResult, Metrics, ValidationResult

logger = logging.getLogger(__name__)

TIKTOK_API = "https://open.tiktokapis.com"
MAX_DESCRIPTION = 2200
MAX_HASHTAGS = 30
VIDEO_POLL_ATTEMPTS = 30
VIDEO_POLL_INTERVAL = 5


class TikTokAdapter(PlatformAdapter):
    platform = "tiktok"

    async def publish_post(self, post, account) -> PublishResult:
        access_token = account.access_token
        if not access_token:
            return PublishResult(success=False, error="Missing TikTok access_token")

        platform_meta = post.platform_meta or {}
        media_ids = post.media_ids or []

        description = self._build_description(post)

        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}

            if not media_ids:
                # Нет медиафайла — для TikTok видео обязательно
                return PublishResult(
                    success=False,
                    error="TikTok requires a video file. Upload a video via media files.",
                )

            if len(media_ids) == 1:
                return await self._publish_video(client, headers, media_ids[0], description, platform_meta)
            else:
                return await self._publish_photo_carousel(client, headers, media_ids, description)

    async def _publish_video(self, client, headers, media_id, description, platform_meta) -> PublishResult:
        """Публикует одно видео через file upload флоу."""
        # Получаем файл из MinIO
        video_bytes = await self._download_from_minio(media_id)
        if not video_bytes:
            return PublishResult(success=False, error=f"Cannot download media {media_id}")

        file_size = len(video_bytes)
        chunk_size = 10 * 1024 * 1024  # 10 MB chunks

        # Step 1: init upload
        init_resp = await client.post(
            f"{TIKTOK_API}/v2/post/publish/video/init/",
            headers=headers,
            json={
                "post_info": {
                    "title": description[:150],
                    "description": description,
                    "privacy_level": platform_meta.get("privacy_level", "SELF_ONLY"),
                    "disable_duet": platform_meta.get("disable_duet", False),
                    "disable_comment": platform_meta.get("disable_comment", False),
                    "disable_stitch": platform_meta.get("disable_stitch", False),
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": chunk_size,
                    "total_chunk_count": (file_size + chunk_size - 1) // chunk_size,
                },
            },
        )

        data = init_resp.json()
        if data.get("error", {}).get("code", "ok") != "ok":
            return PublishResult(success=False, error=str(data.get("error")))

        upload_url = data["data"]["upload_url"]
        publish_id = data["data"]["publish_id"]

        # Step 2: chunk upload
        offset = 0
        chunk_index = 0
        while offset < file_size:
            chunk = video_bytes[offset:offset + chunk_size]
            end = min(offset + chunk_size - 1, file_size - 1)

            upload_resp = await client.put(
                upload_url,
                content=chunk,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes {offset}-{end}/{file_size}",
                    "Content-Length": str(len(chunk)),
                },
                timeout=120.0,
            )
            if upload_resp.status_code not in (200, 206):
                return PublishResult(
                    success=False,
                    error=f"Chunk upload failed: {upload_resp.status_code}",
                )
            offset += chunk_size
            chunk_index += 1

        # Step 3: poll status
        for _ in range(VIDEO_POLL_ATTEMPTS):
            await asyncio.sleep(VIDEO_POLL_INTERVAL)
            status_resp = await client.post(
                f"{TIKTOK_API}/v2/post/publish/status/fetch/",
                headers=headers,
                json={"publish_id": publish_id},
            )
            status_data = status_resp.json()
            status = status_data.get("data", {}).get("status")
            if status == "PUBLISH_COMPLETE":
                post_id = status_data["data"].get("publicaly_available_post_id", [None])[0]
                return PublishResult(
                    success=True,
                    external_post_id=str(post_id) if post_id else publish_id,
                    external_url=f"https://www.tiktok.com/@{status_data['data'].get('tiktok_id', '')}/video/{post_id}",
                )
            if status in ("FAILED", "PUBLISH_FAILED"):
                error_code = status_data.get("data", {}).get("fail_reason", "unknown")
                return PublishResult(success=False, error=f"TikTok publish failed: {error_code}")

        return PublishResult(success=False, error="TikTok video processing timed out")

    async def _publish_photo_carousel(self, client, headers, media_ids, description) -> PublishResult:
        """Публикует карусель изображений (Photo Post)."""
        photos = []
        for media_id in media_ids[:35]:
            img_bytes = await self._download_from_minio(media_id)
            if not img_bytes:
                continue
            photos.append(img_bytes)

        if not photos:
            return PublishResult(success=False, error="No photos could be prepared")

        # Init
        init_resp = await client.post(
            f"{TIKTOK_API}/v2/post/publish/content/init/",
            headers=headers,
            json={
                "post_info": {
                    "title": description,
                    "privacy_level": "SELF_ONLY",
                    "auto_add_music": True,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "photo_cover_index": 0,
                    "photo_images": [{"size": len(p)} for p in photos],
                },
                "media_type": "PHOTO_POST",
            },
        )
        data = init_resp.json()
        if data.get("error", {}).get("code", "ok") != "ok":
            return PublishResult(success=False, error=str(data.get("error")))

        publish_id = data["data"]["publish_id"]
        upload_urls = data["data"].get("photo_upload_urls", [])

        # Upload each photo
        for i, (img_bytes, upload_url) in enumerate(zip(photos, upload_urls)):
            resp = await client.put(
                upload_url,
                content=img_bytes,
                headers={"Content-Type": "image/jpeg", "Content-Length": str(len(img_bytes))},
                timeout=60.0,
            )
            if resp.status_code not in (200, 204):
                logger.warning("Photo %d upload returned %d", i, resp.status_code)

        # Publish
        pub_resp = await client.post(
            f"{TIKTOK_API}/v2/post/publish/content/publish/",
            headers=headers,
            json={"publish_id": publish_id},
        )
        pub_data = pub_resp.json()
        if pub_data.get("error", {}).get("code", "ok") != "ok":
            return PublishResult(success=False, error=str(pub_data.get("error")))

        return PublishResult(
            success=True,
            external_post_id=publish_id,
            external_url="https://www.tiktok.com/",
        )

    async def delete_post(self, external_post_id: str, account) -> bool:
        """TikTok API v2 не поддерживает удаление постов через API."""
        logger.warning("TikTok does not support post deletion via API. post_id=%s", external_post_id)
        return False

    async def get_metrics(self, external_post_id: str, account) -> Metrics:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{TIKTOK_API}/v2/video/query/",
                headers={"Authorization": f"Bearer {account.access_token}"},
                json={
                    "filters": {"video_ids": [external_post_id]},
                    "fields": ["view_count", "like_count", "comment_count", "share_count"],
                },
            )
            data = resp.json()
            videos = data.get("data", {}).get("videos", [])
            if not videos:
                return Metrics()
            v = videos[0]
            return Metrics(
                views=v.get("view_count", 0),
                likes=v.get("like_count", 0),
                comments=v.get("comment_count", 0),
                shares=v.get("share_count", 0),
            )

    async def validate_content(self, post) -> ValidationResult:
        errors = []
        description = self._build_description(post)

        if len(description) > MAX_DESCRIPTION:
            errors.append(f"Описание слишком длинное: {len(description)} (лимит {MAX_DESCRIPTION})")

        hashtag_count = len([w for w in description.split() if w.startswith("#")])
        if hashtag_count > MAX_HASHTAGS:
            errors.append(f"Слишком много хэштегов: {hashtag_count} (лимит {MAX_HASHTAGS})")

        if not post.media_ids:
            errors.append("TikTok требует видео или изображения")

        return ValidationResult(valid=not errors, errors=errors)

    async def refresh_token(self, account):
        """Обновляет OAuth токен через refresh_token."""
        from ..config import settings
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{TIKTOK_API}/v2/oauth/token/",
                data={
                    "client_key": settings.tiktok_client_key,
                    "client_secret": settings.tiktok_client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": account.platform_meta.get("refresh_token", ""),
                },
            )
            data = resp.json()
            if "access_token" in data:
                from datetime import datetime, timezone, timedelta
                account.access_token = data["access_token"]
                account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=data.get("expires_in", 86400)
                )
                meta = dict(account.platform_meta or {})
                meta["refresh_token"] = data.get("refresh_token", meta.get("refresh_token", ""))
                account.platform_meta = meta
        return account

    async def validate_account(self, account) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{TIKTOK_API}/v2/user/info/",
                headers={"Authorization": f"Bearer {account.access_token}"},
                json={"fields": ["open_id", "display_name"]},
            )
            data = resp.json()
            return data.get("error", {}).get("code", "ok") == "ok"

    def _build_description(self, post) -> str:
        parts = [post.body or ""]
        # Скрипт из platform_meta
        script = (post.platform_meta or {}).get("script", "")
        if script and script != post.body:
            parts = [script]
        if post.hashtags:
            parts.append("\n" + " ".join(f"#{t.lstrip('#')}" for t in post.hashtags))
        return "".join(parts)

    async def _download_from_minio(self, media_id: str) -> bytes | None:
        """Скачивает медиафайл из MinIO по media_id (UUID)."""
        try:
            import boto3
            from botocore.config import Config
            from io import BytesIO
            from ..config import settings

            s3 = boto3.client(
                "s3",
                endpoint_url=f"http{'s' if settings.minio_secure else ''}://{settings.minio_endpoint}",
                aws_access_key_id=settings.minio_access_key,
                aws_secret_access_key=settings.minio_secret_key,
                config=Config(signature_version="s3v4"),
            )
            buf = BytesIO()
            s3.download_fileobj(settings.minio_bucket, f"originals/{media_id}", buf)
            return buf.getvalue()
        except Exception as e:
            logger.error("Cannot download %s from MinIO: %s", media_id, e)
            return None
