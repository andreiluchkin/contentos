"""
ScoringService — рассчитывает Content Score через OpenRouter API.
5 критериев, weighted average, конкретные issues.
"""
import json
import logging
from dataclasses import dataclass, field

from openai import OpenAI

from ..config import settings
from .templates import PLATFORM_TEMPLATES, SCORE_WEIGHTS

logger = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    hook: int
    structure: int
    readability: int
    cta: int
    platform_fit: int
    content_score: int
    issues: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)


SCORE_PROMPT = """\
Оцени этот пост для платформы {platform} по 5 критериям. Каждый критерий: от 0 до 100.

Пост:
---
{body}
---

Критерии:
- hook: Насколько сильное начало? Захочет ли читатель читать дальше после первого абзаца?
- structure: Есть ли чёткая логическая структура? Мысли идут последовательно?
- readability: Легко ли читается? Нет ли воды, длинных предложений, канцелярщины?
- cta: Есть ли призыв к действию или сильный завершающий вывод?
- platform_fit: Соответствует ли формат, длина и стиль правилам {platform}?

Правила {platform}:
{platform_rules}

Ответь строго в JSON без дополнительного текста:
{{
  "hook": <0-100>,
  "structure": <0-100>,
  "readability": <0-100>,
  "cta": <0-100>,
  "platform_fit": <0-100>,
  "issues": ["конкретная проблема 1", "конкретная проблема 2"],
  "strengths": ["что хорошо 1"]
}}

Правила для issues:
- Конкретно: "Слабый первый абзац — первая фраза не даёт причины читать дальше" ✓
- НЕ абстрактно: "Нужно улучшить качество текста" ✗
- Максимум 3 issues. Если всё хорошо — пустой массив [].
- Пиши issues на русском языке.
"""


class ScoringService:
    def __init__(self):
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if not self._client:
            self._client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.openrouter_api_key,
            )
        return self._client

    async def calculate_score(self, body: str, platform: str) -> ScoreResult:
        pt = PLATFORM_TEMPLATES.get(platform, {})
        platform_rules = "\n".join(
            f"• {r}" for r in pt.get("format_rules", ["Нет специфичных правил"])
        )

        prompt = SCORE_PROMPT.format(
            platform=pt.get("name", platform),
            body=body[:3000],  # обрезаем для экономии токенов
            platform_rules=platform_rules,
        )

        try:
            response = self.client.chat.completions.create(
                model=settings.openrouter_model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Scoring API call failed: %s", e)
            raise

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Пробуем вырезать JSON из ответа
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
            else:
                logger.error("Could not parse score response: %s", raw)
                raise ValueError(f"Invalid score response: {raw[:200]}")

        hook = int(data.get("hook", 50))
        structure = int(data.get("structure", 50))
        readability = int(data.get("readability", 50))
        cta = int(data.get("cta", 50))
        platform_fit = int(data.get("platform_fit", 50))

        weighted = (
            hook * SCORE_WEIGHTS["hook"]
            + structure * SCORE_WEIGHTS["structure"]
            + readability * SCORE_WEIGHTS["readability"]
            + cta * SCORE_WEIGHTS["cta"]
            + platform_fit * SCORE_WEIGHTS["platform_fit"]
        )

        return ScoreResult(
            hook=hook,
            structure=structure,
            readability=readability,
            cta=cta,
            platform_fit=platform_fit,
            content_score=round(weighted),
            issues=data.get("issues", []),
            strengths=data.get("strengths", []),
        )
