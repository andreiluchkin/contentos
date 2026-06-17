"""
Repurpose Engine API.

Endpoints:
  POST /repurpose/upload          — загрузить голосовую заметку/видео → запустить пайплайн
  POST /repurpose/youtube         — задать YouTube URL → запустить пайплайн
  POST /repurpose/text            — прямой текст → extract_ideas
  GET  /repurpose                 — список джобов
  GET  /repurpose/{id}            — статус + результаты джоба
  POST /repurpose/{id}/create-posts — создать посты из идей джоба
  DELETE /repurpose/{id}          — удалить джоб
"""
import uuid
import hashlib
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from ..auth import require_auth
from ..database import get_db
from ..models import RepurposeJob, MediaFile

router = APIRouter(prefix="/repurpose", tags=["repurpose"])

ALLOWED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/mp4", "audio/m4a",
    "audio/ogg", "audio/wav", "audio/webm", "audio/aac",
}
ALLOWED_VIDEO_TYPES = {
    "video/mp4", "video/quicktime", "video/webm", "video/mpeg",
}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB


# ── Schemas ──────────────────────────────────────────────────────────────────

class RepurposeJobOut(BaseModel):
    id: uuid.UUID
    source_type: str
    source_youtube_url: str | None
    transcription: str | None
    extracted_ideas: list
    status: str
    error: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class YoutubeRepurposeRequest(BaseModel):
    url: str = Field(..., description="YouTube URL")


class TextRepurposeRequest(BaseModel):
    text: str = Field(..., min_length=50, description="Исходный текст для извлечения идей")


class CreatePostsRequest(BaseModel):
    account_id: uuid.UUID
    platform: str = Field(..., description="telegram|instagram|linkedin|x|tiktok|youtube")
    content_type: str = Field("story", description="Тип контента для созданных постов")
    idea_indices: list[int] | None = Field(None, description="Индексы идей (None = все)")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=RepurposeJobOut, status_code=201, dependencies=[Depends(require_auth)])
async def upload_media(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Загружает голосовую заметку или видео, запускает транскрипцию."""
    mime = file.content_type or ""
    is_audio = mime in ALLOWED_AUDIO_TYPES or mime.startswith("audio/")
    is_video = mime in ALLOWED_VIDEO_TYPES or mime.startswith("video/")

    if not is_audio and not is_video:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type: {mime}. Allowed: audio/* or video/*",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 200 MB)")

    # Загружаем в MinIO
    storage_key = await _upload_to_minio(content, file.filename or "upload", mime)

    media = MediaFile(
        filename=file.filename or "upload",
        media_type="audio" if is_audio else "video",
        storage_key=storage_key,
        size_bytes=len(content),
        mime_type=mime,
        transcription_status="pending",
    )
    db.add(media)
    await db.flush()

    source_type = "voice_note" if is_audio else "video_file"
    job = RepurposeJob(
        source_type=source_type,
        source_media_id=media.id,
        status="pending",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Запускаем пайплайн
    from ..tasks.repurpose import run_repurpose_pipeline
    run_repurpose_pipeline(str(job.id))

    return job


@router.post("/youtube", response_model=RepurposeJobOut, status_code=201, dependencies=[Depends(require_auth)])
async def repurpose_youtube(data: YoutubeRepurposeRequest, db: AsyncSession = Depends(get_db)):
    """Запускает транскрипцию YouTube видео."""
    if "youtube.com" not in data.url and "youtu.be" not in data.url:
        raise HTTPException(status_code=400, detail="Not a valid YouTube URL")

    job = RepurposeJob(
        source_type="youtube_url",
        source_youtube_url=data.url,
        status="pending",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    from ..tasks.repurpose import run_repurpose_pipeline
    run_repurpose_pipeline(str(job.id))

    return job


@router.post("/text", response_model=RepurposeJobOut, status_code=201, dependencies=[Depends(require_auth)])
async def repurpose_text(data: TextRepurposeRequest, db: AsyncSession = Depends(get_db)):
    """Извлекает идеи из готового текста без транскрипции."""
    job = RepurposeJob(
        source_type="text",
        source_text=data.text,
        transcription=data.text,
        status="transcribed",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Пропускаем транскрипцию, сразу к извлечению
    from ..tasks.repurpose import extract_ideas
    extract_ideas.delay(str(job.id))

    return job


@router.get("", response_model=list[RepurposeJobOut], dependencies=[Depends(require_auth)])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RepurposeJob).order_by(desc(RepurposeJob.created_at)).limit(50)
    )
    return result.scalars().all()


@router.get("/{job_id}", response_model=RepurposeJobOut, dependencies=[Depends(require_auth)])
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(RepurposeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/create-posts", dependencies=[Depends(require_auth)])
async def create_posts(
    job_id: uuid.UUID,
    data: CreatePostsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Создаёт посты из идей джоба и запускает генерацию для каждого."""
    job = await db.get(RepurposeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "done":
        raise HTTPException(status_code=409, detail=f"Job not ready (status: {job.status})")
    if not job.extracted_ideas:
        raise HTTPException(status_code=409, detail="No ideas extracted yet")

    from ..tasks.repurpose import create_posts_from_job
    task = create_posts_from_job.delay(
        str(job_id),
        str(data.account_id),
        data.platform,
        data.content_type,
        data.idea_indices,
    )
    return {"status": "queued", "celery_task_id": task.id}


@router.delete("/{job_id}", status_code=204, dependencies=[Depends(require_auth)])
async def delete_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(RepurposeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.delete(job)
    await db.commit()


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _upload_to_minio(content: bytes, filename: str, mime_type: str) -> str:
    """Загружает файл в MinIO, возвращает storage_key."""
    import boto3
    from botocore.config import Config
    from ..config import settings

    # Уникальный ключ на основе хэша содержимого
    sha = hashlib.sha256(content).hexdigest()[:16]
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    storage_key = f"repurpose/{sha}.{ext}"

    s3 = boto3.client(
        "s3",
        endpoint_url=f"http{'s' if settings.minio_secure else ''}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
    )
    s3.upload_fileobj(
        io.BytesIO(content),
        settings.minio_bucket,
        storage_key,
        ExtraArgs={"ContentType": mime_type},
    )
    return storage_key
