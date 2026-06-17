from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


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
    collected_at: datetime | None = None


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


class PlatformAdapter(ABC):
    platform: str

    @abstractmethod
    async def publish_post(self, post, account) -> PublishResult:
        """Публикует пост. Идемпотентен — проверяет external_post_id."""

    @abstractmethod
    async def delete_post(self, external_post_id: str, account) -> bool:
        """Удаляет пост из соцсети."""

    @abstractmethod
    async def get_metrics(self, external_post_id: str, account) -> Metrics:
        """Возвращает метрики поста."""

    @abstractmethod
    async def validate_content(self, post) -> ValidationResult:
        """Проверяет контент до публикации (лимиты, форматы)."""

    @abstractmethod
    async def refresh_token(self, account):
        """Обновляет OAuth токен. Возвращает обновлённый account."""

    @abstractmethod
    async def validate_account(self, account) -> bool:
        """Проверяет что токен актуален."""
