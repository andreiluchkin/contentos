import logging

import httpx

from .base import PlatformAdapter, PublishResult, Metrics, ValidationResult

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}"
MAX_TEXT_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024


class TelegramAdapter(PlatformAdapter):
    platform = "telegram"

    async def publish_post(self, post, account) -> PublishResult:
        bot_token = account.platform_meta.get("bot_token", "")
        chat_id = account.platform_meta.get("chat_id", "")
        base_url = TELEGRAM_API.format(token=bot_token)

        body = self._truncate(post.body, MAX_TEXT_LENGTH)

        # Разбиваем на части если текст превышает лимит
        chunks = self._split_text(post.body)

        async with httpx.AsyncClient(timeout=30.0) as client:
            first_message_id = None

            for i, chunk in enumerate(chunks):
                payload = {
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "Markdown",
                }
                # Для частей треда — reply на первое сообщение
                if i > 0 and first_message_id:
                    payload["reply_to_message_id"] = first_message_id

                try:
                    resp = await client.post(f"{base_url}/sendMessage", json=payload)
                    data = resp.json()

                    if not data.get("ok"):
                        error = data.get("description", "Unknown Telegram error")
                        logger.error("Telegram publish failed: %s", error)
                        return PublishResult(success=False, error=error)

                    if i == 0:
                        first_message_id = str(data["result"]["message_id"])

                except httpx.RequestError as e:
                    return PublishResult(success=False, error=f"Network error: {e}")

        return PublishResult(
            success=True,
            external_post_id=first_message_id,
            external_url=f"https://t.me/{account.handle}/{first_message_id}",
        )

    async def delete_post(self, external_post_id: str, account) -> bool:
        bot_token = account.platform_meta.get("bot_token", "")
        chat_id = account.platform_meta.get("chat_id", "")
        base_url = TELEGRAM_API.format(token=bot_token)

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{base_url}/deleteMessage",
                json={"chat_id": chat_id, "message_id": int(external_post_id)},
            )
            return resp.json().get("ok", False)

    async def get_metrics(self, external_post_id: str, account) -> Metrics:
        # Telegram Bot API не предоставляет метрики для обычных постов
        return Metrics()

    async def validate_content(self, post) -> ValidationResult:
        errors = []
        if not post.body or not post.body.strip():
            errors.append("Текст поста не может быть пустым")
        if len(post.body) > MAX_TEXT_LENGTH * 10:
            errors.append(f"Текст слишком длинный даже для разбивки на части")
        return ValidationResult(valid=not errors, errors=errors)

    async def refresh_token(self, account):
        # Telegram Bot API токены не истекают
        return account

    async def validate_account(self, account) -> bool:
        bot_token = account.platform_meta.get("bot_token", "")
        if not bot_token:
            return False
        base_url = TELEGRAM_API.format(token=bot_token)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{base_url}/getMe")
            return resp.json().get("ok", False)

    def _split_text(self, text: str) -> list[str]:
        """Разбивает текст на части по MAX_TEXT_LENGTH символов, не разрывая слова."""
        if len(text) <= MAX_TEXT_LENGTH:
            return [text]

        parts = []
        while text:
            if len(text) <= MAX_TEXT_LENGTH:
                parts.append(text)
                break
            # Ищем последний перенос строки в пределах лимита
            split_at = text.rfind("\n", 0, MAX_TEXT_LENGTH)
            if split_at == -1:
                split_at = text.rfind(" ", 0, MAX_TEXT_LENGTH)
            if split_at == -1:
                split_at = MAX_TEXT_LENGTH
            parts.append(text[:split_at].rstrip())
            text = text[split_at:].lstrip()

        return parts

    def _truncate(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit - 3] + "..."
