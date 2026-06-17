# ContentOS — Детальный технический план разработки

> Версия: 1.0  
> Дата: 2026-06-15  
> Один разработчик, self-hosted, практичный подход

---

## 1. Технологический стек

### 1.1 Backend — Python + FastAPI

**Выбор:** Python 3.12 + FastAPI + Celery + Redis

**Обоснование:**
- FastAPI даёт автоматическую генерацию OpenAPI-документации и async из коробки
- Celery — де-факто стандарт для фоновых задач (расписание, автопубликация) в Python-экосистеме
- Все клиентские библиотеки Instagram/Twitter/LinkedIn написаны на Python
- OpenRouter SDK и Anthropic SDK имеют первоклассную поддержку Python
- Один разработчик: Python читается быстро, итерация быстрая

**Альтернативы и почему не выбраны:**
- Node.js/NestJS — дополнительная сложность при работе с медиа и ML-библиотеками
- Go — более жёсткая типизация замедляет прототипирование для одного разработчика
- Django — избыточен, ORM сложнее кастомизировать под адаптерный паттерн

### 1.2 Frontend — Next.js 14 (App Router)

**Выбор:** Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui

**Обоснование:**
- App Router даёт Server Components — меньше клиентского JS для страниц аналитики
- Tailwind + shadcn/ui: готовые компоненты (календарь, таблицы, формы) без дизайн-системы с нуля
- TypeScript: автодополнение API-типов из backend OpenAPI схемы (через openapi-typescript)
- Один разработчик: shadcn/ui даёт 80% нужных компонентов готовыми
- Next.js API Routes используются только для прокси OAuth — остальное на FastAPI

**Библиотеки UI:**
- `@dnd-kit/core` — drag-and-drop для календаря (легче FullCalendar для кастомизации)
- `react-big-calendar` или `@dnd-kit` с кастомной сеткой — визуальный календарь
- `recharts` — графики аналитики (легковесный, хорошая документация)
- `react-dropzone` — загрузка медиа
- `@tanstack/react-query` — кэширование запросов к API

### 1.3 База данных — PostgreSQL 16

**Выбор:** PostgreSQL 16

**Обоснование:**
- JSONB для хранения platform-specific метаданных поста без изменения схемы при добавлении новой соцсети
- Встроенная поддержка полнотекстового поиска по постам и медиа-тегам
- `pg_cron` или Celery Beat для планирования — оба работают с PG
- Один разработчик: SQL понятнее NoSQL при сложных запросах аналитики
- Надёжность ACID критична для очереди публикаций

**ORM:** SQLAlchemy 2.0 (async) + Alembic для миграций

### 1.4 Очередь задач — Redis + Celery

**Выбор:** Redis 7 как брокер + Celery 5 как воркер

**Обоснование:**
- Redis также используется как кэш (сессии, rate limiting, кэш аналитики)
- Celery Beat — встроенный планировщик для повторяющихся задач
- Celery Flower — UI мониторинга очереди из коробки
- Redis Streams можно использовать для real-time уведомлений (WebSocket через FastAPI)

**Альтернатива:** APScheduler внутри FastAPI — проще, но не масштабируется; выбираем Celery сразу.

### 1.5 Хранилище медиа — MinIO (S3-compatible)

**Выбор:** MinIO self-hosted

**Обоснование:**
- S3-compatible API: можно переехать на AWS S3/Backblaze без изменения кода (только env vars)
- Встроенный UI для просмотра бакетов
- Python SDK `boto3` работает без изменений
- Pre-signed URLs для прямой загрузки из браузера минуя backend
- Бесплатно, self-hosted, нет vendor lock-in

**Конфигурация:**
- Бакет `media-originals` — оригиналы
- Бакет `media-thumbnails` — превью (генерируются Celery-задачей после загрузки)
- Политика публичного чтения для thumbnails

### 1.6 Деплой — Docker Compose (локально) + GitHub

**Выбор:** Docker Compose локально + GitHub как удалённый репозиторий

**Обоснование:**
- Один разработчик, один пользователь: VPS избыточен и стоит денег
- `docker compose up -d` — весь стек в одну команду на локальной машине
- GitHub: хранение кода, CI (GitHub Actions для тестов), история изменений
- Резервное копирование: `pg_dump` в cron + сохранение в MinIO локально
- Нет расходов на инфраструктуру

**Запуск:** `docker compose up -d` на локальной машине, интерфейс доступен на `localhost`

**GitHub Actions:** автоматический запуск тестов при push в main

---

## 2. Архитектурная схема

### 2.1 Общая структура

```
┌─────────────────────────────────────────────────────────────┐
│                     Next.js Frontend                        │
│   Calendar │ Post Editor │ Media Library │ Analytics        │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API (JSON)
┌────────────────────────▼────────────────────────────────────┐
│                   FastAPI Backend (Core)                     │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Posts   │  │ Schedule │  │  Media   │  │    AI    │  │
│  │  Module  │  │  Module  │  │  Module  │  │  Module  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │              │              │              │        │
│  ┌────▼──────────────▼──────────────▼──────────────▼─────┐ │
│  │              Platform Adapter Registry                 │ │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐          │ │
│  │   │Instagram │  │Twitter/X │  │ LinkedIn │  ...      │ │
│  │   │ Adapter  │  │ Adapter  │  │ Adapter  │          │ │
│  │   └──────────┘  └──────────┘  └──────────┘          │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
    ┌─────▼──────┐ ┌──────▼──────┐ ┌────▼────────┐
    │ PostgreSQL │ │    Redis    │ │    MinIO    │
    │    (DB)    │ │ (Queue+Cache)│ │   (Media)  │
    └────────────┘ └──────┬──────┘ └─────────────┘
                          │
                   ┌──────▼──────┐
                   │   Celery    │
                   │   Workers   │
                   │             │
                   │ • publish   │
                   │ • thumbnail │
                   │ • analytics │
                   │ • notify    │
                   └─────────────┘
```

### 2.2 Адаптерный паттерн для соцсетей

Каждая платформа реализует единый интерфейс `PlatformAdapter`:

```python
class PlatformAdapter(ABC):
    platform: PlatformType

    async def publish_post(self, post: Post, account: Account) -> PublishResult
    async def delete_post(self, external_id: str, account: Account) -> bool
    async def get_metrics(self, external_id: str, account: Account) -> Metrics
    async def validate_media(self, media: MediaFile) -> ValidationResult
    async def refresh_token(self, account: Account) -> Account

class AdapterRegistry:
    _adapters: dict[PlatformType, PlatformAdapter]

    def get(self, platform: PlatformType) -> PlatformAdapter
    def register(self, adapter: PlatformAdapter) -> None
```

**Правило:** ядро (Posts, Schedule, Media, AI модули) знает только об интерфейсе `PlatformAdapter`. Добавление новой платформы = создание нового класса адаптера + регистрация в реестре. Ядро не меняется.

### 2.3 Поток публикации

```
[Celery Beat: каждую минуту]
        │
        ▼
check_scheduled_posts()
        │
   Находит посты WHERE scheduled_at <= now() AND status = 'scheduled'
        │
        ▼
publish_post.delay(post_id)  ← Celery task
        │
        ▼
AdapterRegistry.get(post.platform)
        │
        ▼
adapter.publish_post(post, account)
        │
   ┌────▼────┐
   │ Success │ → update post status='published', save external_id
   │         │   → trigger analytics.delay(post_id, delay=3600)
   └─────────┘
   ┌────▼────┐
   │  Error  │ → update post status='failed', increment retry_count
   │         │   → if retry_count < 3: retry with exponential backoff
   │         │   → if retry_count >= 3: notify user (email + push)
   └─────────┘
```

---

## 3. Структура проекта

```
content-os/
├── docker-compose.yml          # Все сервисы: api, worker, beat, db, redis, minio
├── docker-compose.dev.yml      # Переопределения для разработки (hot reload, порты)
├── .env.example                # Шаблон переменных окружения
├── Makefile                    # Команды: make dev, make migrate, make test
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml          # Зависимости (uv или poetry)
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/           # Миграции БД
│   │
│   ├── app/
│   │   ├── main.py             # FastAPI app, подключение роутеров
│   │   ├── config.py           # Pydantic Settings из .env
│   │   ├── database.py         # SQLAlchemy async engine, сессии
│   │   ├── celery_app.py       # Celery instance + Beat расписание
│   │   │
│   │   ├── core/               # Ядро — платформо-независимо
│   │   │   ├── models/         # SQLAlchemy модели
│   │   │   │   ├── post.py
│   │   │   │   ├── media.py
│   │   │   │   ├── account.py
│   │   │   │   ├── schedule.py
│   │   │   │   └── analytics.py
│   │   │   ├── schemas/        # Pydantic схемы (request/response)
│   │   │   │   ├── post.py
│   │   │   │   ├── media.py
│   │   │   │   └── ...
│   │   │   ├── services/       # Бизнес-логика
│   │   │   │   ├── post_service.py
│   │   │   │   ├── media_service.py
│   │   │   │   ├── schedule_service.py
│   │   │   │   └── ai_service.py
│   │   │   └── tasks/          # Celery задачи
│   │   │       ├── publish.py
│   │   │       ├── analytics.py
│   │   │       ├── media.py
│   │   │       └── notify.py
│   │   │
│   │   ├── adapters/           # Адаптеры платформ
│   │   │   ├── base.py         # Абстрактный PlatformAdapter
│   │   │   ├── registry.py     # AdapterRegistry
│   │   │   ├── instagram/
│   │   │   │   ├── adapter.py  # InstagramAdapter(PlatformAdapter)
│   │   │   │   ├── client.py   # Обёртка над Graph API
│   │   │   │   └── types.py    # Платформо-специфичные типы
│   │   │   ├── twitter/
│   │   │   │   └── adapter.py
│   │   │   └── linkedin/
│   │   │       └── adapter.py
│   │   │
│   │   ├── api/                # FastAPI роутеры
│   │   │   ├── v1/
│   │   │   │   ├── posts.py
│   │   │   │   ├── media.py
│   │   │   │   ├── accounts.py
│   │   │   │   ├── schedule.py
│   │   │   │   ├── analytics.py
│   │   │   │   └── ai.py
│   │   │   └── deps.py         # FastAPI dependencies (db session, current user)
│   │   │
│   │   └── storage/
│   │       └── s3.py           # MinIO/S3 клиент (boto3 wrapper)
│   │
│   └── tests/
│       ├── unit/
│       └── integration/
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   │
│   ├── src/
│   │   ├── app/                # Next.js App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx        # Редирект на /calendar
│   │   │   ├── calendar/
│   │   │   │   └── page.tsx
│   │   │   ├── posts/
│   │   │   │   ├── page.tsx    # Лента постов
│   │   │   │   ├── new/
│   │   │   │   │   └── page.tsx
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx
│   │   │   ├── media/
│   │   │   │   └── page.tsx
│   │   │   └── analytics/
│   │   │       └── page.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── ui/             # shadcn/ui компоненты
│   │   │   ├── calendar/
│   │   │   │   ├── CalendarGrid.tsx
│   │   │   │   ├── CalendarEvent.tsx
│   │   │   │   └── DraggablePost.tsx
│   │   │   ├── post-editor/
│   │   │   │   ├── PostEditor.tsx
│   │   │   │   ├── PlatformPreview.tsx
│   │   │   │   └── AIAssistant.tsx
│   │   │   ├── media/
│   │   │   │   ├── MediaGrid.tsx
│   │   │   │   └── MediaUploader.tsx
│   │   │   └── shared/
│   │   │       ├── PostCard.tsx
│   │   │       └── StatusBadge.tsx
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts          # Typed API client (из OpenAPI схемы)
│   │   │   └── utils.ts
│   │   │
│   │   └── hooks/
│   │       ├── usePosts.ts
│   │       ├── useCalendar.ts
│   │       └── useMedia.ts
│   │
│   └── public/
│
├── .github/
│   └── workflows/
│       └── test.yml            # GitHub Actions: запуск тестов при push
└── infra/
    └── scripts/
        ├── backup.sh           # pg_dump + сохранение в MinIO локально
        └── restore.sh
```

---

## 4. Схема базы данных

### 4.1 Таблица `accounts`

```sql
CREATE TABLE accounts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform         VARCHAR(20) NOT NULL,           -- 'instagram', 'twitter', 'linkedin'
    username         VARCHAR(100) NOT NULL,
    display_name     VARCHAR(200),
    avatar_url       TEXT,
    access_token     TEXT NOT NULL,                  -- зашифрован (Fernet)
    refresh_token    TEXT,                           -- зашифрован
    token_expires_at TIMESTAMPTZ,
    platform_user_id VARCHAR(100),
    meta             JSONB DEFAULT '{}',             -- platform-specific данные
    is_active        BOOLEAN DEFAULT true,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_accounts_platform ON accounts(platform);
```

### 4.2 Таблица `posts`

```sql
CREATE TABLE posts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id       UUID REFERENCES accounts(id) ON DELETE CASCADE,
    status           VARCHAR(20) NOT NULL DEFAULT 'draft',
                     -- draft | scheduled | publishing | published | failed | cancelled
    content          TEXT,
    content_variants JSONB DEFAULT '{}',             -- {instagram: '...', twitter: '...'}
    scheduled_at     TIMESTAMPTZ,
    published_at     TIMESTAMPTZ,
    external_id      VARCHAR(200),                   -- ID поста на платформе
    external_url     TEXT,
    retry_count      INT DEFAULT 0,
    last_error       TEXT,
    template_id      UUID REFERENCES post_templates(id) ON DELETE SET NULL,
    series_id        UUID REFERENCES post_series(id) ON DELETE SET NULL,
    meta             JSONB DEFAULT '{}',             -- platform-specific параметры
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_scheduled_at ON posts(scheduled_at) WHERE status = 'scheduled';
CREATE INDEX idx_posts_account_id ON posts(account_id);
```

### 4.3 Таблица `post_media`

```sql
CREATE TABLE post_media (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id    UUID REFERENCES posts(id) ON DELETE CASCADE,
    media_id   UUID REFERENCES media_files(id) ON DELETE RESTRICT,
    position   INT DEFAULT 0,                        -- порядок в карусели
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.4 Таблица `media_files`

```sql
CREATE TABLE media_files (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename      VARCHAR(500) NOT NULL,
    original_url  TEXT NOT NULL,                     -- MinIO URL оригинала
    thumbnail_url TEXT,                              -- MinIO URL превью
    media_type    VARCHAR(20) NOT NULL,              -- 'image', 'video', 'gif'
    mime_type     VARCHAR(100),
    file_size     BIGINT,                            -- байты
    width         INT,
    height        INT,
    duration_secs INT,                               -- для видео
    tags          TEXT[] DEFAULT '{}',
    alt_text      TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_media_tags ON media_files USING GIN(tags);
CREATE INDEX idx_media_type ON media_files(media_type);
```

### 4.5 Таблица `post_analytics`

```sql
CREATE TABLE post_analytics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id         UUID REFERENCES posts(id) ON DELETE CASCADE,
    collected_at    TIMESTAMPTZ DEFAULT NOW(),
    views           INT DEFAULT 0,
    likes           INT DEFAULT 0,
    comments        INT DEFAULT 0,
    shares          INT DEFAULT 0,
    saves           INT DEFAULT 0,
    reach           INT DEFAULT 0,
    impressions     INT DEFAULT 0,
    engagement_rate DECIMAL(5,4),
    raw_data        JSONB DEFAULT '{}'
);

CREATE INDEX idx_analytics_post_id ON post_analytics(post_id);
CREATE INDEX idx_analytics_collected_at ON post_analytics(collected_at);
```

### 4.6 Таблица `post_templates`

```sql
CREATE TABLE post_templates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(200) NOT NULL,
    description TEXT,
    content     TEXT,                                -- шаблон с {{variables}}
    platforms   TEXT[] DEFAULT '{}',
    category    VARCHAR(100),
    meta        JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.7 Таблица `recurring_schedules`

```sql
CREATE TABLE recurring_schedules (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id  UUID REFERENCES accounts(id) ON DELETE CASCADE,
    name        VARCHAR(200),
    cron_expr   VARCHAR(100) NOT NULL,               -- '0 9 * * 1,3,5'
    template_id UUID REFERENCES post_templates(id),
    is_active   BOOLEAN DEFAULT true,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 5. API-дизайн

**Базовый URL:** `/api/v1`  
**Аутентификация:** API Key в заголовке `X-API-Key`  
**Формат:** JSON, snake_case поля  
**Пагинация:** cursor-based (`?cursor=<id>&limit=20`)

### 5.1 Posts

```
GET    /posts                        # Лента постов
       ?status=published&platform=instagram&limit=20&cursor=<id>
POST   /posts                        # Создать черновик
GET    /posts/{id}                   # Получить пост
PATCH  /posts/{id}                   # Обновить
DELETE /posts/{id}                   # Удалить / отменить
POST   /posts/{id}/schedule          # Запланировать
       body: {"scheduled_at": "2026-06-20T09:00:00Z"}
POST   /posts/{id}/publish-now       # Опубликовать немедленно
POST   /posts/{id}/cancel            # Отменить публикацию
GET    /posts/{id}/analytics         # Метрики поста
GET    /posts/calendar               # Посты для календаря
       ?from=2026-06-01&to=2026-06-30
```

**Пример ответа GET /posts:**
```json
{
  "items": [
    {
      "id": "uuid",
      "status": "published",
      "content": "Текст поста",
      "scheduled_at": null,
      "published_at": "2026-06-14T09:00:00Z",
      "platform": "instagram",
      "account": {"id": "uuid", "username": "@handle"},
      "media": [{"id": "uuid", "thumbnail_url": "...", "media_type": "image"}],
      "analytics": {"likes": 42, "views": 310, "engagement_rate": 0.0135}
    }
  ],
  "next_cursor": "uuid",
  "total": 156
}
```

### 5.2 Media

```
GET    /media                        # Медиа-библиотека
       ?type=image&tags=nature,travel&limit=40
POST   /media/upload-url             # Pre-signed URL для прямой загрузки
       response: {"upload_url": "...", "media_id": "uuid", "fields": {...}}
POST   /media/{id}/confirm           # Подтвердить загрузку
PATCH  /media/{id}                   # Обновить теги, alt_text
DELETE /media/{id}                   # Удалить
```

### 5.3 Accounts

```
GET    /accounts                           # Список аккаунтов
GET    /accounts/{platform}/oauth/start    # Начать OAuth flow
GET    /accounts/{platform}/oauth/callback # OAuth callback
DELETE /accounts/{id}                      # Отключить аккаунт
POST   /accounts/{id}/refresh-token        # Принудительно обновить токен
```

### 5.4 Schedule

```
GET    /schedules                    # Повторяющиеся расписания
POST   /schedules                    # Создать
PATCH  /schedules/{id}               # Обновить
DELETE /schedules/{id}               # Удалить
POST   /schedules/{id}/toggle        # Включить/выключить
```

### 5.5 Analytics

```
GET    /analytics/overview           # Агрегированная статистика
       ?from=2026-05-01&to=2026-06-01&platform=instagram
GET    /analytics/top-posts          # Топ постов по engagement
       ?period=30d&metric=likes&limit=10
GET    /analytics/timeline           # Временной ряд для графика
       ?metric=views&period=30d&granularity=day
```

### 5.6 AI

```
POST   /ai/generate                  # Сгенерировать текст
       body: {"prompt": "...", "platform": "instagram", "tone": "casual", "model": "gpt-4o"}
POST   /ai/adapt                     # Адаптировать под другую платформу
       body: {"content": "...", "from_platform": "instagram", "to_platform": "twitter"}
POST   /ai/improve                   # Улучшить текст
       body: {"content": "...", "instruction": "сделай более эмоциональным"}
```

### 5.7 Templates

```
GET    /templates
POST   /templates
GET    /templates/{id}
PATCH  /templates/{id}
DELETE /templates/{id}
POST   /templates/{id}/create-post   # Создать пост из шаблона
       body: {"variables": {"topic": "..."}, "account_id": "uuid"}
```

---

## 6. Декомпозиция на спринты

**Формат работы:** 1 разработчик, ~6 рабочих часов в день

### Фаза 0: Инфраструктура (1 неделя)

| Задача | Оценка |
|--------|--------|
| GitHub репозиторий + структура проекта | 0.5 дня |
| Docker Compose: PostgreSQL + Redis + MinIO | 0.5 дня |
| FastAPI boilerplate: config, database, health check | 0.5 дня |
| Alembic: первые миграции (accounts, posts, media) | 0.5 дня |
| MinIO: настройка бакетов, политики, S3 клиент | 0.5 дня |
| Next.js boilerplate: shadcn/ui, layout, API client | 1 день |
| Celery + Redis: настройка, тестовая задача | 0.5 дня |
| GitHub Actions: CI (запуск тестов) | 0.5 дня |
| **Итого** | **4.5 дня** |

**Результат:** Работающий стек, можно делать запросы к API.

---

### Фаза 1: MVP — Instagram + публикация (3 недели)

**Sprint 1.1: Instagram адаптер (1 неделя)**

| Задача | Оценка |
|--------|--------|
| OAuth flow для Instagram Business API | 1.5 дня |
| `InstagramAdapter.publish_post()` (фото) | 1 день |
| `InstagramAdapter.validate_media()` (размеры, форматы) | 0.5 дня |
| Celery задача `publish_post` с retry логикой | 0.5 дня |
| Celery Beat: проверка расписания каждую минуту | 0.5 дня |
| **Итого** | **4 дня** |

**Sprint 1.2: Posts CRUD + расписание (1 неделя)**

| Задача | Оценка |
|--------|--------|
| API: `POST /posts`, `GET /posts`, `PATCH /posts/{id}` | 1 день |
| API: `POST /posts/{id}/schedule`, `/publish-now` | 0.5 дня |
| Media upload: pre-signed URL + confirm endpoint | 1 день |
| Thumbnail генерация (Celery + Pillow/ffmpeg) | 0.5 дня |
| Email уведомления об ошибках (fastapi-mail) | 0.5 дня |
| **Итого** | **3.5 дня** |

**Sprint 1.3: Frontend MVP (1 неделя)**

| Задача | Оценка |
|--------|--------|
| Страница лента постов (`/posts`) | 1 день |
| Страница создания поста (`/posts/new`) | 1.5 дня |
| Загрузка медиа с превью (react-dropzone) | 0.5 дня |
| Планирование: DateTimePicker | 0.5 дня |
| Статусы постов, toast-уведомления | 0.5 дня |
| **Итого** | **4 дня** |

**MVP готов: ~4 недели. Можно публиковать посты в Instagram по расписанию.**

---

### Фаза 2: v1.0 — AI + Медиабиблиотека + Календарь (5 недель)

**Sprint 2.1: AI-ассистент (1 неделя)**

| Задача | Оценка |
|--------|--------|
| OpenRouter клиент (httpx + streaming) | 0.5 дня |
| `POST /ai/generate` со стриминговым ответом | 1 день |
| `POST /ai/adapt` и `POST /ai/improve` | 0.5 дня |
| Frontend: панель AI-ассистента в редакторе поста | 1.5 дня |
| **Итого** | **3.5 дня** |

**Sprint 2.2: Медиа-библиотека (1 неделя)**

| Задача | Оценка |
|--------|--------|
| API: полный CRUD для медиа | 0.5 дня |
| Поиск по тегам (PostgreSQL `@>`) | 0.5 дня |
| Frontend: Grid с фильтрами и поиском | 1 день |
| Bulk upload (несколько файлов) | 0.5 дня |
| Drag-and-drop прикрепление медиа к посту | 0.5 дня |
| Видео поддержка (ffmpeg thumbnail) | 1 день |
| **Итого** | **4 дня** |

**Sprint 2.3: Визуальный календарь (1.5 недели)**

| Задача | Оценка |
|--------|--------|
| `GET /posts/calendar` API | 0.5 дня |
| Компонент `CalendarGrid` (месяц/неделя/день) | 1.5 дня |
| Drag-and-drop перенос поста (@dnd-kit) | 1.5 дня |
| Клик на ячейку → открыть редактор с датой | 0.5 дня |
| Цветовая кодировка по платформе | 0.5 дня |
| **Итого** | **4.5 дня** |

**Sprint 2.4: Шаблоны + базовая аналитика (1.5 недели)**

| Задача | Оценка |
|--------|--------|
| API: Templates CRUD | 0.5 дня |
| Frontend: менеджер шаблонов | 1 день |
| `InstagramAdapter.get_metrics()` | 1 день |
| Celery: сбор метрик (через 1ч / 24ч / 7д после публикации) | 0.5 дня |
| Frontend: страница аналитики с Recharts | 1.5 дня |
| Push-уведомления в браузере (Web Push API) | 1 день |
| **Итого** | **5.5 дней** |

**v1.0 готова: ~9 недель от старта.**

---

### Фаза 3: v2.0 — Расширение платформ + серии (4 недели)

**Sprint 3.1: Twitter/X адаптер (1 неделя)**

| Задача | Оценка |
|--------|--------|
| Twitter OAuth 2.0 | 1 день |
| `TwitterAdapter.publish_post()` (текст + медиа) | 1 день |
| Thread поддержка (серия твитов) | 1 день |
| Twitter-specific ограничения (280 символов) в редакторе | 0.5 дня |
| **Итого** | **3.5 дня** |

**Sprint 3.2: Серии постов + репёрпоз (1.5 недели)**

| Задача | Оценка |
|--------|--------|
| Таблица `post_series`, API для серий | 1 день |
| Репёрпоз: адаптация поста под другую платформу | 1 день |
| Frontend: создание серии, timeline | 1.5 дня |
| Повторяющиеся расписания (Celery Beat + cron_expr) | 1 день |
| **Итого** | **4.5 дня** |

**Sprint 3.3: Расширенная аналитика + LinkedIn (1.5 недели)**

| Задача | Оценка |
|--------|--------|
| Агрегированный кросс-платформенный дашборд | 1.5 дня |
| Топ постов, сравнение периодов | 1 день |
| Экспорт в CSV | 0.5 дня |
| LinkedIn адаптер (базовый) | 2 дня |
| **Итого** | **5 дней** |

**v2.0 готова: ~13 недель от старта (~3 месяца).**

---

## 7. Риски и митигация

### Риск 1: Instagram API ограничения (ВЫСОКИЙ)

**Проблема:**
- Instagram Graph API требует Business/Creator аккаунт (не личный)
- Публикация видео — асинхронная (Container API: создать → подождать → опубликовать)
- Лимит: 50 публикаций за 24 часа на аккаунт
- Reels и карусели — отдельные multi-step flow

**Митигация:**
- Документировать требование Business-аккаунта как обязательное
- Реализовать Container API с polling статуса через Celery retry
- Счётчик публикаций за 24ч в Redis, блокировка при достижении лимита
- Отдельные методы: `publish_single_image`, `publish_carousel`, `publish_reel`

### Риск 2: OAuth токены истекают (СРЕДНИЙ)

**Проблема:** Instagram — 60 дней, Twitter Access Token — 2 часа, LinkedIn — 60 дней

**Митигация:**
- Celery задача `refresh_tokens` раз в час: проверяет `token_expires_at < now() + 7 days`
- При ошибке 401 в адаптере — автоматический retry после refresh
- Email уведомление если refresh не удался (нужна переавторизация)
- Токены шифровать Fernet (python-cryptography) в БД

### Риск 3: Медиа-ограничения платформ (СРЕДНИЙ)

**Проблема:**
- Instagram: JPG/PNG макс 8MB; видео MP4 макс 100MB, соотношение 4:5–1.91:1
- Twitter: JPG/PNG/GIF макс 5MB; видео макс 512MB, 30 FPS
- LinkedIn: JPG/PNG макс 10MB; видео макс 200MB

**Митигация:**
- `validate_media()` в каждом адаптере — проверка до загрузки на платформу
- При создании поста — немедленная валидация с понятными ошибками в UI
- Опциональная конвертация через ffmpeg (Celery задача)

### Риск 4: Rate limits API (СРЕДНИЙ)

**Проблема:** Instagram Graph API: 200 вызовов/час; Twitter Basic: 300 твитов/3ч

**Митигация:**
- Redis счётчик API-вызовов с TTL
- Exponential backoff при 429
- Приоритет: публикации важнее аналитики
- Сбор аналитики — отложенные задачи с jitter

### Риск 5: Instagram API нестабильность (СРЕДНИЙ)

**Проблема:** Meta меняет Graph API, бывают deprecation'ы без предупреждения

**Митигация:**
- Явная версия API в вызовах: `v19.0`
- Health check каждые 30 мин (тестовый `/me` запрос)
- Мониторинг [Meta Changelog](https://developers.facebook.com/docs/graph-api/changelog)

### Риск 6: Хранилище медиа растёт (НИЗКИЙ)

**Митигация:**
- MinIO lifecycle policy: перемещать в cold storage через 90 дней
- Компрессия превью в WebP
- Отображение размера хранилища в UI

---

## 8. Первые шаги (День 1)

### Утро: Инфраструктура (~3 часа)

```bash
# 1. Создать GitHub репозиторий и склонировать
gh repo create content-os --private --clone
cd content-os
git checkout -b main

# 2. Написать docker-compose.yml (postgres, redis, minio)
# 3. Создать .env на основе .env.example
# 4. Поднять инфраструктуру локально
docker compose up -d postgres redis minio

# 5. Инициализировать backend
uv init backend
cd backend
uv add fastapi uvicorn sqlalchemy alembic asyncpg pydantic-settings celery redis boto3 httpx pillow cryptography
```

### Вечер: Первый API (~3 часа)

```bash
# 6. app/config.py — Pydantic Settings из .env
# 7. app/database.py — async SQLAlchemy engine
# 8. alembic init + настройка env.py
alembic init alembic

# 9. Модели Account и Post в app/core/models/
# 10. Первая миграция
alembic revision --autogenerate -m "initial"
alembic upgrade head

# 11. GET /health + POST /posts + GET /posts
# 12. Запуск локально
uvicorn app.main:app --reload
# Открыть http://localhost:8000/docs

# 13. Пушим в GitHub
git add . && git commit -m "feat: initial project setup" && git push -u origin main
```

### Критерий успеха дня 1

- [ ] `docker compose up -d` поднимает весь стек без ошибок
- [ ] `GET /health` возвращает `{"status": "ok", "db": "ok", "redis": "ok"}`
- [ ] `POST /posts` создаёт черновик в БД
- [ ] `GET /posts` возвращает список постов
- [ ] Swagger UI доступен на `/docs`

---

## Приложение: Ключевые зависимости

### Backend (`pyproject.toml`)

```toml
[project]
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pydantic-settings>=2.2",
    "celery[redis]>=5.3",
    "redis>=5.0",
    "boto3>=1.34",
    "httpx>=0.27",
    "pillow>=10.3",
    "cryptography>=42.0",
    "fastapi-mail>=1.4",
    "python-multipart>=0.0.9",
]
```

### Frontend (`package.json` — ключевые)

```json
{
  "dependencies": {
    "next": "14",
    "@tanstack/react-query": "^5",
    "@dnd-kit/core": "^6",
    "@dnd-kit/sortable": "^8",
    "recharts": "^2",
    "react-dropzone": "^14",
    "date-fns": "^3",
    "lucide-react": "^0.378"
  }
}
```

---

## Итоговый таймлайн

| Этап | Срок | Результат |
|------|------|-----------|
| Фаза 0: Инфраструктура | Нед. 1 | Работающий стек, health check |
| Фаза 1: MVP | Нед. 2–4 | Публикация в Instagram по расписанию |
| Фаза 2: v1.0 | Нед. 5–9 | AI, медиа-библиотека, календарь, аналитика |
| Фаза 3: v2.0 | Нед. 10–13 | Twitter/X, LinkedIn, серии, расширенная аналитика |

**Общий срок до v2.0: ~13 недель при 6 часах работы в день.**
