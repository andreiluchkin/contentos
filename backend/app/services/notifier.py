import logging
from datetime import datetime, timezone

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

_BASE = "https://api.telegram.org/bot"


async def _send(text: str, parse_mode: str = "HTML") -> bool:
    if not settings.telegram_bot_token or not settings.telegram_notify_chat_id:
        logger.debug("Telegram notifier not configured, skipping")
        return False
    url = f"{_BASE}{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json={
                "chat_id": settings.telegram_notify_chat_id,
                "text": text,
                "parse_mode": parse_mode,
            })
            r.raise_for_status()
            return True
    except Exception as e:
        logger.warning("Telegram notify failed: %s", e)
        return False


PLATFORM_EMOJI = {
    "telegram": "✈️",
    "instagram": "📸",
    "tiktok": "🎵",
    "youtube": "▶️",
    "linkedin": "💼",
    "x": "🐦",
}


async def notify_published(post_id: str, platform: str, handle: str, body_preview: str, external_id: str | None) -> bool:
    emoji = PLATFORM_EMOJI.get(platform, "📢")
    text = (
        f"{emoji} <b>Пост опубликован</b>\n"
        f"@{handle} · {platform}\n\n"
        f"{body_preview[:200]}{'…' if len(body_preview) > 200 else ''}"
    )
    if external_id:
        text += f"\n\n<code>{external_id}</code>"
    return await _send(text)


async def notify_error(post_id: str, platform: str, handle: str, error: str) -> bool:
    emoji = PLATFORM_EMOJI.get(platform, "📢")
    text = (
        f"❌ <b>Ошибка публикации</b>\n"
        f"{emoji} @{handle} · {platform}\n\n"
        f"<code>{error[:400]}</code>\n\n"
        f"Post ID: <code>{post_id}</code>"
    )
    return await _send(text)


async def send_daily_digest(stats: dict) -> bool:
    """stats: {total, published_today, score_avg, top_platform, pending_review}"""
    lines = ["📊 <b>Дайджест ContentOS</b>", ""]
    lines.append(f"📝 Всего постов: <b>{stats.get('total', 0)}</b>")
    lines.append(f"✅ Опубликовано сегодня: <b>{stats.get('published_today', 0)}</b>")
    lines.append(f"⏳ На проверке: <b>{stats.get('pending_review', 0)}</b>")
    if stats.get("score_avg"):
        lines.append(f"⭐ Средний Score: <b>{stats['score_avg']}</b>")
    if stats.get("top_platform"):
        emoji = PLATFORM_EMOJI.get(stats["top_platform"], "")
        lines.append(f"🏆 Топ платформа: {emoji} <b>{stats['top_platform']}</b>")
    lines.append(f"\n🕐 {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC")
    return await _send("\n".join(lines))
