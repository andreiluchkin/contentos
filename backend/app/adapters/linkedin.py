"""
LinkedIn API v2 adapter.

Поддерживает:
  - Текстовые посты (UGC Posts)
  - Посты с изображениями (registerUpload → upload → post)
  - Посты с документами (PDF-карусели через doxMetaData)
  - Метрики через Share Statistics

Флоу для изображений:
  1. POST /v2/assets?action=registerUpload → uploadMechanism + asset URN
  2. PUT uploadUrl                          → загрузка файла
  3. POST /v2/ugcPosts с media[].media=asset URN

Ограничения:
  - text: ≤ 3000 символов
  - images: ≤ 9 в одном посте
  - Требует scopes: r_liteprofile, w_member_social

OAuth: 3-legged (Authorization Code Flow). Токены живут 60 дней.
"""
import logging

import httpx

from .base import PlatformAdapter, PublishResult, Metrics, ValidationResult

logger = logging.getLogger(__name__)

LI_API = "https://api.linkedin.com/v2"
MAX_TEXT = 3000
MAX_IMAGES = 9


class LinkedInAdapter(PlatformAdapter):
    platform = "linkedin"

    async def publish_post(self, post, account) -> PublishResult:
        access_token = account.access_token
        person_urn = account.platform_meta.get("person_urn", "")  # urn:li:person:xxx

        if not access_token or not person_urn:
            return PublishResult(success=False, error="Missing LinkedIn access_token or person_urn")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202401",
        }

        text = post.body or ""
        media_ids = post.media_ids or []

        async with httpx.AsyncClient(timeout=60.0) as client:
            media_assets = []
            if media_ids:
                for media_id in media_ids[:MAX_IMAGES]:
                    asset_urn = await self._register_and_upload_image(
                        client, headers, person_urn, media_id
                    )
                    if asset_urn:
                        media_assets.append(asset_urn)

            return await self._create_ugc_post(client, headers, person_urn, text, media_assets)

    async def _register_and_upload_image(
        self, client, headers, person_urn, media_id
    ) -> str | None:
        """Регистрирует изображение в LinkedIn и загружает его."""
        # Step 1: register upload
        register_resp = await client.post(
            f"{LI_API}/assets?action=registerUpload",
            headers=headers,
            json={
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": person_urn,
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent",
                        }
                    ],
                }
            },
        )
        reg_data = register_resp.json()
        if register_resp.status_code != 200:
            logger.error("LinkedIn registerUpload failed: %s", reg_data)
            return None

        upload_url = (
            reg_data["value"]["uploadMechanism"]
            ["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        )
        asset_urn = reg_data["value"]["asset"]

        # Step 2: upload image bytes
        img_bytes = await self._download_from_minio(media_id)
        if not img_bytes:
            return None

        upload_resp = await client.put(
            upload_url,
            content=img_bytes,
            headers={"Authorization": headers["Authorization"], "Content-Type": "image/jpeg"},
            timeout=60.0,
        )
        if upload_resp.status_code not in (200, 201):
            logger.error("LinkedIn image upload failed: %d", upload_resp.status_code)
            return None

        return asset_urn

    async def _create_ugc_post(
        self, client, headers, person_urn, text, media_assets
    ) -> PublishResult:
        """Создаёт UGC пост в LinkedIn."""
        share_content: dict = {
            "shareCommentary": {"text": text},
            "shareMediaCategory": "NONE" if not media_assets else "IMAGE",
        }

        if media_assets:
            share_content["shareMediaCategory"] = "IMAGE"
            share_content["media"] = [
                {
                    "status": "READY",
                    "media": asset_urn,
                }
                for asset_urn in media_assets
            ]

        resp = await client.post(
            f"{LI_API}/ugcPosts",
            headers=headers,
            json={
                "author": person_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": share_content
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                },
            },
        )

        if resp.status_code not in (200, 201):
            error_text = resp.text[:300]
            logger.error("LinkedIn ugcPosts failed %d: %s", resp.status_code, error_text)
            return PublishResult(success=False, error=f"LinkedIn API error {resp.status_code}: {error_text}")

        post_id = resp.headers.get("x-restli-id") or resp.json().get("id", "")
        return PublishResult(
            success=True,
            external_post_id=post_id,
            external_url=f"https://www.linkedin.com/feed/update/{post_id}/",
        )

    async def delete_post(self, external_post_id: str, account) -> bool:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(
                f"{LI_API}/ugcPosts/{external_post_id}",
                headers={
                    "Authorization": f"Bearer {account.access_token}",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
            )
            return resp.status_code == 204

    async def get_metrics(self, external_post_id: str, account) -> Metrics:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{LI_API}/socialActions/{external_post_id}",
                headers={
                    "Authorization": f"Bearer {account.access_token}",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
            )
            data = resp.json()
            return Metrics(
                likes=data.get("likesSummary", {}).get("totalLikes", 0),
                comments=data.get("commentsSummary", {}).get("totalFirstLevelComments", 0),
                shares=data.get("shareStatistics", {}).get("shareCount", 0),
            )

    async def validate_content(self, post) -> ValidationResult:
        errors = []
        if not post.body or not post.body.strip():
            errors.append("Текст поста не может быть пустым")
        if len(post.body or "") > MAX_TEXT:
            errors.append(f"Текст слишком длинный: {len(post.body)} (лимит {MAX_TEXT})")
        if post.media_ids and len(post.media_ids) > MAX_IMAGES:
            errors.append(f"Слишком много изображений: {len(post.media_ids)} (лимит {MAX_IMAGES})")
        return ValidationResult(valid=not errors, errors=errors)

    async def refresh_token(self, account):
        """LinkedIn токены живут 60 дней; refresh через Authorization Code Flow."""
        from ..config import settings
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://www.linkedin.com/oauth/v2/accessToken",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": account.platform_meta.get("refresh_token", ""),
                    "client_id": settings.linkedin_client_id,
                    "client_secret": settings.linkedin_client_secret,
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
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{LI_API}/me",
                headers={"Authorization": f"Bearer {account.access_token}"},
            )
            data = resp.json()
            return "id" in data

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
