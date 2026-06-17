# ContentOS — Полная техническая спецификация

> Версия: 1.0 · Дата: 2026-06-17
> Источники: PRODUCT.md v2.0, PLAN.md v1.0
> Статус: Ready for implementation

---

## 0. Структура проекта

```
contentos/
├── backend/                    # FastAPI приложение
│   ├── app/
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── config.py           # Settings (pydantic-settings)
│   │   ├── database.py         # SQLAlchemy async engine
│   │   ├── models/             # SQLAlchemy ORM модели
│   │   ├── schemas/            # Pydantic schemas (request/response)
│   │   ├── api/                # FastAPI routers
│   │   ├── services/           # Business logic
│   │   ├── adapters/           # Platform adapters (Telegram, IG, etc.)
│   │   ├── tasks/              # Celery tasks
│   │   └── ai/                 # AI generation, Content Score
│   ├── alembic/                # Миграции БД
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                   # Next.js приложение
│   ├── app/                    # App Router pages
│   ├── components/             # UI компоненты
│   ├── lib/                    # API клиент, утилиты
│   ├── types/                  # TypeScript типы (из OpenAPI)
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── PRODUCT.md
├── PLAN.md
├── SPEC.md                     # этот файл
└── design/                     # Jitter дизайн-система
```

---

## 1. Модели данных

### 1.1 Enum типы

```python
# backend/app/models/enums.py

from enum import Enum

class PipelineStatus(str, Enum):
    INBOX = "inbox"
    IDEA_APPROVED = "idea_approved"
    DRAFT = "draft"
    REVIEW = "review"
    READY = "ready"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ERROR = "error"

class Platform(str, Enum):
    TELEGRAM = "telegram"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    LINKEDIN = "linkedin"
    X = "x"

class ContentType(str, Enum):
    CASE = "case"           # Кейс
    BREAKDOWN = "breakdown" # Разбор
    HOW_TO = "how_to"       # Инструкция
    OPINION = "opinion"     # Мнение
    ROUNDUP = "roundup"     # Подборка
    STORY = "story"         # История
    OBSERVATION = "observation" # Наблюдение
    MISTAKE = "mistake"     # Ошибка
    LESSON = "lesson"       # Урок
    LAUNCH = "launch"       # Запуск продукта

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"

class RepurposeSourceType(str, Enum):
    VOICE_NOTE = "voice_note"
    VIDEO_FILE = "video_file"
    YOUTUBE_URL = "youtube_url"
    TEXT = "text"

class KBItemType(str, Enum):
    NOTE = "note"
    CASE = "case"
    POST = "post"
    DOCUMENT = "document"
```

### 1.2 ContentPillar

```python
# backend/app/models/pillar.py

class ContentPillar(Base):
    __tablename__ = "content_pillars"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)  # hex color, e.g. "#7a40ed"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relations
    ideas: Mapped[list["Idea"]] = relationship(back_populates="pillar")
    posts: Mapped[list["Post"]] = relationship(back_populates="pillar")
```

### 1.3 SocialAccount

```python
# backend/app/models/account.py

class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    platform: Mapped[Platform] = mapped_column(nullable=False)
    handle: Mapped[str] = mapped_column(String(255), nullable=False)  # @username или channel id
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # OAuth токены — зашифрованы в БД (Fernet)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Platform-specific данные (chat_id для Telegram, user_id для IG и т.д.)
    platform_meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    is_active: Mapped[bool] = mapped_column(default=True)
    last_token_refresh: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Оптимальное время постинга по дням недели
    # {"mon": "09:00", "tue": "09:00", ...}
    optimal_posting_times: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relations
    posts: Mapped[list["Post"]] = relationship(back_populates="account")

    __table_args__ = (
        UniqueConstraint("platform", "handle"),
    )
```

### 1.4 Idea

```python
# backend/app/models/idea.py

class Idea(Base):
    __tablename__ = "ideas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Контент идеи
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "reddit", "manual"

    # Suggested meta от источника
    suggested_platform: Mapped[Platform | None] = mapped_column(nullable=True)
    suggested_content_type: Mapped[ContentType | None] = mapped_column(nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0–1.0

    # Пиллар
    pillar_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_pillars.id"), nullable=True)

    # Статус
    status: Mapped[PipelineStatus] = mapped_column(default=PipelineStatus.INBOX)
    rejected_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Внешний источник
    external_source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("external_sources.id"), nullable=True)
    external_idea_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # ID в системе источника

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    pillar: Mapped["ContentPillar"] = relationship(back_populates="ideas")
    posts: Mapped[list["Post"]] = relationship(back_populates="idea")
    external_source: Mapped["ExternalSource | None"] = relationship()
```

### 1.5 Post

```python
# backend/app/models/post.py

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Связи
    idea_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ideas.id"), nullable=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("social_accounts.id"), nullable=False)
    pillar_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_pillars.id"), nullable=True)
    repurpose_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("repurpose_jobs.id"), nullable=True)

    # Контент
    platform: Mapped[Platform] = mapped_column(nullable=False)
    content_type: Mapped[ContentType] = mapped_column(nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)          # Основной текст
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    media_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)  # UUID медиафайлов

    # Platform-specific поля (хранятся в JSONB, структура зависит от платформы)
    platform_meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Telegram: {"parse_mode": "Markdown"}
    # Instagram: {"alt_text": "...", "location": null}
    # TikTok: {"script": "...", "hook": "...", "cta": "..."}
    # YouTube: {"title": "...", "description": "...", "tags": [...], "timecodes": [...]}
    # LinkedIn: {"article_url": null}
    # X: {"thread": ["tweet1", "tweet2"]}

    # Pipeline
    status: Mapped[PipelineStatus] = mapped_column(default=PipelineStatus.DRAFT)

    # Content Score
    content_score: Mapped[int | None] = mapped_column(Integer, nullable=True)       # 0–100
    score_hook: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_structure: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_readability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_cta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_platform_fit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_issues: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)    # Список проблем
    score_calculated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Расписание и публикация
    scheduled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    external_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # ID в соцсети
    publish_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_attempts: Mapped[int] = mapped_column(default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # История правок
    body_history: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    # [{"body": "...", "edited_at": "...", "score": 74}]

    # Заметки автора (не публикуются)
    author_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    idea: Mapped["Idea | None"] = relationship(back_populates="posts")
    account: Mapped["SocialAccount"] = relationship(back_populates="posts")
    pillar: Mapped["ContentPillar | None"] = relationship(back_populates="posts")
    repurpose_job: Mapped["RepurposeJob | None"] = relationship(back_populates="posts")

    # Индексы
    __table_args__ = (
        Index("idx_posts_status", "status"),
        Index("idx_posts_scheduled_at", "scheduled_at"),
        Index("idx_posts_platform", "platform"),
        Index("idx_posts_pillar_id", "pillar_id"),
    )
```

### 1.6 BrandVoice

```python
# backend/app/models/brand_voice.py

class BrandVoice(Base):
    __tablename__ = "brand_voice"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Стиль
    tone: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # "Прямой, без воды, с позицией. Говорю от первого лица."

    # Предпочтения по длине по платформам
    length_preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    # {"telegram": {"min": 800, "max": 1200}, "linkedin": {"min": 600, "max": 900}, ...}

    # Запрещённые слова и фразы
    forbidden_words: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    # ["синергия", "уникальный", "революционный", "инновация", "комплексный"]

    # Любимые конструкции
    preferred_patterns: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    # ["конкретные цифры", "личный опыт", "чёткая позиция"]

    # Эталонные посты — полный текст для обучения голосу
    example_posts: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    # [{"text": "...", "platform": "telegram", "content_score": 94, "added_at": "..."}]

    # Системный промпт, собранный из всех полей (кэш, регенерируется при изменении)
    system_prompt_cache: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 1.7 KnowledgeBaseItem

```python
# backend/app/models/knowledge_base.py

class KnowledgeBaseItem(Base):
    __tablename__ = "knowledge_base_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_type: Mapped[KBItemType] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Теги для поиска при генерации
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    # Векторный эмбеддинг для семантического поиска (pgvector)
    # Если pgvector не установлен — используем полнотекстовый поиск PG
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)

    pillar_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_pillars.id"), nullable=True)

    # Ссылка на оригинальный пост если это старый пост
    source_post_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("posts.id"), nullable=True)

    # Ссылка на медиафайл если это документ
    media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_files.id"), nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_kb_tags", "tags", postgresql_using="gin"),
        Index("idx_kb_type", "item_type"),
    )
```

### 1.8 MediaFile

```python
# backend/app/models/media.py

class MediaFile(Base):
    __tablename__ = "media_files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(nullable=False)

    # MinIO пути
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    # "originals/2026/06/17/<uuid>.mp4"
    thumbnail_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # "thumbnails/2026/06/17/<uuid>.jpg"

    # Метаданные файла
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)  # для видео/аудио
    width: Mapped[int | None] = mapped_column(nullable=True)
    height: Mapped[int | None] = mapped_column(nullable=True)

    # Транскрипция (для аудио/видео)
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcription_status: Mapped[str] = mapped_column(String(50), default="none")
    # "none" | "pending" | "processing" | "done" | "error"
    transcription_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Repurpose — был ли использован как источник
    repurpose_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("repurpose_jobs.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

### 1.9 RepurposeJob

```python
# backend/app/models/repurpose.py

class RepurposeJob(Base):
    __tablename__ = "repurpose_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_type: Mapped[RepurposeSourceType] = mapped_column(nullable=False)

    # Источник
    source_media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_files.id"), nullable=True)
    source_youtube_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Транскрипция
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Извлечённые ключевые мысли
    extracted_ideas: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    # [{"text": "...", "suggested_platform": "telegram", "suggested_type": "opinion", "index": 0}]

    # Статус обработки
    status: Mapped[str] = mapped_column(String(50), default="pending")
    # "pending" | "transcribing" | "extracting" | "done" | "error"
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relations
    source_media: Mapped["MediaFile | None"] = relationship()
    posts: Mapped[list["Post"]] = relationship(back_populates="repurpose_job")
```

### 1.10 ExternalSource

```python
# backend/app/models/external_source.py

class ExternalSource(Base):
    __tablename__ = "external_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # "reddit-project", "manual"
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # Хэш ключа для сравнения, сам ключ показывается только при создании

    # Webhook URL куда отправлять обратную связь
    feedback_webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True)
    last_idea_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ideas_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

### 1.11 ScheduleSlot (умное расписание)

```python
# backend/app/models/schedule.py

class ScheduleSlot(Base):
    """Хранит занятые слоты для умного планирования."""
    __tablename__ = "schedule_slots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("social_accounts.id"), nullable=False)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id"), nullable=False, unique=True)
    scheduled_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("account_id", "scheduled_at"),
        Index("idx_slots_account_date", "account_id", "scheduled_at"),
    )
```

---

## 2. API Endpoints

### 2.1 Базовая конфигурация

```
Base URL: http://localhost:8000
API prefix: /api/v1
Auth: Bearer token (JWT, single-user, token в .env)
Content-Type: application/json
```

Единственный пользователь — автор. Аутентификация через статический Bearer-токен из `.env`. Нет ролей, нет регистрации.

### 2.2 Inbox & Ideas

```
POST   /api/v1/inbox/idea              — Входящая идея от внешнего источника
GET    /api/v1/ideas                   — Список идей (фильтры: status, pillar_id, source)
GET    /api/v1/ideas/{id}              — Одна идея
PATCH  /api/v1/ideas/{id}/approve      — Одобрить идею
PATCH  /api/v1/ideas/{id}/reject       — Отклонить (body: {"reason": "..."})
POST   /api/v1/ideas/batch-approve     — Одобрить пачку (body: {"idea_ids": [...]})
DELETE /api/v1/ideas/{id}              — Удалить идею
```

**POST /api/v1/inbox/idea** — публичный endpoint (аутентификация по API-ключу источника):

```json
// Request
{
  "title": "Почему LLM-агенты плохо работают с долгосрочными задачами",
  "context": "DeepMind опубликовали исследование...",
  "source_url": "https://reddit.com/r/MachineLearning/...",
  "source_name": "reddit",
  "suggested_platform": "telegram",
  "suggested_content_type": "breakdown",
  "relevance_score": 0.87,
  "pillar": "AI",
  "external_idea_id": "reddit_post_abc123"
}

// Response 201
{
  "id": "uuid",
  "status": "inbox",
  "created_at": "2026-06-17T09:00:00Z"
}
```

**GET /api/v1/ideas** — query params:

```
status=inbox,idea_approved (comma-separated)
pillar_id=uuid
source_name=reddit
limit=50 (default 50, max 200)
offset=0
order_by=created_at_desc (default)
```

### 2.3 Posts (Content Pipeline)

```
POST   /api/v1/posts                    — Создать пост вручную
GET    /api/v1/posts                    — Backlog (фильтры ниже)
GET    /api/v1/posts/{id}               — Один пост
PATCH  /api/v1/posts/{id}               — Обновить тело/метаданные
DELETE /api/v1/posts/{id}               — Удалить

PATCH  /api/v1/posts/{id}/status        — Сменить статус
POST   /api/v1/posts/{id}/score         — Запросить Content Score
POST   /api/v1/posts/{id}/improve       — AI-улучшение по Score
PATCH  /api/v1/posts/{id}/schedule      — Назначить время
DELETE /api/v1/posts/{id}/schedule      — Снять со расписания

POST   /api/v1/posts/generate           — Сгенерировать пост из идеи
POST   /api/v1/posts/batch-generate     — Batch Mode: пачка из одобренных идей
POST   /api/v1/posts/{id}/duplicate     — Дублировать пост
GET    /api/v1/posts/{id}/history       — История правок
```

**GET /api/v1/posts** — query params:

```
status=draft,review,ready (comma-separated)
platform=telegram,instagram
pillar_id=uuid
content_type=case,opinion
account_id=uuid
scheduled_date=2026-06-17         (только посты на эту дату)
scheduled_week=2026-W25           (ISO week)
score_lt=80                       (для фильтра "низкое качество")
search=keyword                    (full-text по body)
limit=50
offset=0
order_by=created_at_desc|scheduled_at_asc
```

**POST /api/v1/posts/generate**:

```json
// Request
{
  "idea_id": "uuid",                  // опционально — берём из идеи
  "account_id": "uuid",
  "platform": "telegram",
  "content_type": "breakdown",
  "topic": "...",                      // если без idea_id
  "pillar_id": "uuid"
}

// Response 201 — пост в статусе draft
{
  "id": "uuid",
  "body": "...",
  "status": "draft",
  "platform": "telegram",
  "content_type": "breakdown"
}
```

**POST /api/v1/posts/batch-generate**:

```json
// Request
{
  "idea_ids": ["uuid1", "uuid2", "uuid3"]  // все должны быть idea_approved
}

// Response 202 — задача поставлена в очередь
{
  "task_id": "celery-task-uuid",
  "idea_count": 3,
  "estimated_seconds": 45
}
```

**POST /api/v1/posts/{id}/score**:

```json
// Response 200
{
  "content_score": 74,
  "score_hook": 88,
  "score_structure": 82,
  "score_readability": 70,
  "score_cta": 45,
  "score_platform_fit": 94,
  "score_issues": [
    "Нет CTA — непонятно что делать после прочтения",
    "Третий абзац слишком длинный — убери первые 2 предложения"
  ]
}
```

**PATCH /api/v1/posts/{id}/schedule**:

```json
// Request
{
  "scheduled_at": "2026-06-17T09:00:00Z"
}

// Validation:
// - scheduled_at должен быть в будущем
// - нет другого поста этого account_id в ±30 минут
```

### 2.4 Calendar

```
GET /api/v1/calendar/month              — Месячный вид
GET /api/v1/calendar/week               — Недельный вид
GET /api/v1/calendar/day/{date}         — Один день
GET /api/v1/calendar/gaps               — Дни без контента (текущая неделя)
GET /api/v1/calendar/next-slot          — Следующий свободный слот для платформы
```

**GET /api/v1/calendar/month**:

```
year=2026&month=6
platform=telegram,instagram (фильтр, опционально)
pillar_id=uuid (опционально)
```

```json
// Response
{
  "year": 2026,
  "month": 6,
  "days": {
    "2026-06-17": {
      "total": 3,
      "platforms": ["telegram", "instagram", "linkedin"],
      "pillars": [{"id": "uuid", "color": "#7a40ed", "count": 2}],
      "has_error": false
    },
    "2026-06-19": {
      "total": 0,
      "platforms": [],
      "is_gap": true
    }
  }
}
```

**GET /api/v1/calendar/next-slot**:

```
account_id=uuid
after=2026-06-17T12:00:00Z
```

```json
{
  "next_slot": "2026-06-17T19:00:00Z",
  "reason": "optimal_time"
}
```

### 2.5 AI Generation

```
POST /api/v1/ai/generate-post           — Прямая генерация
POST /api/v1/ai/improve-post            — Улучшение по Score
POST /api/v1/ai/score                   — Рассчитать Score без сохранения
POST /api/v1/ai/suggest-schedule        — Предложить расписание для пачки постов
```

**POST /api/v1/ai/generate-post**:

```json
// Request
{
  "topic": "...",
  "platform": "telegram",
  "content_type": "breakdown",
  "pillar_id": "uuid",
  "context": "...",              // доп. контекст
  "source_url": "..."           // опционально
}

// Response — streaming SSE или обычный JSON (настраивается через Accept)
{
  "body": "...",
  "platform_meta": {},
  "hashtags": []
}
```

**POST /api/v1/ai/improve-post**:

```json
// Request
{
  "post_id": "uuid",
  "score_issues": ["Нет CTA", "Длинное вступление"]  // какие именно улучшить
}

// Response
{
  "body": "... улучшенный текст ...",
  "changes_made": ["Добавлен CTA в последний абзац", "Убраны первые 2 предложения вступления"]
}
```

### 2.6 Repurpose Engine

```
POST   /api/v1/repurpose/upload          — Загрузить файл и запустить job
POST   /api/v1/repurpose/youtube         — YouTube URL → job
POST   /api/v1/repurpose/text            — Длинный текст → job
GET    /api/v1/repurpose/jobs            — Список jobs
GET    /api/v1/repurpose/jobs/{id}       — Статус job + extracted_ideas
POST   /api/v1/repurpose/jobs/{id}/send-to-backlog — Отправить выбранные идеи в Backlog
DELETE /api/v1/repurpose/jobs/{id}       — Удалить job
```

**POST /api/v1/repurpose/send-to-backlog**:

```json
// Request
{
  "repurpose_job_id": "uuid",
  "selections": [
    {
      "idea_index": 0,
      "platform": "telegram",
      "content_type": "observation",
      "account_id": "uuid",
      "pillar_id": "uuid",
      "scheduled_at": "2026-06-18T09:00:00Z"  // опционально
    }
  ]
}

// Response — созданные посты в статусе idea_approved (ждут генерации)
{
  "created_posts": [{"id": "uuid", "status": "idea_approved"}]
}
```

### 2.7 Brand Voice

```
GET    /api/v1/brand-voice              — Получить настройки
PUT    /api/v1/brand-voice              — Обновить настройки
POST   /api/v1/brand-voice/example-posts — Добавить эталонный пост
DELETE /api/v1/brand-voice/example-posts/{index} — Удалить эталонный пост
POST   /api/v1/brand-voice/regenerate-prompt — Перегенерировать system prompt кэш
```

### 2.8 Knowledge Base

```
GET    /api/v1/kb                        — Список записей
POST   /api/v1/kb                        — Добавить запись
GET    /api/v1/kb/{id}                   — Одна запись
PUT    /api/v1/kb/{id}                   — Обновить
DELETE /api/v1/kb/{id}                   — Удалить
POST   /api/v1/kb/search                 — Семантический поиск (для генерации)
POST   /api/v1/kb/import-post/{post_id}  — Импортировать опубликованный пост в KB
```

### 2.9 Social Accounts

```
GET    /api/v1/accounts                  — Список аккаунтов
POST   /api/v1/accounts/telegram         — Подключить Telegram (бот токен + chat_id)
GET    /api/v1/accounts/{id}/oauth-url   — Получить OAuth URL (для IG, LI, X)
GET    /api/v1/accounts/oauth/callback   — OAuth callback
DELETE /api/v1/accounts/{id}             — Отключить аккаунт
PATCH  /api/v1/accounts/{id}/posting-times — Обновить оптимальное время постинга
POST   /api/v1/accounts/{id}/refresh-token — Принудительно обновить токен
```

### 2.10 External Sources (Reddit-проект и другие)

```
GET    /api/v1/sources                   — Список источников
POST   /api/v1/sources                   — Создать источник (генерирует API-ключ)
DELETE /api/v1/sources/{id}              — Удалить источник
GET    /api/v1/sources/{id}/ideas        — Идеи из этого источника
POST   /api/v1/sources/{id}/test         — Тест вебхука обратной связи
```

### 2.11 Pillars

```
GET    /api/v1/pillars                   — Список пилларов
POST   /api/v1/pillars                   — Создать
PATCH  /api/v1/pillars/{id}              — Обновить
DELETE /api/v1/pillars/{id}              — Удалить
GET    /api/v1/pillars/{id}/stats        — Статистика (кол-во постов, баланс)
```

### 2.12 Media

```
POST   /api/v1/media/upload              — Загрузить файл (multipart)
GET    /api/v1/media/{id}                — Метаданные файла
GET    /api/v1/media/{id}/presigned-url  — Presigned URL для прямого доступа
DELETE /api/v1/media/{id}                — Удалить файл
```

### 2.13 Webhooks (исходящие — обратная связь)

```
POST /api/v1/webhooks/send-feedback      — Ручная отправка обратной связи
GET  /api/v1/webhooks/feedback-history   — История отправленных сигналов
```

---

## 3. Celery Tasks

### 3.1 Конфигурация

```python
# backend/app/tasks/celery_app.py

from celery import Celery
from celery.schedules import crontab

app = Celery(
    "contentos",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
)

app.conf.update(
    task_serializer="json",
    result_expires=3600,
    timezone="UTC",
    beat_schedule={
        # Публикация запланированных постов — каждую минуту
        "publish-scheduled-posts": {
            "task": "tasks.publish.check_and_publish",
            "schedule": 60.0,
        },
        # Обновление просроченных токенов — каждый час
        "refresh-expiring-tokens": {
            "task": "tasks.accounts.refresh_expiring_tokens",
            "schedule": crontab(minute=0),
        },
        # Еженедельная обратная связь в Reddit-проект — понедельник 08:00 UTC
        "send-weekly-feedback": {
            "task": "tasks.feedback.send_weekly_feedback",
            "schedule": crontab(day_of_week=1, hour=8, minute=0),
        },
        # Предупреждение о пустых днях — каждое утро 07:00
        "check-content-gaps": {
            "task": "tasks.schedule.check_content_gaps",
            "schedule": crontab(hour=7, minute=0),
        },
    },
)
```

### 3.2 Задачи публикации

```python
# backend/app/tasks/publish.py

@app.task(name="tasks.publish.check_and_publish")
async def check_and_publish():
    """
    Запускается каждую минуту.
    Находит посты со статусом SCHEDULED и scheduled_at <= now + 2min.
    Для каждого вызывает publish_post.
    """

@app.task(
    name="tasks.publish.publish_post",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 минут между попытками
)
async def publish_post(self, post_id: str):
    """
    1. Загружает Post + SocialAccount из БД
    2. Проверяет токен (refresh если истёк)
    3. Загружает медиа из MinIO если есть
    4. Вызывает adapter.publish_post(post, account)
    5. При успехе: status=PUBLISHED, external_post_id, published_at
    6. При ошибке: retry; после max_retries → status=ERROR, publish_error
    """

@app.task(name="tasks.publish.retry_error_posts")
async def retry_error_posts():
    """
    Находит посты в статусе ERROR с publish_attempts < 3.
    Повторяет публикацию.
    """
```

### 3.3 AI Generation задачи

```python
# backend/app/tasks/generation.py

@app.task(name="tasks.generation.generate_post")
async def generate_post(post_id: str):
    """
    1. Загружает Post (status=IDEA_APPROVED)
    2. Загружает BrandVoice (system_prompt_cache)
    3. Ищет релевантные KB items через /api/v1/kb/search
    4. Формирует промпт с учётом platform template + content_type template
    5. Вызывает Anthropic API (claude-sonnet-4-6)
    6. Сохраняет body → status=DRAFT
    7. Запускает calculate_content_score
    """

@app.task(name="tasks.generation.batch_generate")
async def batch_generate(idea_ids: list[str]):
    """
    Batch Mode: создаёт Post для каждой Idea, запускает generate_post для каждого.
    Параллельно через Celery group.
    """

@app.task(name="tasks.generation.calculate_content_score")
async def calculate_content_score(post_id: str):
    """
    1. Загружает Post
    2. Вызывает AI с оценочным промптом (5 критериев)
    3. Парсит JSON ответ: {hook, structure, readability, cta, platform_fit, issues}
    4. Вычисляет weighted average:
       hook * 0.25 + structure * 0.20 + readability * 0.20 + cta * 0.15 + platform_fit * 0.20
    5. Сохраняет scores и issues → status=REVIEW
    """

@app.task(name="tasks.generation.improve_post")
async def improve_post(post_id: str, issue_keys: list[str]):
    """
    1. Загружает Post с текущим body и score_issues
    2. Формирует промпт: "Улучши эти конкретные проблемы: {issues}"
    3. AI генерирует улучшенный текст
    4. Сохраняет в body_history старую версию
    5. Обновляет body
    6. Запускает calculate_content_score повторно
    """
```

### 3.4 Repurpose задачи

```python
# backend/app/tasks/repurpose.py

@app.task(name="tasks.repurpose.process_job")
async def process_repurpose_job(job_id: str):
    """
    Оркестратор: запускает transcribe → extract_ideas в цепочке.
    """

@app.task(name="tasks.repurpose.transcribe")
async def transcribe(job_id: str):
    """
    1. Загружает RepurposeJob
    2. Если source_type == YOUTUBE_URL:
       - Скачивает аудио через yt-dlp
       - Сохраняет во временный файл
    3. Если source_type == VOICE_NOTE или VIDEO_FILE:
       - Скачивает из MinIO
    4. Отправляет в Whisper API (OpenAI) или локальный faster-whisper
    5. Сохраняет transcription в RepurposeJob
    6. Обновляет status=extracting
    """

@app.task(name="tasks.repurpose.extract_ideas")
async def extract_ideas(job_id: str):
    """
    1. Загружает транскрипцию из RepurposeJob
    2. AI промпт: "Выдели 5-10 самостоятельных идей из текста.
       Для каждой: text, suggested_platform, suggested_content_type"
    3. Ответ: JSON массив идей
    4. Сохраняет в extracted_ideas
    5. Обновляет status=done
    """
```

### 3.5 Account задачи

```python
# backend/app/tasks/accounts.py

@app.task(name="tasks.accounts.refresh_expiring_tokens")
async def refresh_expiring_tokens():
    """
    Находит аккаунты где token_expires_at < now + 24h.
    Для каждого вызывает adapter.refresh_token().
    При ошибке — уведомление (будущее: Telegram бот).
    """

@app.task(name="tasks.accounts.refresh_token")
async def refresh_token(account_id: str):
    """
    Принудительное обновление токена одного аккаунта.
    """
```

### 3.6 Feedback задачи

```python
# backend/app/tasks/feedback.py

@app.task(name="tasks.feedback.send_weekly_feedback")
async def send_weekly_feedback():
    """
    1. Собирает статистику за последние 7 дней:
       - Посты по пиллару: {pillar_id: {published: N, avg_score: X}}
       - Топ content_types по среднему Score
    2. Формирует feedback payload:
       {
         "performing_pillars": [...],  # score > 80 AND published >= 3
         "weak_pillars": [...],        # score < 60 OR published < 1
         "top_content_types": [...],
         "period_start": "...",
         "period_end": "..."
       }
    3. Отправляет POST на feedback_webhook_url каждого активного ExternalSource
    4. Логирует результат
    """

@app.task(name="tasks.schedule.check_content_gaps")
async def check_content_gaps():
    """
    Находит дни следующие 7 дней без запланированных постов.
    Пока просто логирует — в будущем уведомление.
    """
```

---

## 4. Platform Adapters

### 4.1 Базовый интерфейс

```python
# backend/app/adapters/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class PublishResult:
    success: bool
    external_post_id: str | None = None
    external_url: str | None = None
    error: str | None = None

@dataclass
class Metrics:
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    collected_at: datetime = None

@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = None

class PlatformAdapter(ABC):
    platform: Platform

    @abstractmethod
    async def publish_post(self, post: Post, account: SocialAccount) -> PublishResult:
        """Опубликовать пост. Должен быть идемпотентным."""

    @abstractmethod
    async def delete_post(self, external_post_id: str, account: SocialAccount) -> bool:
        """Удалить пост из соцсети."""

    @abstractmethod
    async def get_metrics(self, external_post_id: str, account: SocialAccount) -> Metrics:
        """Получить метрики поста."""

    @abstractmethod
    async def validate_content(self, post: Post) -> ValidationResult:
        """Проверить пост до публикации (лимиты, форматы)."""

    @abstractmethod
    async def refresh_token(self, account: SocialAccount) -> SocialAccount:
        """Обновить OAuth токен. Возвращает обновлённый account."""

    @abstractmethod
    async def validate_account(self, account: SocialAccount) -> bool:
        """Проверить что токен актуален."""
```

### 4.2 Telegram Adapter

```python
# backend/app/adapters/telegram.py

class TelegramAdapter(PlatformAdapter):
    platform = Platform.TELEGRAM

    async def publish_post(self, post: Post, account: SocialAccount) -> PublishResult:
        """
        Использует python-telegram-bot или httpx для Bot API.
        account.platform_meta["bot_token"] — токен бота
        account.platform_meta["chat_id"] — ID канала/группы

        Если media_ids — сначала sendPhoto/sendVideo, текст в caption.
        Иначе sendMessage с parse_mode=Markdown.

        Лимит caption: 1024 символа.
        Лимит текста: 4096 символов (разбиваем на части если больше).
        """

    async def validate_content(self, post: Post) -> ValidationResult:
        errors = []
        if len(post.body) > 4096:
            errors.append(f"Текст слишком длинный: {len(post.body)} символов (лимит 4096)")
        return ValidationResult(valid=not errors, errors=errors)

    async def refresh_token(self, account: SocialAccount) -> SocialAccount:
        # Telegram Bot API токены не истекают — метод no-op
        return account
```

### 4.3 Instagram Adapter

```python
# backend/app/adapters/instagram.py

class InstagramAdapter(PlatformAdapter):
    platform = Platform.INSTAGRAM

    """
    Использует Meta Graph API v19.0.
    Требует: Facebook Page + Instagram Business Account + OAuth.

    Флоу публикации медиа-поста:
    1. POST /{ig-user-id}/media
       {image_url: presigned_url, caption: body + hashtags}
       → creation_id
    2. POST /{ig-user-id}/media_publish
       {creation_id: ...}
       → media_id (external_post_id)

    Флоу Reels:
    1. POST /{ig-user-id}/media
       {media_type: "REELS", video_url: ..., caption: ..., share_to_feed: true}
    2. Polling статуса: GET /{creation_id}?fields=status_code
    3. Когда FINISHED → media_publish

    Лимиты:
    - caption: 2200 символов (включая хэштеги)
    - хэштеги: максимум 30
    - изображение: JPEG/PNG, мин 320px, макс 1440px
    - видео: MP4/MOV, макс 1GB, макс 60 минут (обычные), 90 сек (Reels)
    """
```

### 4.4 TikTok Adapter

```python
# backend/app/adapters/tiktok.py

class TikTokAdapter(PlatformAdapter):
    platform = Platform.TIKTOK

    """
    Использует TikTok Content Posting API.
    Требует: TikTok Developer App + OAuth.

    Публикует ВИДЕО — не текст.
    post.platform_meta["script"] — скрипт (для записи)
    post.platform_meta["video_id"] — MinIO ID видеофайла

    Если видеофайл не прикреплён → PublishResult(success=False, error="TikTok requires video")

    Флоу:
    1. POST /v2/post/publish/video/init/
       {post_info: {title, privacy_level}, source_info: {source: FILE_UPLOAD}}
       → upload_url, publish_id
    2. PUT {upload_url} с бинарными данными видео
    3. GET /v2/post/publish/status/fetch/ → check status
    4. PUBLISHED → external_post_id = publish_id
    """
```

### 4.5 YouTube Adapter

```python
# backend/app/adapters/youtube.py

class YouTubeAdapter(PlatformAdapter):
    platform = Platform.YOUTUBE

    """
    Использует YouTube Data API v3.
    OAuth scope: https://www.googleapis.com/auth/youtube.upload

    post.platform_meta:
      title: str                  — заголовок видео
      description: str            — body + timecodes
      tags: list[str]
      category_id: str            — default "22" (People & Blogs)
      privacy_status: str         — "public" | "unlisted" | "private"

    Флоу:
    1. Создаём resumable upload session
    2. Стримим видеофайл из MinIO
    3. Получаем video_id → external_post_id

    Если нет видеофайла — только обновляем описание существующего видео
    (для случая когда видео уже загружено вручную).
    """
```

### 4.6 LinkedIn Adapter

```python
# backend/app/adapters/linkedin.py

class LinkedInAdapter(PlatformAdapter):
    platform = Platform.LINKEDIN

    """
    Использует LinkedIn API v2.
    OAuth scopes: w_member_social, r_liteprofile

    Текстовый пост: POST /v2/ugcPosts
    {
      author: "urn:li:person:{person_id}",
      lifecycleState: "PUBLISHED",
      specificContent: {
        shareCommentary: {text: body},
        shareMediaCategory: "NONE"
      },
      visibility: {memberNetworkVisibility: "PUBLIC"}
    }

    Токен: expires в 60 дней, refresh через OAuth.
    """
```

### 4.7 X (Twitter) Adapter

```python
# backend/app/adapters/x.py

class XAdapter(PlatformAdapter):
    platform = Platform.X

    """
    Использует Twitter API v2.
    OAuth 2.0 PKCE.

    Обычный твит: POST /2/tweets {"text": body}
    Тред: POST /2/tweets для первого твита,
          затем POST /2/tweets {"text": ..., "reply": {"in_reply_to_tweet_id": prev_id}}

    post.platform_meta["thread"] — список строк если тред
    Иначе post.body (≤280 символов)

    Лимиты: 280 символов на твит (без медиа)
    Токен: expires в 2 часа, refresh токен на 6 месяцев
    """
```

### 4.8 AdapterRegistry

```python
# backend/app/adapters/registry.py

class AdapterRegistry:
    _adapters: dict[Platform, PlatformAdapter] = {}

    def register(self, adapter: PlatformAdapter) -> None:
        self._adapters[adapter.platform] = adapter

    def get(self, platform: Platform) -> PlatformAdapter:
        adapter = self._adapters.get(platform)
        if not adapter:
            raise ValueError(f"No adapter registered for platform: {platform}")
        return adapter

# Инициализация при старте приложения
registry = AdapterRegistry()
registry.register(TelegramAdapter())
registry.register(InstagramAdapter())
registry.register(TikTokAdapter())
registry.register(YouTubeAdapter())
registry.register(LinkedInAdapter())
registry.register(XAdapter())
```

---

## 5. AI Generation System

### 5.1 Промпты по типам контента

```python
# backend/app/ai/templates.py

CONTENT_TYPE_TEMPLATES: dict[ContentType, dict] = {
    ContentType.BREAKDOWN: {
        "name": "Разбор",
        "structure": [
            "Что анализируем — первый абзац (тема + почему важно)",
            "Ключевые выводы — пункты списком (3-5 пунктов)",
            "Главный инсайт — почему это важно для читателя",
        ],
        "instruction": "Пиши как человек который прочитал исследование и делится главным с другом."
    },
    ContentType.CASE: {
        "name": "Кейс",
        "structure": [
            "Ситуация — контекст и что происходило",
            "Проблема — в чём была сложность",
            "Решение — что конкретно сделали",
            "Результат — что получилось, желательно с цифрами",
        ],
        "instruction": "Конкретика важнее общих слов. Числа, детали, реальные решения."
    },
    ContentType.OPINION: {
        "name": "Мнение",
        "structure": [
            "Тезис — чёткая позиция с первого предложения",
            "Аргументы — 2-3 конкретных довода",
            "Вывод — что делать или думать после прочтения",
        ],
        "instruction": "Не бойся быть спорным. Слабая позиция хуже чем провокационная."
    },
    # ... остальные типы
}

PLATFORM_TEMPLATES: dict[Platform, dict] = {
    Platform.TELEGRAM: {
        "format_rules": [
            "Первый абзац — самый важный, читатель решает читать дальше",
            "Короткие блоки по 2-4 строки, пустая строка между блоками",
            "Личное мнение или позиция автора обязательны",
            "Вывод или призыв в последнем абзаце",
            "Без хэштегов",
            "Markdown: *bold*, _italic_, `code`",
        ],
        "length": {"min": 600, "max": 1800},
    },
    Platform.INSTAGRAM: {
        "format_rules": [
            "Первые 125 символов — hook (видны без раскрытия)",
            "История или инсайт в теле поста",
            "CTA в конце (вопрос к аудитории или призыв)",
            "5-10 хэштегов в конце отдельным блоком",
            "Эмодзи для структурирования (не злоупотреблять)",
        ],
        "length": {"min": 150, "max": 2200},
    },
    Platform.TIKTOK: {
        "format_rules": [
            "Это СКРИПТ для видео, не текстовый пост",
            "Hook (первые 3 секунды): вопрос или шокирующее утверждение",
            "Удержание: развитие идеи с нарастанием интереса",
            "Payoff: главный инсайт или ответ",
            "CTA: подписка, комментарий или следующий ролик",
        ],
        "length": {"min": 100, "max": 500},  # скрипт на 30-60 сек
    },
    # ... остальные платформы
}
```

### 5.2 Generation Service

```python
# backend/app/ai/generation.py

class GenerationService:
    def __init__(self, anthropic_client: AsyncAnthropic):
        self.client = anthropic_client

    async def generate_post(
        self,
        topic: str,
        platform: Platform,
        content_type: ContentType,
        brand_voice: BrandVoice,
        kb_context: list[KnowledgeBaseItem],
        source_context: str | None = None,
    ) -> GenerationResult:
        """
        Строит промпт и вызывает Anthropic API.

        Структура промпта:
        1. SYSTEM: Brand Voice system prompt (из кэша)
        2. USER:
           - Контекст KB (релевантные записи)
           - Тип контента + его структура
           - Правила платформы
           - Тема/идея
           - Источник контекст (если есть)

        Модель: claude-sonnet-4-6
        Max tokens: 2000
        Temperature: 0.7
        """

    async def build_brand_voice_prompt(self, brand_voice: BrandVoice) -> str:
        """
        Собирает system prompt из BrandVoice:
        - Тон и стиль
        - Запрещённые слова
        - Любимые конструкции
        - 2-3 примера постов (сокращённые)
        - Предпочтения по длине
        """

    async def search_kb_context(
        self,
        topic: str,
        platform: Platform,
        limit: int = 3,
    ) -> list[KnowledgeBaseItem]:
        """
        Полнотекстовый поиск в Knowledge Base.
        Возвращает топ-3 релевантных записи.
        """
```

### 5.3 Content Score Service

```python
# backend/app/ai/scoring.py

SCORE_PROMPT = """
Оцени этот пост для {platform} по 5 критериям.
Каждый критерий: 0-100.

Пост:
---
{body}
---

Критерии:
- hook: Насколько сильно начало? Захочет ли читатель читать дальше?
- structure: Есть ли логическая структура? Последовательность мыслей?
- readability: Легко ли читается? Нет ли воды и лишних слов?
- cta: Есть ли призыв к действию или завершающий вывод?
- platform_fit: Соответствует ли формат правилам {platform}?

Ответь строго в JSON:
{{
  "hook": 0-100,
  "structure": 0-100,
  "readability": 0-100,
  "cta": 0-100,
  "platform_fit": 0-100,
  "issues": ["конкретная проблема 1", "конкретная проблема 2"],
  "strengths": ["что хорошо 1"]
}}

Правила для issues:
- Конкретно: "Слабый первый абзац — читатель не поймёт зачем читать" ✓
- НЕ абстрактно: "Нужно улучшить качество" ✗
- Максимум 3 issues
- Если всё хорошо — пустой массив
"""

WEIGHTS = {
    "hook": 0.25,
    "structure": 0.20,
    "readability": 0.20,
    "cta": 0.15,
    "platform_fit": 0.20,
}

class ScoringService:
    async def calculate_score(self, post: Post) -> ScoreResult:
        # Вызов Anthropic API с SCORE_PROMPT
        # Парсинг JSON ответа
        # Расчёт weighted average
        # Возврат ScoreResult
```

---

## 6. Frontend — Спецификация страниц

### 6.1 Технический стек и конфигурация

```
Next.js 14 (App Router)
TypeScript 5
Tailwind CSS v4 (конфиг через CSS variables из design/variables.css)
shadcn/ui (base components)
@tanstack/react-query v5 (data fetching + caching)
axios (HTTP клиент)
date-fns (работа с датами)
react-hook-form + zod (формы)
```

**Структура директорий:**

```
frontend/
├── app/
│   ├── layout.tsx              — RootLayout: sidebar + providers
│   ├── page.tsx                → redirect to /inbox
│   ├── inbox/page.tsx
│   ├── backlog/page.tsx
│   ├── editor/
│   │   ├── page.tsx            — Новый пост
│   │   └── [id]/page.tsx       — Редактировать существующий
│   ├── calendar/page.tsx
│   ├── repurpose/
│   │   ├── page.tsx
│   │   └── [jobId]/page.tsx
│   ├── brand-voice/page.tsx
│   └── settings/
│       ├── accounts/page.tsx
│       └── integrations/page.tsx
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   ├── MobileSidebar.tsx
│   │   └── TopBar.tsx
│   ├── inbox/
│   │   ├── IdeaCard.tsx
│   │   ├── InboxList.tsx
│   │   ├── TodayPanel.tsx
│   │   └── WeekGapsGrid.tsx
│   ├── backlog/
│   │   ├── BacklogRow.tsx
│   │   ├── BacklogFilters.tsx
│   │   └── StatusBadge.tsx
│   ├── editor/
│   │   ├── ContentTypeSelector.tsx
│   │   ├── PlatformTabs.tsx
│   │   ├── PostEditor.tsx
│   │   ├── PlatformPreview.tsx
│   │   ├── ContentScorePanel.tsx
│   │   └── TemplateHint.tsx
│   ├── calendar/
│   │   ├── CalendarGrid.tsx
│   │   ├── CalendarCell.tsx
│   │   └── DayPostsList.tsx
│   ├── repurpose/
│   │   ├── UploadArea.tsx
│   │   ├── ExtractedIdeaCard.tsx
│   │   └── DistributionPanel.tsx
│   └── shared/
│       ├── PlatformIcon.tsx
│       ├── PillarTag.tsx
│       ├── ContentTypeBadge.tsx
│       └── ScheduleTimePicker.tsx
└── lib/
    ├── api.ts                  — axios instance + interceptors
    ├── queries/                — react-query hooks
    └── utils.ts
```

### 6.2 Страница: Inbox

**URL:** `/inbox`

**Данные:**
- `GET /api/v1/ideas?status=inbox&limit=50` — список идей
- `GET /api/v1/calendar/day/{today}` — посты сегодня
- `GET /api/v1/calendar/gaps` — пустые дни недели

**Layout:** двухколоночный (список идей + правая панель)

**Компонент IdeaCard:**
```typescript
interface IdeaCardProps {
  idea: Idea;
  selected: boolean;
  onApprove: () => void;
  onReject: () => void;
  onEdit: () => void;
  onSelect: (checked: boolean) => void;  // для Batch Mode
}
// Показывает: заголовок, источник, контекст (collapsed/expanded),
// предлагаемую платформу, пиллар, relevance_score бар
```

**Batch Mode:**
1. Пользователь выбирает идеи чекбоксами
2. Кнопка "Создать черновики (N)" активируется
3. Click → `POST /api/v1/posts/batch-generate {idea_ids: [...]}`
4. Показываем прогресс через polling `GET /api/v1/tasks/{task_id}`
5. По завершении — уведомление, ссылка на Backlog

**Правая панель — Сегодня:**
- Список `GET /api/v1/calendar/day/{today}` постов с временем и статусом
- Иконки платформ, статус-индикаторы

**Правая панель — Неделя:**
- 7 ячеек Пн–Вс
- Зелёные = есть посты, красные = пустые (gaps), тёмная = сегодня

**Acceptance criteria:**
- Идеи загружаются за <500ms
- Approve/reject одной идеи работает без перезагрузки страницы
- Batch Mode запускает генерацию и показывает прогресс
- Красные дни в сетке недели видны явно

### 6.3 Страница: Content Backlog

**URL:** `/backlog`

**Данные:**
- `GET /api/v1/posts` с фильтрами из URL query params

**Filters (URL query params):**
```
?status=draft,review&pillar=uuid&platform=telegram&type=case
```

**Компонент BacklogRow:**
```typescript
interface BacklogRowProps {
  post: Post;
  onStatusChange: (status: PipelineStatus) => void;
  onSchedule: () => void;
  onEdit: () => void;
}
// Колонки: статус-badge | заголовок (первые 80 символов body) | пиллар-тег |
//          тип-badge | платформа-иконка | время (или "не назначен") | Content Score
```

**Stats row:** счётчики по статусам из текущей выборки (без доп. запроса — из data.length).

**Быстрые действия:**
- Клик на строку → открывает редактор `/editor/{id}`
- Кнопка "Назначить время" → inline DateTimePicker
- Кнопка смены статуса → dropdown (PATCH /api/v1/posts/{id}/status)

### 6.4 Страница: Редактор постов

**URL:** `/editor` (новый) или `/editor/{id}` (редактирование)

**Layout:** split-screen (50/50 на desktop, tabs на mobile)

**Левая панель — Редактор:**

1. **ContentTypeSelector** — horizontal pills: Разбор, Кейс, Мнение, Инструкция...
2. **PlatformTabs** — tabs: TG | IG | LI | X | TT | YT
   - Каждый таб = отдельная версия поста
   - В мультиплатформа режиме — все активны
   - В одиночном — один таб активен
3. **TemplateHint** — фиолетовая подсказка структуры для выбранного type+platform
4. **PostEditor textarea** — auto-resize, char counter
5. **MediaUpload** — drag & drop, показывает превью
6. **Footer:** char count | кнопка Content Score | кнопка "На Review"

**Правая панель — Preview / Score:**

Переключается кнопкой Content Score:

**Preview режим:**
- Показывает как выглядит пост в выбранной платформе
- TelegramPreview: bubble с аватаром
- InstagramPreview: карточка с фото-плейсхолдером
- LinkedInPreview: пост-карточка
- X: твит-карточка (или тред)
- TikTok: экран смартфона с оверлеем скрипта

**Score режим (после нажатия кнопки):**
- Запрос `POST /api/v1/posts/{id}/score`
- Отображение 5 метрик с прогресс-барами
- Список issues
- Кнопка "Улучшить" → `POST /api/v1/posts/{id}/improve`
- После улучшения: Score пересчитывается автоматически

**Флоу генерации (новый пост из идеи):**
1. Переход из Inbox через "Редактировать" у одобренной идеи
2. Выбор ContentType + Platform
3. Кнопка "Сгенерировать" → `POST /api/v1/ai/generate-post`
4. Streaming ответ → текст появляется в textarea постепенно
5. Score рассчитывается после генерации

**Acceptance criteria:**
- Переключение между платформами не сбрасывает текст каждой вкладки
- Генерация через streaming — текст появляется без задержки
- Content Score отображается за <3 сек после запроса
- Кнопка "Улучшить" применяет изменения и показывает новый Score

### 6.5 Страница: Календарь

**URL:** `/calendar`

**Данные:**
- `GET /api/v1/calendar/month?year=2026&month=6`

**CalendarGrid:**
- 7 колонок × 5-6 строк
- Каждая CalendarCell: номер дня + цветные точки платформ + пиллар-бар снизу
- Красная граница = gap (нет постов)
- Тёмный фон = сегодня

**CalendarCell клик** → слайдовая панель справа (DayPostsList):
```
17 июня — 3 поста

09:00  [TG]  Утренний дайджест  ✓ Опубликован
14:00  [LI]  Кейс: автоматизация  ⏱ Ожидает
19:00  [IG]  5 ошибок  ⏱ Ожидает
[+ Добавить пост на этот день]
```

**Filters:** chips по платформам и пилларам над calendar.

**Переключение вид:** Месяц / Неделя (week показывает больше деталей в каждой ячейке).

### 6.6 Страница: Repurpose Engine

**URL:** `/repurpose`

**Layout:** двухколоночный

**Левая колонка — Источник + Результат:**

Input tabs: Голосовая заметка | Видео/YouTube | Текст

Для голосовой заметки:
- Кнопка "Записать" → MediaRecorder API → WAV файл
- Или drag & drop аудио файла

После загрузки → `POST /api/v1/repurpose/upload` (или /youtube или /text)
→ job создан, status=pending

Polling `GET /api/v1/repurpose/jobs/{id}` каждые 3 сек пока status != done

Когда done → показываем extracted_ideas:
```
Извлечённые идеи (4)

[Идея 1]
"AI-агенты не могут работать с задачами дольше 15 шагов..."
[TG] [LI] [X] [Reels] [+ Все платформы]

[Идея 2]
...
```

**Правая колонка — Распределение:**
- Список выбранных пар (идея × платформа) с предлагаемыми датами
- Кнопка "Добавить в Backlog"
- Предупреждение если автоматически заполняет пустые дни

### 6.7 Страница: Brand Voice & Knowledge Base

**URL:** `/brand-voice`

**Layout:** двухколоночный

**Левая колонка — Brand Voice:**

Секция "Голос автора":
- Textarea "Тон и стиль" (свободный текст)
- Инпут "Предпочтения по длине" (per platform)
- Tags input "Запрещённые слова"
- Tags input "Любимые конструкции"

Секция "Эталонные посты":
- Список текстов с оценкой
- Кнопка "Добавить" → modal с textarea
- DELETE для каждого

Кнопка "Сохранить" → `PUT /api/v1/brand-voice`
Кнопка "Обновить промпт" → `POST /api/v1/brand-voice/regenerate-prompt`

**Правая колонка — Knowledge Base:**

Quick note input (всегда видна):
```
[Быстрая заметка...]  [+ Добавить]
```

Список KBItem:
- Тип, заголовок, превью текста, теги, пиллар, дата
- Клик → открывает в modal для редактирования

Кнопка "+ Импортировать пост" → выбор из опубликованных постов

---

## 7. Docker Compose конфигурация

```yaml
# docker-compose.yml

version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: contentos
      POSTGRES_USER: contentos
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U contentos"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redisdata:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - miniodata:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://contentos:${POSTGRES_PASSWORD}@postgres:5432/contentos
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      API_SECRET_TOKEN: ${API_SECRET_TOKEN}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}  # Fernet key для токенов
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://contentos:${POSTGRES_PASSWORD}@postgres:5432/contentos
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
    depends_on:
      - postgres
      - redis
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4

  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://contentos:${POSTGRES_PASSWORD}@postgres:5432/contentos
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    command: celery -A app.tasks.celery_app beat --loglevel=info

  celery-flower:
    image: mher/flower:latest
    environment:
      CELERY_BROKER_URL: redis://redis:6379/0
    ports:
      - "5555:5555"
    depends_on:
      - redis

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    ports:
      - "3000:3000"
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next

volumes:
  pgdata:
  redisdata:
  miniodata:
```

---

## 8. Переменные окружения

```bash
# .env.example

# Database
POSTGRES_PASSWORD=strong_password_here

# Redis — использует docker default

# MinIO
MINIO_ROOT_USER=contentos_admin
MINIO_ROOT_PASSWORD=strong_minio_password

# API Auth — статический Bearer токен для доступа к API
API_SECRET_TOKEN=your_static_bearer_token_here

# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...

# Encryption (для токенов соцсетей в БД)
# Генерация: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your_fernet_key_here

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional: OpenAI Whisper API для транскрипции
OPENAI_API_KEY=sk-...
# Или: использовать локальный faster-whisper (модель загружается автоматически)
WHISPER_MODE=api  # "api" | "local"
WHISPER_LOCAL_MODEL=base  # "tiny" | "base" | "small" | "medium" | "large"

# OAuth credentials для каждой платформы
TELEGRAM_BOT_TOKEN=...         # для Telegram Bot API
INSTAGRAM_APP_ID=...
INSTAGRAM_APP_SECRET=...
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...
TIKTOK_CLIENT_KEY=...
TIKTOK_CLIENT_SECRET=...
X_CLIENT_ID=...
X_CLIENT_SECRET=...
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
```

---

## 9. Acceptance Criteria — полный сервис

### 9.1 Content Pipeline

- [ ] Идея проходит все 8 статусов от INBOX до PUBLISHED без ручного вмешательства (кроме одобрений)
- [ ] PATCH /status с неверным переходом возвращает 400 (например, PUBLISHED → DRAFT запрещён)
- [ ] Пост в статусе ERROR не публикуется повторно автоматически (только ручной retry)
- [ ] Celery Beat запускает check_and_publish каждую минуту ±5 сек

### 9.2 Публикация

- [ ] Telegram: пост с Markdown форматированием публикуется корректно
- [ ] Instagram: пост без медиафайла возвращает ValidationError до публикации
- [ ] TikTok: пост без видео возвращает PublishResult(success=False) с понятным error
- [ ] При ошибке публикации (сеть, API) — retry 3 раза с задержкой 5 мин
- [ ] После 3 неудачных попыток — статус ERROR, publish_error содержит причину

### 9.3 AI Generation

- [ ] generate_post возвращает ответ за <10 сек (P95)
- [ ] Сгенерированный пост содержит структуру выбранного content_type
- [ ] Запрещённые слова из Brand Voice НЕ появляются в генерации
- [ ] Content Score рассчитывается за <5 сек
- [ ] score_issues содержит конкретные, не абстрактные формулировки
- [ ] Кнопка "Улучшить" применяет изменения и повышает Score минимум на 5 пунктов

### 9.4 Batch Mode

- [ ] batch_generate для 10 идей завершается за <120 сек
- [ ] Все 10 постов создаются даже если 1-2 генерации вернули ошибку (частичный успех)
- [ ] Polling task_id возвращает прогресс (N из 10 готово)

### 9.5 Repurpose Engine

- [ ] Голосовая заметка 5 мин транскрибируется за <60 сек (API mode)
- [ ] YouTube URL 30 мин → транскрипция за <3 мин
- [ ] Из 8-минутной заметки извлекается минимум 3 самостоятельные идеи
- [ ] "Добавить в Backlog" создаёт посты и переходит на /backlog

### 9.6 Brand Voice

- [ ] Обновление Brand Voice → regenerate_prompt → cache обновлён
- [ ] Следующая генерация использует новый кэш (без перезапуска сервиса)
- [ ] Пример поста в BrandVoice влияет на стиль генерации (верифицируется вручную)

### 9.7 Reddit Integration

- [ ] POST /api/inbox/idea без API ключа → 401
- [ ] POST /api/inbox/idea с корректным ключом → идея появляется в Inbox за <1 сек
- [ ] send_weekly_feedback отправляет корректный payload на feedback_webhook_url
- [ ] При недоступности webhook — ошибка логируется, задача не падает

### 9.8 Календарь

- [ ] calendar/month возвращает дни с правильным количеством постов
- [ ] Дни без постов отмечены is_gap: true
- [ ] next-slot возвращает ближайшее оптимальное время для платформы
- [ ] Нельзя поставить два поста одного аккаунта в ±30 минут (409 Conflict)

### 9.9 Frontend

- [ ] Inbox загружается за <500ms на локальной сети
- [ ] Score panel открывается/закрывается без перезагрузки страницы
- [ ] На мобайле (<768px) sidebar скрыт, показывается bottom nav
- [ ] Все формы имеют validation перед отправкой (zod схемы)
- [ ] Ошибки API показываются пользователю (toast уведомления)

---

## 10. Порядок разработки

| Итерация | Модули | Результат |
|----------|--------|-----------|
| 1 | БД: все модели + миграции; Docker Compose | `docker compose up` поднимает стек |
| 2 | Backend: Post + Account CRUD; Telegram adapter; Celery publish task | Первый пост уходит в Telegram |
| 3 | AI: generate_post + Content Score; Brand Voice модель | Генерация из темы с Brand Voice |
| 4 | Frontend: Inbox + Backlog + Editor (Telegram only) | Полный флоу в браузере |
| 5 | Reddit webhook + Batch Mode | Утренний ритуал работает |
| 6 | Instagram adapter; мультиплатформа в редакторе | 2 платформы |
| 7 | Repurpose Engine (голос → пост) | Заметка → Backlog |
| 8 | Calendar страница; Content Pillars | Баланс тем виден |
| 9 | Knowledge Base; TikTok + YouTube (скрипты) | KB влияет на генерацию |
| 10 | LinkedIn + X adapters; Weekly feedback | Все платформы, замкнутый конвейер |
