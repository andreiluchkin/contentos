"""
X (Twitter) API v2 adapter.

Поддерживает:
  - Одиночные твиты с текстом
  - Треды (thread): массив текстов в platform_meta.thread[]
  - Медиа: upload через v1.1 (chunked), attach к твиту через v2
  - Метрики через tweet.fields=public_metrics

Флоу с медиа:
  1. POST /1.1/media/upload (INIT)   → media_id_string
  2. POST /1.1/media/upload (APPEND) → чанки по 5 MB
  3. POST /1.1/media/upload (FINALIZE)
  4. POST /2/tweets {media: {media_ids: [...]}}

Тред:
  - Первый твит публикуется обычно
  - Каждый следующий: reply_to = предыдущий tweet_id

Ограничения:
  - Текст: ≤ 280 символов (с медиа URL занимает 23 символа)
  - Медиа: ≤ 4 изображения или 1 GIF или 1 видео
  - Тред: ≤ 25 твитов

Требует: OAuth 2.0 User Context или OAuth 1.0a с user tokens.
"""
import logging

import httpx

from .base import PlatformAdapter, PublishResult, Metrics, ValidationResult

logger = logging.getLogger(__name__)

X_API_V2 = "https://api.twitter.com/2"
X_API_V1 = "https://upload.twitter.com/1.1"

MAX_TWEET_LENGTH = 280
MAX_THREAD_LENGTH = 25
MAX_IMAGES = 4
MEDIA_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB


class XAdapter(PlatformAdapter):
    platform = "x"

    async def publish_post(self, post, account) -> PublishResult:
        access_token = account.access_token
        if not access_token:
            return PublishResult(success=False, error="Missing X access_token")

        platform_meta = post.platform_meta or {}
        thread_texts: list[str] = platform_meta.get("thread", [])
        media_ids = post.media_ids or []

        # Если есть тред — публикуем тред, иначе одиночный твит
        if thread_texts:
            texts = thread_texts[:MAX_THREAD_LENGTH]
        else:
            texts = [post.body or ""]

        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {"Authorization": f"Bearer {access_token}"}

            # Загружаем медиа (только к первому твиту)
            x_media_ids = []
            if media_ids:
                for media_id in media_ids[:MAX_IMAGES]:
                    x_media_id = await self._upload_media(client, headers, media_id)
                    if x_media_id:
                        x_media_ids.append(x_media_id)

            return await self._post_thread(client, headers, texts, x_media_ids)

    async def _post_thread(
        self, client, headers, texts: list[str], media_ids: list[str]
    ) -> PublishResult:
        """Публикует твит или цепочку твитов."""
        first_tweet_id = None
        prev_tweet_id = None

        for i, text in enumerate(texts):
            payload: dict = {"text": text[:MAX_TWEET_LENGTH]}

            # Медиа только к первому твиту
            if i == 0 and media_ids:
                payload["media"] = {"media_ids": media_ids}

            # Reply для треда
            if prev_tweet_id:
                payload["reply"] = {"in_reply_to_tweet_id": prev_tweet_id}

            resp = await client.post(
                f"{X_API_V2}/tweets",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
            )
            data = resp.json()

            if resp.status_code not in (200, 201):
                error = data.get("detail") or data.get("errors", [{}])[0].get("message", str(data))
                return PublishResult(success=False, error=f"X API error: {error}")

            tweet_id = data["data"]["id"]
            if i == 0:
                first_tweet_id = tweet_id
            prev_tweet_id = tweet_id

        if not first_tweet_id:
            return PublishResult(success=False, error="No tweets published")

        username = "i"
        return PublishResult(
            success=True,
            external_post_id=first_tweet_id,
            external_url=f"https://x.com/{username}/status/{first_tweet_id}",
        )

    async def _upload_media(self, client, headers, media_id: str) -> str | None:
        """Загружает медиафайл через chunked upload API v1.1."""
        img_bytes = await self._download_from_minio(media_id)
        if not img_bytes:
            return None

        file_size = len(img_bytes)
        # Определяем тип из размера (упрощённо — все как JPEG)
        # В production: хранить mime_type в MediaFile
        media_type = "image/jpeg"
        media_category = "tweet_image"

        upload_headers = {
            "Authorization": headers["Authorization"],
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # INIT
        init_resp = await client.post(
            f"{X_API_V1}/media/upload.json",
            headers=upload_headers,
            data={
                "command": "INIT",
                "total_bytes": str(file_size),
                "media_type": media_type,
                "media_category": media_category,
            },
        )
        if init_resp.status_code != 202:
            logger.error("X media INIT failed: %d %s", init_resp.status_code, init_resp.text[:200])
            return None

        x_media_id = init_resp.json()["media_id_string"]

        # APPEND (chunks)
        segment = 0
        offset = 0
        while offset < file_size:
            chunk = img_bytes[offset:offset + MEDIA_CHUNK_SIZE]
            append_resp = await client.post(
                f"{X_API_V1}/media/upload.json",
                headers={"Authorization": headers["Authorization"]},
                data={
                    "command": "APPEND",
                    "media_id": x_media_id,
                    "segment_index": str(segment),
                },
                files={"media": ("chunk", chunk, media_type)},
            )
            if append_resp.status_code != 204:
                logger.error("X media APPEND failed: %d", append_resp.status_code)
                return None
            offset += MEDIA_CHUNK_SIZE
            segment += 1

        # FINALIZE
        fin_resp = await client.post(
            f"{X_API_V1}/media/upload.json",
            headers=upload_headers,
            data={"command": "FINALIZE", "media_id": x_media_id},
        )
        if fin_resp.status_code not in (200, 201):
            logger.error("X media FINALIZE failed: %d", fin_resp.status_code)
            return None

        return x_media_id

    async def delete_post(self, external_post_id: str, account) -> bool:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(
                f"{X_API_V2}/tweets/{external_post_id}",
                headers={"Authorization": f"Bearer {account.access_token}"},
            )
            data = resp.json()
            return data.get("data", {}).get("deleted", False)

    async def get_metrics(self, external_post_id: str, account) -> Metrics:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{X_API_V2}/tweets/{external_post_id}",
                headers={"Authorization": f"Bearer {account.access_token}"},
                params={"tweet.fields": "public_metrics"},
            )
            data = resp.json()
            m = data.get("data", {}).get("public_metrics", {})
            return Metrics(
                views=m.get("impression_count", 0),
                likes=m.get("like_count", 0),
                comments=m.get("reply_count", 0),
                shares=m.get("retweet_count", 0),
            )

    async def validate_content(self, post) -> ValidationResult:
        errors = []
        platform_meta = post.platform_meta or {}
        thread_texts = platform_meta.get("thread", [])

        if thread_texts:
            for i, t in enumerate(thread_texts):
                if len(t) > MAX_TWEET_LENGTH:
                    errors.append(f"Твит #{i+1} слишком длинный: {len(t)} символов (лимит {MAX_TWEET_LENGTH})")
            if len(thread_texts) > MAX_THREAD_LENGTH:
                errors.append(f"Тред слишком длинный: {len(thread_texts)} твитов (лимит {MAX_THREAD_LENGTH})")
        else:
            if not post.body or not post.body.strip():
                errors.append("Текст твита не может быть пустым")
            if len(post.body or "") > MAX_TWEET_LENGTH:
                errors.append(f"Текст слишком длинный: {len(post.body)} символов (лимит {MAX_TWEET_LENGTH})")

        if post.media_ids and len(post.media_ids) > MAX_IMAGES:
            errors.append(f"Слишком много медиафайлов: {len(post.media_ids)} (лимит {MAX_IMAGES})")

        return ValidationResult(valid=not errors, errors=errors)

    async def refresh_token(self, account):
        """OAuth 2.0 PKCE refresh."""
        from ..config import settings
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.twitter.com/2/oauth2/token",
                auth=(settings.x_client_id, settings.x_client_secret),
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": account.platform_meta.get("refresh_token", ""),
                },
            )
            data = resp.json()
            if "access_token" in data:
                from datetime import datetime, timezone, timedelta
                account.access_token = data["access_token"]
                account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=data.get("expires_in", 7200)
                )
                meta = dict(account.platform_meta or {})
                meta["refresh_token"] = data.get("refresh_token", meta.get("refresh_token", ""))
                account.platform_meta = meta
        return account

    async def validate_account(self, account) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{X_API_V2}/users/me",
                headers={"Authorization": f"Bearer {account.access_token}"},
            )
            return "data" in resp.json()

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
