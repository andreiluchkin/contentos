"use client"

import { useState } from "react"
import { Loader2, Sparkles, TrendingUp } from "lucide-react"
import { cn, scoreColor } from "@/lib/utils"
import type { Post, ContentScore } from "@/lib/types"

interface Props {
  post: Post
  onScore: () => Promise<ContentScore>
  onImprove: (issues: string[]) => Promise<void>
}

const CRITERIA = [
  { key: "score_hook" as const, label: "Hook", hint: "Насколько сильное начало?" },
  { key: "score_structure" as const, label: "Структура", hint: "Логичность и последовательность" },
  { key: "score_readability" as const, label: "Читабельность", hint: "Лёгкость восприятия" },
  { key: "score_cta" as const, label: "CTA", hint: "Есть ли призыв или вывод?" },
  { key: "score_platform_fit" as const, label: "Платформа", hint: "Соответствие формату" },
]

export function ContentScorePanel({ post, onScore, onImprove }: Props) {
  const [loading, setLoading] = useState(false)
  const [improving, setImproving] = useState(false)
  const [score, setScore] = useState<ContentScore | null>(
    post.content_score !== null
      ? {
          content_score: post.content_score!,
          score_hook: post.score_hook!,
          score_structure: post.score_structure!,
          score_readability: post.score_readability!,
          score_cta: post.score_cta!,
          score_platform_fit: post.score_platform_fit!,
          score_issues: post.score_issues,
        }
      : null
  )

  async function handleScore() {
    setLoading(true)
    try {
      const result = await onScore()
      setScore(result)
    } finally {
      setLoading(false)
    }
  }

  async function handleImprove() {
    if (!score?.score_issues.length) return
    setImproving(true)
    try {
      await onImprove(score.score_issues)
      // Score пересчитается через polling
      setTimeout(() => setScore(null), 500)
    } finally {
      setImproving(false)
    }
  }

  if (!score) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-12 px-6 text-center">
        <div className="w-12 h-12 rounded-full bg-accent-light flex items-center justify-center mb-4">
          <Sparkles size={20} className="text-accent" />
        </div>
        <p className="text-sm font-medium text-ink mb-1">Content Score</p>
        <p className="text-xs text-ink-secondary mb-6 max-w-[200px]">
          Оцени пост по 5 критериям — Hook, Структура, Читабельность, CTA, Платформа
        </p>
        <button
          onClick={handleScore}
          disabled={loading || !post.body}
          className="btn-primary flex items-center gap-2"
        >
          {loading ? (
            <><Loader2 size={14} className="animate-spin" />Анализирую...</>
          ) : (
            <><Sparkles size={14} />Рассчитать Score</>
          )}
        </button>
      </div>
    )
  }

  const totalScore = score.content_score

  return (
    <div className="p-5 h-full overflow-y-auto">
      {/* Итоговый score */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <p className="text-xs text-ink-secondary mb-1">Content Score</p>
          <div className="flex items-end gap-2">
            <span className={cn("text-4xl font-bold tabular-nums", scoreColor(totalScore))}>
              {totalScore}
            </span>
            <span className="text-sm text-ink-secondary mb-1">/ 100</span>
          </div>
        </div>
        <button
          onClick={handleScore}
          disabled={loading}
          className="btn-ghost flex items-center gap-1.5 text-xs"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <TrendingUp size={12} />}
          Пересчитать
        </button>
      </div>

      {/* Метрики */}
      <div className="space-y-3 mb-5">
        {CRITERIA.map(({ key, label, hint }) => {
          const val = score[key as keyof ContentScore] as number
          return (
            <div key={key}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-ink">{label}</span>
                <span className={cn("text-xs font-semibold tabular-nums", scoreColor(val))}>
                  {val}
                </span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-500",
                    val >= 80 ? "bg-green-500" : val >= 60 ? "bg-amber-400" : "bg-red-400"
                  )}
                  style={{ width: `${val}%` }}
                />
              </div>
              <p className="text-[10px] text-ink-secondary mt-0.5">{hint}</p>
            </div>
          )
        })}
      </div>

      {/* Issues */}
      {score.score_issues.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-medium text-ink mb-2">Что улучшить:</p>
          <ul className="space-y-2">
            {score.score_issues.map((issue, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-ink-secondary leading-relaxed">
                <span className="text-red-400 mt-0.5 shrink-0">•</span>
                {issue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Кнопка улучшить */}
      {score.score_issues.length > 0 && (
        <button
          onClick={handleImprove}
          disabled={improving}
          className="btn-primary w-full flex items-center justify-center gap-2"
        >
          {improving ? (
            <><Loader2 size={14} className="animate-spin" />Улучшаю...</>
          ) : (
            <><Sparkles size={14} />Улучшить пост</>
          )}
        </button>
      )}

      {score.score_issues.length === 0 && (
        <div className="text-center py-2 text-xs text-green-600 font-medium">
          ✓ Пост готов к публикации
        </div>
      )}
    </div>
  )
}
