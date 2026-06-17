"use client"

import { useState } from "react"
import { ChevronDown, ChevronUp, Check, X, ExternalLink } from "lucide-react"
import { cn, formatRelative, PLATFORM_LABELS, CONTENT_TYPE_LABELS } from "@/lib/utils"
import { PlatformIcon } from "@/components/shared/PlatformIcon"
import type { Idea, ContentPillar } from "@/lib/types"

interface Props {
  idea: Idea
  pillar?: ContentPillar
  selected: boolean
  onSelect: (id: string, checked: boolean) => void
  onApprove: (id: string) => void
  onReject: (id: string) => void
}

export function IdeaCard({ idea, pillar, selected, onSelect, onApprove, onReject }: Props) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className={cn(
        "card p-4 transition-shadow duration-150 hover:shadow-card-hover",
        selected && "ring-2 ring-accent"
      )}
    >
      <div className="flex items-start gap-3">
        {/* Чекбокс */}
        <input
          type="checkbox"
          checked={selected}
          onChange={(e) => onSelect(idea.id, e.target.checked)}
          className="mt-0.5 w-4 h-4 accent-accent cursor-pointer shrink-0"
        />

        <div className="flex-1 min-w-0">
          {/* Заголовок */}
          <p className="text-sm font-medium text-ink leading-snug">{idea.title}</p>

          {/* Мета */}
          <div className="flex flex-wrap items-center gap-2 mt-2">
            {idea.suggested_platform && (
              <div className="flex items-center gap-1">
                <PlatformIcon platform={idea.suggested_platform} size="sm" />
                <span className="text-xs text-ink-secondary">
                  {PLATFORM_LABELS[idea.suggested_platform]}
                </span>
              </div>
            )}
            {idea.suggested_content_type && (
              <span className="platform-chip">
                {CONTENT_TYPE_LABELS[idea.suggested_content_type]}
              </span>
            )}
            {pillar && (
              <span
                className="platform-chip"
                style={{ borderColor: pillar.color, color: pillar.color }}
              >
                {pillar.name}
              </span>
            )}
            {idea.relevance_score !== null && (
              <span className="text-xs text-ink-secondary tabular-nums">
                {Math.round((idea.relevance_score ?? 0) * 100)}% релевантность
              </span>
            )}
          </div>

          {/* Контекст */}
          {idea.context && (
            <div className="mt-2">
              <p className={cn("text-xs text-ink-secondary leading-relaxed", !expanded && "line-clamp-2")}>
                {idea.context}
              </p>
              {idea.context.length > 120 && (
                <button
                  onClick={() => setExpanded(!expanded)}
                  className="flex items-center gap-1 mt-1 text-xs text-accent hover:text-accent/80"
                >
                  {expanded ? (
                    <><ChevronUp size={12} />Свернуть</>
                  ) : (
                    <><ChevronDown size={12} />Развернуть</>
                  )}
                </button>
              )}
            </div>
          )}

          {/* Источник + время */}
          <div className="flex items-center justify-between mt-3">
            <div className="flex items-center gap-2">
              {idea.source_name && (
                <span className="text-xs text-ink-secondary capitalize">{idea.source_name}</span>
              )}
              {idea.source_url && (
                <a
                  href={idea.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ink-secondary hover:text-accent"
                >
                  <ExternalLink size={11} />
                </a>
              )}
            </div>
            <span className="text-xs text-ink-secondary">{formatRelative(idea.created_at)}</span>
          </div>
        </div>

        {/* Кнопки действий */}
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => onApprove(idea.id)}
            className="flex items-center justify-center w-8 h-8 rounded-nav bg-green-50 text-green-600 hover:bg-green-100 transition-colors"
            title="Одобрить"
          >
            <Check size={15} strokeWidth={2.5} />
          </button>
          <button
            onClick={() => onReject(idea.id)}
            className="flex items-center justify-center w-8 h-8 rounded-nav bg-gray-50 text-ink-secondary hover:bg-red-50 hover:text-red-500 transition-colors"
            title="Отклонить"
          >
            <X size={15} strokeWidth={2.5} />
          </button>
        </div>
      </div>
    </div>
  )
}
