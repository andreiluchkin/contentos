"""
Media Upload API.

Endpoints:
  POST /media/upload        — загрузить файл в MinIO, вернуть MediaFile
  GET  /media               — список медиафайлов
  GET  /media/{id}          — мета + presigned URL
  DELETE /media/{id}        — удалить из MinIO + БД

Presigned URL живёт 1 час. Фронтенд использует его напрямую для показа.
Поддерживаемые типы: image/*, video/*, audio/*
"""
import hashlib
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_auth
from ..database import get_db
from ..models import MediaFile

router = APIRouter(prefix="/media", tags=["media"])

MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
ALLOWED_PREFIXES = ("image/", "video/", "audio/")


class MediaFileOut(BaseModel):
    id: uuid.UUID
    filename: str
    media_type: str
    mime_type: str
    size_bytes: int
    duration_seconds: float | None
    width: int | None
    height: int | None
    presigned_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/upload", response_model=MediaFileOut, status_code=201, dependencies=[Depends(require_auth)])
async def upload_media(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    mime = file.content_type or "application/octet-stream"
    if not any(mime.startswith(p) for p in ALLOWED_PREFIXES):
        raise HTTPException(status_code=415, detail=f"Unsupported media type: {mime}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 500 MB)")

    # Уникальный ключ через SHA256
    sha = hashlib.sha256(content).hexdigest()[:24]
    orig_name = file.filename or "upload"
    ext = orig_name.rsplit(".", 1)[-1].lower() if "." in orig_name else "bin"
    storage_key = f"originals/{sha}.{ext}"

    # Определяем media_type
    if mime.startswith("image/"):
        media_type = "image"
    elif mime.startswith("video/"):
        media_type = "video"
    else:
        media_type = "audio"

    # Размеры изображения
    width = height = None
    if media_type == "image":
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(content))
            width, height = img.size
        except Exception:
            pass

    # Загружаем в MinIO
    from ..config import settings
    import boto3
    from botocore.config import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=f"http{'s' if settings.minio_secure else ''}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
    )

    # Проверяем не загружен ли уже (idempotent по SHA256)
    existing_result = await db.execute(
        select(MediaFile).where(MediaFile.storage_key == storage_key)
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        url = _presigned_url(s3, settings.minio_bucket, storage_key)
        out = MediaFileOut.model_validate(existing)
        out.presigned_url = url
        return out

    s3.upload_fileobj(
        io.BytesIO(content),
        settings.minio_bucket,
        storage_key,
        ExtraArgs={"ContentType": mime},
    )

    media = MediaFile(
        filename=orig_name,
        media_type=media_type,
        storage_key=storage_key,
        size_bytes=len(content),
        mime_type=mime,
        width=width,
        height=height,
    )
    db.add(media)
    await db.commit()
    await db.refresh(media)

    url = _presigned_url(s3, settings.minio_bucket, storage_key)
    out = MediaFileOut.model_validate(media)
    out.presigned_url = url
    return out


@router.get("", response_model=list[MediaFileOut], dependencies=[Depends(require_auth)])
async def list_media(
    media_type: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    q = select(MediaFile).order_by(desc(MediaFile.created_at)).limit(min(limit, 200))
    if media_type:
        q = q.where(MediaFile.media_type == media_type)
    result = await db.execute(q)
    items = result.scalars().all()

    from ..config import settings
    import boto3
    from botocore.config import Config
    s3 = boto3.client(
        "s3",
        endpoint_url=f"http{'s' if settings.minio_secure else ''}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
    )
    out = []
    for item in items:
        o = MediaFileOut.model_validate(item)
        o.presigned_url = _presigned_url(s3, settings.minio_bucket, item.storage_key)
        out.append(o)
    return out


@router.get("/{media_id}", response_model=MediaFileOut, dependencies=[Depends(require_auth)])
async def get_media(media_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    media = await db.get(MediaFile, media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    from ..config import settings
    import boto3
    from botocore.config import Config
    s3 = boto3.client(
        "s3",
        endpoint_url=f"http{'s' if settings.minio_secure else ''}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
    )
    out = MediaFileOut.model_validate(media)
    out.presigned_url = _presigned_url(s3, settings.minio_bucket, media.storage_key)
    return out


@router.delete("/{media_id}", status_code=204, dependencies=[Depends(require_auth)])
async def delete_media(media_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    media = await db.get(MediaFile, media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    from ..config import settings
    import boto3
    from botocore.config import Config
    s3 = boto3.client(
        "s3",
        endpoint_url=f"http{'s' if settings.minio_secure else ''}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
    )
    try:
        s3.delete_object(Bucket=settings.minio_bucket, Key=media.storage_key)
    except Exception:
        pass

    await db.delete(media)
    await db.commit()


def _presigned_url(s3_client, bucket: str, key: str, expires: int = 3600) -> str:
    try:
        return s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )
    except Exception:
        return ""
