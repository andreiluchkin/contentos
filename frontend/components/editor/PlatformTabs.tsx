"use client"

import { useState, useEffect, useCallback } from "react"
import { Sparkles, Loader2, Hash, AlertCircle } from "lucide-react"
import { PlatformIcon } from "@/components/shared/PlatformIcon"
import { cn, PLATFORM_LABELS } from "@/lib/utils"
import type { Platform } from "@/lib/types"

const PLATFORM_LIMITS: Record<Platform, { min: number; max: number; label: string }> = {
  telegram:  { min: 600,  max: 1800, label: "600–1800 символов" },
  instagram: { min: 80,   max: 2200, label: "≤ 2200 символов + хэштеги" },
  linkedin:  { min: 400,  max: 3000, label: "400–3000 символов" },
  x:         { min: 50,   max: 280,  label: "≤ 280 символов (тред)" },
  tiktok:    { min: 0,    max: 2200, label: "Текст сценария" },
  youtube:   { min: 100,  max: 5000, label: "Описание + таймкоды" },
}

interface PlatformTabState {
  body: string
  hashtags: string  // строка для редактирования, разбиваем по пробелам
}

interface PlatformTabsProps {
  platforms: Platform[]
  primaryPlatform: Platform
  initialBodies: Record<Platform, string>
  initialHashtags: Record<Platform, string[]>
  onTabChange: (platform: Platform, body: string, hashtags: string[]) => void
  onGenerate: (platform: Platform) => Promise<void>
  generatingPlatform: Platform | null
  readOnly?: boolean
}

export function PlatformTabs({
  platforms,
  primaryPlatform,
  initialBodies,
  initialHashtags,
  onTabChange,
  onGenerate,
  generatingPlatform,
  readOnly = false,
}: PlatformTabsProps) {
  const [active, setActive] = useState<Platform>(primaryPlatform)
  const [tabs, setTabs] = useState<Record<Platform, PlatformTabState>>(() => {
    const init = {} as Record<Platform, PlatformTabState>
    for (const p of platforms) {
      init[p] = {
        body: initialBodies[p] ?? "",
        hashtags: (initialHashtags[p] ?? []).join(" "),
      }
    }
    return init
  })

  // Обновляем если внешние данные изменились (после generate)
  useEffect(() => {
    setTabs((prev) => {
      const next = { ...prev }
      for (const p of platforms) {
        const newBody = initialBodies[p] ?? ""
        const newHashtags = (initialHashtags[p] ?? []).join(" ")
        if (next[p]?.body !== newBody || next[p]?.hashtags !== newHashtags) {
          next[p] = { body: newBody, hashtags: newHashtags }
        }
      }
      return next
    })
  }, [initialBodies, initialHashtags, platforms])

  const handleBodyChange = useCallback(
    (platform: Platform, val: string) => {
      setTabs((prev) => ({ ...prev, [platform]: { ...prev[platform], body: val } }))
      const hashtags = tabs[platform]?.hashtags?.split(/\s+/).filter(Boolean) ?? []
      onTabChange(platform, val, hashtags)
    },
    [tabs, onTabChange]
  )

  const handleHashtagsChange = useCallback(
    (platform: Platform, val: string) => {
      setTabs((prev) => ({ ...prev, [platform]: { ...prev[platform], hashtags: val } }))
      const body = tabs[platform]?.body ?? ""
      const hashtags = val.split(/\s+/).filter(Boolean)
      onTabChange(platform, body, hashtags)
    },
    [tabs, onTabChange]
  )

  const current = tabs[active] ?? { body: "", hashtags: "" }
  const limits = PLATFORM_LIMITS[active]
  const charCount = current.body.length
  const isOverLimit = charCount > limits.max
  const isBelowMin = limits.min > 0 && charCount > 0 && charCount < limits.min
  const hashtagCount = current.hashtags.split(/\s+/).filter((w) => w.length > 0).length

  return (
    <div className="flex flex-col flex-1 min-w-0">
      {/* Tab bar */}
      <div className="flex items-center gap-0.5 px-4 pt-3 pb-0 border-b border-border bg-white shrink-0 overflow-x-auto">
        {platforms.map((p) => {
          const tabBody = tabs[p]?.body ?? ""
          const hasContent = tabBody.length > 0
          const isActive = active === p

          return (
            <button
              key={p}
              onClick={() => setActive(p)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium rounded-t-sm transition-all shrink-0",
                "border-b-2 -mb-px",
                isActive
                  ? "border-accent text-accent bg-white"
                  : "border-transparent text-ink-secondary hover:text-ink hover:bg-canvas"
              )}
            >
              <PlatformIcon platform={p} size="sm" />
              <span>{PLATFORM_LABELS[p]}</span>
              {hasContent && !isActive && (
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 shrink-0" />
              )}
              {p === primaryPlatform && (
                <span className="text-[9px] text-accent/70 font-normal ml-0.5">(осн.)</span>
              )}
            </button>
          )
        })}
      </div>

      {/* Editor area */}
      <div className="flex flex-col flex-1 overflow-hidden">
        <textarea
          key={active}
          value={current.body}
          onChange={(e) => handleBodyChange(active, e.target.value)}
          placeholder={`Текст для ${PLATFORM_LABELS[active]}...`}
          disabled={readOnly}
          className="flex-1 resize-none p-5 text-sm text-ink leading-relaxed bg-white outline-none font-ui placeholder:text-ink-secondary disabled:opacity-60"
        />

        {/* X thread hint */}
        {active === "x" && current.body.length > 0 && (
          <div className="px-5 py-2.5 border-t border-border bg-canvas shrink-0">
            <p className="text-[11px] text-ink-secondary">
              Тред: раздели твиты символом <code className="bg-white border border-border px-1 rounded text-[10px]">---</code>.
              Каждая часть ≤ 280 символов.
            </p>
          </div>
        )}

        {/* Instagram hashtags field */}
        {active === "instagram" && (
          <div className="px-5 py-3 border-t border-border bg-canvas shrink-0">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Hash size={11} className="text-ink-secondary" />
              <span className="text-xs text-ink-secondary font-medium">
                Хэштеги ({hashtagCount}/30)
              </span>
              {hashtagCount > 30 && (
                <span className="flex items-center gap-0.5 text-[10px] text-red-500">
                  <AlertCircle size={10} />
                  Превышен лимит
                </span>
              )}
            </div>
            <input
              value={current.hashtags}
              onChange={(e) => handleHashtagsChange(active, e.target.value)}
              placeholder="#контент #маркетинг #продвижение"
              disabled={readOnly}
              className="input-base w-full text-xs py-2"
            />
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-2.5 border-t border-border bg-white shrink-0">
          <div className="flex items-center gap-3">
            <span className={cn(
              "text-xs tabular-nums",
              isOverLimit ? "text-red-500 font-medium" :
              isBelowMin ? "text-amber-500" : "text-ink-secondary"
            )}>
              {charCount.toLocaleString()} символов
            </span>
            <span className="text-[10px] text-ink-secondary/70">{limits.label}</span>
          </div>

          {!readOnly && (
            <button
              onClick={() => onGenerate(active)}
              disabled={generatingPlatform !== null}
              className="flex items-center gap-1.5 btn-ghost text-xs py-1.5 px-3 text-accent hover:bg-accent/10"
            >
              {generatingPlatform === active ? (
                <Loader2 size={11} className="animate-spin" />
              ) : (
                <Sparkles size={11} />
              )}
              Сгенерировать для {PLATFORM_LABELS[active]}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
