"""
GenerationService — генерирует посты через Anthropic API.
Использует Brand Voice system prompt + KB контекст + шаблоны платформ.
"""
import json
import logging
from dataclasses import dataclass

import anthropic

from ..config import settings
from .templates import CONTENT_TYPE_TEMPLATES, PLATFORM_TEMPLATES

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2000


@dataclass
class GenerationResult:
    body: str
    platform_meta: dict
    hashtags: list[str]


class GenerationService:
    def __init__(self):
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        if not self._client:
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def generate_post(
        self,
        topic: str,
        platform: str,
        content_type: str,
        brand_voice_prompt: str,
        kb_context: str = "",
        source_context: str = "",
    ) -> GenerationResult:
        ct = CONTENT_TYPE_TEMPLATES.get(content_type, {})
        pt = PLATFORM_TEMPLATES.get(platform, {})

        structure_block = ""
        if ct.get("structure"):
            structure_block = "Структура поста:\n" + "\n".join(
                f"  {i+1}. {s}" for i, s in enumerate(ct["structure"])
            )

        rules_block = ""
        if pt.get("format_rules"):
            rules_block = "Правила форматирования:\n" + "\n".join(
                f"  • {r}" for r in pt["format_rules"]
            )

        length = pt.get("length", {})
        length_hint = f"Длина: {length.get('min', 300)}–{length.get('max', 1500)} символов."

        kb_block = f"\nКонтекст из базы знаний автора:\n{kb_context}\n" if kb_context else ""
        source_block = f"\nИсточник/контекст:\n{source_context}\n" if source_context else ""

        user_prompt = f"""Напиши пост для {pt.get('name', platform)}.

Тип контента: {ct.get('name', content_type)}
Тема: {topic}
{source_block}{kb_block}
{structure_block}

{rules_block}

{ct.get('instruction', '')}

{length_hint}

Ответь ТОЛЬКО текстом поста, без пояснений и без кавычек.
{"Верни JSON: {\"body\": \"...\", \"hashtags\": [...]}" if platform == "instagram" else "Для треда разделяй твиты строкой ---. Каждый твит ≤ 280 символов. Верни только текст." if platform == "x" else "Верни только текст поста."}"""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=brand_voice_prompt or self._default_system_prompt(),
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text.strip()
        except Exception as e:
            logger.error("Generation failed: %s", e)
            raise

        # Для Instagram парсим JSON с хэштегами
        if platform == "instagram":
            try:
                parsed = json.loads(raw)
                return GenerationResult(
                    body=parsed.get("body", raw),
                    hashtags=parsed.get("hashtags", []),
                    platform_meta={},
                )
            except json.JSONDecodeError:
                pass

        platform_meta = {}

        # TikTok: кладём текст в platform_meta.script
        if platform == "tiktok":
            platform_meta = {"script": raw}

        # X: если в тексте есть разделители "---", собираем тред
        if platform == "x":
            parts = [p.strip() for p in raw.split("\n---\n") if p.strip()]
            if len(parts) > 1:
                platform_meta = {"thread": parts}
                raw = parts[0]  # body = первый твит

        return GenerationResult(body=raw, hashtags=[], platform_meta=platform_meta)

    def _default_system_prompt(self) -> str:
        return (
            "Ты — профессиональный автор контента. "
            "Пишешь чётко, конкретно, без воды. "
            "Используешь личный опыт и факты. "
            "Избегаешь банальностей и корпоратщины."
        )

    def build_brand_voice_prompt(self, brand_voice) -> str:
        """Собирает system prompt из модели BrandVoice."""
        parts = []

        if brand_voice.tone:
            parts.append(f"Стиль и тон автора:\n{brand_voice.tone}")

        if brand_voice.forbidden_words:
            words = ", ".join(brand_voice.forbidden_words)
            parts.append(f"Запрещённые слова и выражения (никогда не используй): {words}")

        if brand_voice.preferred_patterns:
            patterns = ", ".join(brand_voice.preferred_patterns)
            parts.append(f"Любимые конструкции автора: {patterns}")

        if brand_voice.length_preferences:
            prefs = []
            for platform, pref in brand_voice.length_preferences.items():
                prefs.append(f"{platform}: {pref.get('min', '?')}–{pref.get('max', '?')} символов")
            parts.append("Предпочтения по длине:\n" + "\n".join(prefs))

        if brand_voice.example_posts:
            examples = brand_voice.example_posts[:2]
            ex_texts = []
            for ex in examples:
                text = ex.get("text", "")[:500]
                platform = ex.get("platform", "")
                ex_texts.append(f"[{platform}] {text}")
            parts.append("Примеры постов автора (пиши в похожем стиле):\n\n" + "\n\n---\n\n".join(ex_texts))

        if not parts:
            return self._default_system_prompt()

        return (
            "Ты пишешь от лица автора. Точно следуй его стилю.\n\n"
            + "\n\n".join(parts)
        )
