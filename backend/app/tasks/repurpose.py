"""
Repurpose Engine Celery tasks.

Пайплайн:
  1. transcribe_media(job_id)   — Whisper (OpenAI) → transcription
  2. extract_ideas(job_id)      — Claude → extracted_ideas[]
  3. create_repurpose_posts(job_id, account_id, platforms, content_type)
     → создаёт Post записи → generate_post.delay() на каждую

YouTube URL → yt-dlp скачивает аудио → transcribe_media

source_type=text пропускает шаг транскрипции, сразу extract_ideas.
"""
import asyncio
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone

from celery import chain

from .celery_app import app

logger = logging.getLogger(__name__)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ─── шаг 1: транскрипция ─────────────────────────────────────────────────────

@app.task(bind=True, max_retries=2, default_retry_delay=60, name="app.tasks.repurpose.transcribe_media")
def transcribe_media(self, job_id: str):
    """Транскрибирует медиафайл через OpenAI Whisper."""
    return run_async(_transcribe_media(self, job_id))


async def _transcribe_media(task, job_id: str):
    from ..database import AsyncSessionLocal as _session_factory
    from sqlalchemy.ext.asyncio import AsyncSession
    from ..models import RepurposeJob, MediaFile

    async with _session_factory() as db:
        job = await db.get(RepurposeJob, uuid.UUID(job_id))
        if not job:
            logger.error("RepurposeJob %s not found", job_id)
            return

        job.status = "transcribing"
        await db.commit()

        try:
            if job.source_type == "text":
                # Нет файла — текст уже есть в source_text
                job.transcription = job.source_text or ""
                job.status = "transcribed"
                await db.commit()
                return job_id

            if job.source_type == "youtube_url":
                transcription = await _transcribe_youtube(job.source_youtube_url)
            else:
                # voice_note / video_file → берём из MinIO
                media = await db.get(MediaFile, job.source_media_id)
                if not media:
                    raise ValueError(f"MediaFile {job.source_media_id} not found")
                transcription = await _transcribe_file_from_minio(media.storage_key, media.mime_type)

            job.transcription = transcription
            job.status = "transcribed"
            await db.commit()
            return job_id

        except Exception as e:
            logger.exception("Transcription failed for job %s", job_id)
            job.status = "error"
            job.error = str(e)
            await db.commit()
            raise task.retry(exc=e)


async def _transcribe_youtube(url: str) -> str:
    """yt-dlp скачивает аудио, Whisper транскрибирует."""
    import subprocess
    import openai

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "audio.mp3")
        result = subprocess.run(
            [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "5",
                "-o", out_path,
                url,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed: {result.stderr[:500]}")

        if not os.path.exists(out_path):
            # yt-dlp добавляет расширение
            candidates = [f for f in os.listdir(tmpdir) if f.endswith(".mp3")]
            if not candidates:
                raise RuntimeError("yt-dlp did not produce an audio file")
            out_path = os.path.join(tmpdir, candidates[0])

        from ..config import settings
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        with open(out_path, "rb") as f:
            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="ru",
            )
        return response.text


async def _transcribe_file_from_minio(storage_key: str, mime_type: str) -> str:
    """Скачивает файл из MinIO и транскрибирует через Whisper."""
    import boto3
    import openai
    from botocore.config import Config
    from ..config import settings

    s3 = boto3.client(
        "s3",
        endpoint_url=f"http{'s' if settings.minio_secure else ''}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
    )

    with tempfile.NamedTemporaryFile(suffix=_ext_from_mime(mime_type), delete=False) as tmp:
        tmp_path = tmp.name
        s3.download_fileobj(settings.minio_bucket, storage_key, tmp)

    try:
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        with open(tmp_path, "rb") as f:
            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="ru",
            )
        return response.text
    finally:
        os.unlink(tmp_path)


def _ext_from_mime(mime_type: str) -> str:
    mapping = {
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/ogg": ".ogg",
        "audio/wav": ".wav",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
    }
    return mapping.get(mime_type, ".bin")


# ─── шаг 2: извлечение идей ──────────────────────────────────────────────────

@app.task(bind=True, max_retries=2, default_retry_delay=30, name="app.tasks.repurpose.extract_ideas")
def extract_ideas(self, job_id: str):
    """Claude извлекает идеи для постов из транскрипции."""
    return run_async(_extract_ideas(self, job_id))


EXTRACT_PROMPT = """Ты — редактор контента. Тебе дана расшифровка голосовой заметки или видео.
Извлеки из неё 3-7 отдельных идей для постов в социальных сетях.

Для каждой идеи верни JSON-объект с полями:
- title: заголовок идеи (до 100 символов)
- context: суть идеи, что именно рассказать (2-4 предложения)
- suggested_content_type: один из [case, breakdown, how_to, opinion, roundup, story, observation, mistake, lesson, launch]

Верни ТОЛЬКО JSON-массив без markdown-обёртки.

Расшифровка:
{transcription}"""


async def _extract_ideas(task, job_id: str):
    import json
    import anthropic
    from ..database import AsyncSessionLocal as _session_factory
    from ..models import RepurposeJob
    from ..config import settings

    async with _session_factory() as db:
        job = await db.get(RepurposeJob, uuid.UUID(job_id))
        if not job:
            return

        job.status = "extracting"
        await db.commit()

        try:
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            message = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": EXTRACT_PROMPT.format(transcription=job.transcription or ""),
                }],
            )
            raw = message.content[0].text.strip()

            # Убираем возможную markdown-обёртку
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

            ideas = json.loads(raw)
            job.extracted_ideas = ideas
            job.status = "done"
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return job_id

        except Exception as e:
            logger.exception("Idea extraction failed for job %s", job_id)
            job.status = "error"
            job.error = str(e)
            await db.commit()
            raise task.retry(exc=e)


# ─── шаг 3: создание постов из идей ─────────────────────────────────────────

@app.task(bind=True, name="app.tasks.repurpose.create_posts_from_job")
def create_posts_from_job(
    self,
    job_id: str,
    account_id: str,
    platform: str,
    content_type: str,
    idea_indices: list[int] | None = None,
):
    """
    Создаёт Post записи из extracted_ideas репёрпоуз-джоба.
    idea_indices=None → создаём посты для всех идей.
    Запускает generate_post.delay() на каждый.
    """
    return run_async(_create_posts_from_job(job_id, account_id, platform, content_type, idea_indices))


async def _create_posts_from_job(job_id, account_id, platform, content_type, idea_indices):
    import uuid as _uuid
    from ..database import AsyncSessionLocal as _session_factory
    from ..models import RepurposeJob, Post
    from .generation import generate_post

    async with _session_factory() as db:
        job = await db.get(RepurposeJob, _uuid.UUID(job_id))
        if not job or not job.extracted_ideas:
            return []

        ideas = job.extracted_ideas
        if idea_indices is not None:
            ideas = [ideas[i] for i in idea_indices if 0 <= i < len(ideas)]

        post_ids = []
        for idea in ideas:
            post = Post(
                account_id=_uuid.UUID(account_id),
                platform=platform,
                content_type=idea.get("suggested_content_type", content_type),
                status="idea_approved",
                repurpose_job_id=_uuid.UUID(job_id),
                platform_meta={
                    "repurpose_title": idea.get("title", ""),
                    "repurpose_context": idea.get("context", ""),
                },
            )
            db.add(post)
            await db.flush()
            post_ids.append(str(post.id))

        await db.commit()

        for pid in post_ids:
            generate_post.delay(pid)

        return post_ids


# ─── утилита: полный пайплайн одной цепочкой ─────────────────────────────────

def run_repurpose_pipeline(job_id: str):
    """Запускает transcribe → extract_ideas цепочкой Celery."""
    return chain(
        transcribe_media.s(job_id),
        extract_ideas.s(),
    ).apply_async()
