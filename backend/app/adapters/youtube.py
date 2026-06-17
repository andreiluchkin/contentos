"""
YouTube Data API v3 adapter.

Поддерживает:
  - Загрузку видео (resumable upload)
  - Обновление description/tags после загрузки
  - Установку thumbnail (если есть thumbnail_key)
  - Метрики через YouTube Analytics API

Флоу публикации:
  1. POST /upload/youtube/v3/videos?uploadType=resumable → Location header (upload URI)
  2. PUT upload_uri с телом файла → video_id
  3. (опционально) POST /thumbnails/set

Scopes: youtube.upload, youtube.readonly, youtubepartner (для аналитики).

Ограничения:
  - description: ≤ 5000 символов
  - title: ≤ 100 символов
  - tags: каждый тег ≤ 500 символов, суммарно ≤ 500 символов
"""
import logging

import httpx

from .base import PlatformAdapter, PublishResult, Metrics, ValidationResult

logger = logging.getLogger(__name__)

YT_API = "https://www.googleapis.com/youtube/v3"
YT_UPLOAD = "https://www.googleapis.com/upload/youtube/v3"
YT_ANALYTICS = "https://youtubeanalytics.googleapis.com/v2"

MAX_DESCRIPTION = 5000
MAX_TITLE = 100


class YouTubeAdapter(PlatformAdapter):
    platform = "youtube"

    async def publish_post(self, post, account) -> PublishResult:
        access_token = account.access_token
        if not access_token:
            return PublishResult(success=False, error="Missing YouTube access_token")

        media_ids = post.media_ids or []
        if not media_ids:
            return PublishResult(
                success=False,
                error="YouTube requires a video file.",
            )

        platform_meta = post.platform_meta or {}
        title = platform_meta.get("title") or post.body[:MAX_TITLE].strip().split("\n")[0]
        description = self._build_description(post)
        tags = post.hashtags or []
        privacy = platform_meta.get("privacy_status", "private")  # private / unlisted / public

        video_bytes = await self._download_from_minio(media_ids[0])
        if not video_bytes:
            return PublishResult(success=False, error=f"Cannot download media {media_ids[0]}")

        async with httpx.AsyncClient(timeout=300.0) as client:
            headers = {"Authorization": f"Bearer {access_token}"}

            # Step 1: initiate resumable upload
            init_resp = await client.post(
                f"{YT_UPLOAD}/videos?uploadType=resumable&part=snippet,status",
                headers={
                    **headers,
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": "video/*",
                    "X-Upload-Content-Length": str(len(video_bytes)),
                },
                json={
                    "snippet": {
                        "title": title[:MAX_TITLE],
                        "description": description[:MAX_DESCRIPTION],
                        "tags": [t.lstrip("#") for t in tags],
                        "categoryId": platform_meta.get("category_id", "22"),  # 22 = People & Blogs
                        "defaultLanguage": platform_meta.get("language", "ru"),
                    },
                    "status": {
                        "privacyStatus": privacy,
                        "selfDeclaredMadeForKids": False,
                    },
                },
                timeout=30.0,
            )

            if init_resp.status_code != 200:
                return PublishResult(
                    success=False,
                    error=f"YouTube init failed: {init_resp.status_code} {init_resp.text[:200]}",
                )

            upload_uri = init_resp.headers.get("Location")
            if not upload_uri:
                return PublishResult(success=False, error="No upload URI in YouTube response")

            # Step 2: upload video (single PUT — для файлов < 256 MB)
            # Для больших файлов нужен chunk upload
            file_size = len(video_bytes)
            upload_resp = await client.put(
                upload_uri,
                content=video_bytes,
                headers={
                    **headers,
                    "Content-Type": "video/mp4",
                    "Content-Length": str(file_size),
                },
                timeout=300.0,
            )

            if upload_resp.status_code not in (200, 201):
                return PublishResult(
                    success=False,
                    error=f"YouTube upload failed: {upload_resp.status_code} {upload_resp.text[:200]}",
                )

            video_data = upload_resp.json()
            video_id = video_data.get("id")

            if not video_id:
                return PublishResult(success=False, error=f"No video ID in YouTube response: {video_data}")

            # Step 3: опционально устанавливаем thumbnail
            if platform_meta.get("thumbnail_media_id"):
                await self._set_thumbnail(client, headers, video_id, platform_meta["thumbnail_media_id"])

            return PublishResult(
                success=True,
                external_post_id=video_id,
                external_url=f"https://www.youtube.com/watch?v={video_id}",
            )

    async def _set_thumbnail(self, client, headers, video_id, thumbnail_media_id) -> None:
        img_bytes = await self._download_from_minio(thumbnail_media_id)
        if not img_bytes:
            return
        try:
            await client.post(
                f"{YT_UPLOAD}/thumbnails/set?videoId={video_id}&uploadType=media",
                headers={**headers, "Content-Type": "image/jpeg", "Content-Length": str(len(img_bytes))},
                content=img_bytes,
                timeout=60.0,
            )
        except Exception as e:
            logger.warning("Failed to set YouTube thumbnail: %s", e)

    async def delete_post(self, external_post_id: str, account) -> bool:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(
                f"{YT_API}/videos?id={external_post_id}",
                headers={"Authorization": f"Bearer {account.access_token}"},
            )
            return resp.status_code == 204

    async def get_metrics(self, external_post_id: str, account) -> Metrics:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{YT_API}/videos",
                headers={"Authorization": f"Bearer {account.access_token}"},
                params={
                    "id": external_post_id,
                    "part": "statistics",
                },
            )
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return Metrics()

            stats = items[0].get("statistics", {})
            return Metrics(
                views=int(stats.get("viewCount", 0)),
                likes=int(stats.get("likeCount", 0)),
                comments=int(stats.get("commentCount", 0)),
                shares=0,  # YouTube API не возвращает shares публично
            )

    async def validate_content(self, post) -> ValidationResult:
        errors = []
        platform_meta = post.platform_meta or {}

        description = self._build_description(post)
        title = platform_meta.get("title") or post.body[:MAX_TITLE].strip().split("\n")[0]

        if not title:
            errors.append("YouTube видео требует заголовок")

        if len(title) > MAX_TITLE:
            errors.append(f"Заголовок слишком длинный: {len(title)} (лимит {MAX_TITLE})")

        if len(description) > MAX_DESCRIPTION:
            errors.append(f"Описание слишком длинное: {len(description)} (лимит {MAX_DESCRIPTION})")

        if not post.media_ids:
            errors.append("YouTube требует видео файл")

        return ValidationResult(valid=not errors, errors=errors)

    async def refresh_token(self, account):
        """Обновляет Google OAuth токен через refresh_token."""
        from ..config import settings
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "refresh_token": account.platform_meta.get("refresh_token", ""),
                    "grant_type": "refresh_token",
                },
            )
            data = resp.json()
            if "access_token" in data:
                from datetime import datetime, timezone, timedelta
                account.access_token = data["access_token"]
                account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=data.get("expires_in", 3600)
                )
        return account

    async def validate_account(self, account) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{YT_API}/channels?part=id&mine=true",
                headers={"Authorization": f"Bearer {account.access_token}"},
            )
            data = resp.json()
            return bool(data.get("items"))

    def _build_description(self, post) -> str:
        """Собирает description: body + timecodes из platform_meta."""
        platform_meta = post.platform_meta or {}
        parts = [post.body or ""]

        timecodes = platform_meta.get("timecodes", [])
        if timecodes:
            parts.append("\n\n⏱ Таймкоды:")
            for tc in timecodes:
                parts.append(f"\n{tc.get('time', '')} — {tc.get('title', '')}")

        if post.hashtags:
            parts.append("\n\n" + " ".join(f"#{t.lstrip('#')}" for t in post.hashtags))

        return "".join(parts)

    async def _download_from_minio(self, media_id: str) -> bytes | None:
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
