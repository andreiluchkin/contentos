"use client"

import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Plus, X, Sparkles, Save, Loader2, RefreshCw, ChevronDown, ChevronUp, Info,
} from "lucide-react"
import { brandVoiceApi } from "@/lib/api"
import { PLATFORM_LABELS, cn } from "@/lib/utils"
import type { Platform } from "@/lib/types"

interface BrandVoice {
  tone: string
  length_preferences: Record<string, unknown>
  forbidden_words: string[]
  preferred_patterns: string[]
  example_posts: { text: string; platform: string; added_at: string }[]
  system_prompt_cache: string | null
  system_prompt_updated_at: string | null
}

const TONE_PRESETS = [
  "Прямой и честный",
  "Дружелюбный эксперт",
  "Провокационный",
  "Вдохновляющий",
  "Аналитический",
  "Разговорный",
]

const PATTERN_SUGGESTIONS = [
  "Начинать с цифры или факта",
  "Задавать вопрос в начале",
  "История → урок → вывод",
  "Противоречие → объяснение",
  "Список с нумерацией",
  "Личный опыт → совет",
]

const PLATFORM_LIST = ["telegram", "instagram", "linkedin", "x", "tiktok", "youtube"] as Platform[]

export default function BrandVoicePage() {
  const qc = useQueryClient()
  const { data: bv, isLoading } = useQuery<BrandVoice>({
    queryKey: ["brand-voice"],
    queryFn: () => brandVoiceApi.get(),
  })

  const [tone, setTone] = useState("")
  const [forbiddenInput, setForbiddenInput] = useState("")
  const [patternInput, setPatternInput] = useState("")
  const [isDirty, setIsDirty] = useState(false)
  const [showPrompt, setShowPrompt] = useState(false)

  // Форма для примера поста
  const [exampleText, setExampleText] = useState("")
  const [examplePlatform, setExamplePlatform] = useState<Platform>("telegram")

  useEffect(() => {
    if (bv) {
      setTone(bv.tone)
      setIsDirty(false)
    }
  }, [bv])

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => brandVoiceApi.update(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["brand-voice"] }); setIsDirty(false) },
  })

  const addExampleMutation = useMutation({
    mutationFn: ({ text, platform }: { text: string; platform: string }) =>
      brandVoiceApi.addExample(text, platform),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["brand-voice"] })
      setExampleText("")
    },
  })

  const deleteExampleMutation = useMutation({
    mutationFn: (index: number) => brandVoiceApi.deleteExample(index),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["brand-voice"] }),
  })

  const regenerateMutation = useMutation({
    mutationFn: () => brandVoiceApi.regeneratePrompt(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["brand-voice"] }),
  })

  function handleSave() {
    if (!bv) return
    updateMutation.mutate({
      tone,
      forbidden_words: bv.forbidden_words,
      preferred_patterns: bv.preferred_patterns,
    })
  }

  function addForbiddenWord() {
    const word = forbiddenInput.trim()
    if (!word || !bv) return
    const words = [...bv.forbidden_words]
    if (!words.includes(word)) {
      updateMutation.mutate({ forbidden_words: [...words, word] })
    }
    setForbiddenInput("")
  }

  function removeForbiddenWord(word: string) {
    if (!bv) return
    updateMutation.mutate({ forbidden_words: bv.forbidden_words.filter((w) => w !== word) })
  }

  function addPattern(pattern: string) {
    if (!bv) return
    const patterns = [...bv.preferred_patterns]
    if (!patterns.includes(pattern)) {
      updateMutation.mutate({ preferred_patterns: [...patterns, pattern] })
    }
    setPatternInput("")
  }

  function removePattern(pattern: string) {
    if (!bv) return
    updateMutation.mutate({ preferred_patterns: bv.preferred_patterns.filter((p) => p !== pattern) })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={24} className="animate-spin text-ink-secondary" />
      </div>
    )
  }

  if (!bv) return null

  const promptAge = bv.system_prompt_updated_at
    ? Math.round((Date.now() - new Date(bv.system_prompt_updated_at).getTime()) / 3600000)
    : null

  return (
    <div className="flex h-full overflow-hidden">
      {/* Main scroll area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-2xl mx-auto space-y-6">

          <div>
            <h1 className="text-xl font-semibold text-ink mb-1">Brand Voice</h1>
            <p className="text-sm text-ink-secondary">
              Настрой свой голос — он будет применяться во всех AI-генерациях
            </p>
          </div>

          {/* Тон */}
          <section className="card space-y-4">
            <h2 className="text-sm font-semibold text-ink">Тон голоса</h2>

            <div className="flex flex-wrap gap-2">
              {TONE_PRESETS.map((preset) => (
                <button
                  key={preset}
                  onClick={() => { setTone(preset); setIsDirty(true) }}
                  className={cn(
                    "text-xs px-3 py-1.5 rounded-full border transition-all",
                    tone === preset
                      ? "border-accent bg-accent/10 text-accent"
                      : "border-border text-ink-secondary hover:border-border-strong hover:text-ink"
                  )}
                >
                  {preset}
                </button>
              ))}
            </div>

            <div>
              <label className="block text-xs text-ink-secondary mb-1.5">Или опиши свой тон</label>
              <textarea
                value={tone}
                onChange={(e) => { setTone(e.target.value); setIsDirty(true) }}
                rows={3}
                placeholder="Например: Говорю как эксперт-практик без воды. Использую конкретные цифры. Не боюсь противоречить мейнстриму."
                className="input-base w-full resize-none text-sm leading-relaxed"
              />
            </div>

            <button
              onClick={handleSave}
              disabled={!isDirty || updateMutation.isPending}
              className="btn-primary flex items-center gap-1.5 text-sm"
            >
              {updateMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
              {isDirty ? "Сохранить тон" : "Сохранено"}
            </button>
          </section>

          {/* Запрещённые слова */}
          <section className="card space-y-4">
            <h2 className="text-sm font-semibold text-ink">Запрещённые слова</h2>
            <p className="text-xs text-ink-secondary -mt-2">
              AI никогда не будет использовать эти слова в генерациях
            </p>

            <div className="flex flex-wrap gap-2 min-h-[32px]">
              {bv.forbidden_words.map((word) => (
                <span
                  key={word}
                  className="flex items-center gap-1 text-xs bg-red-50 text-red-700 border border-red-200 px-2.5 py-1 rounded-full"
                >
                  {word}
                  <button onClick={() => removeForbiddenWord(word)} className="hover:text-red-900">
                    <X size={11} />
                  </button>
                </span>
              ))}
              {bv.forbidden_words.length === 0 && (
                <p className="text-xs text-ink-secondary italic">Нет запрещённых слов</p>
              )}
            </div>

            <div className="flex gap-2">
              <input
                value={forbiddenInput}
                onChange={(e) => setForbiddenInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addForbiddenWord()}
                placeholder="Добавить слово..."
                className="input-base flex-1 text-sm"
              />
              <button
                onClick={addForbiddenWord}
                disabled={!forbiddenInput.trim()}
                className="btn-secondary flex items-center gap-1"
              >
                <Plus size={13} />
                Добавить
              </button>
            </div>
          </section>

          {/* Любимые паттерны */}
          <section className="card space-y-4">
            <h2 className="text-sm font-semibold text-ink">Структурные паттерны</h2>
            <p className="text-xs text-ink-secondary -mt-2">
              Предпочтительные способы подачи контента
            </p>

            <div className="flex flex-wrap gap-2 min-h-[32px]">
              {bv.preferred_patterns.map((pattern) => (
                <span
                  key={pattern}
                  className="flex items-center gap-1 text-xs bg-accent/10 text-accent border border-accent/20 px-2.5 py-1 rounded-full"
                >
                  {pattern}
                  <button onClick={() => removePattern(pattern)} className="hover:text-accent/70">
                    <X size={11} />
                  </button>
                </span>
              ))}
              {bv.preferred_patterns.length === 0 && (
                <p className="text-xs text-ink-secondary italic">Нет паттернов</p>
              )}
            </div>

            {/* Suggestions */}
            <div>
              <p className="text-xs text-ink-secondary mb-2">Быстро добавить:</p>
              <div className="flex flex-wrap gap-1.5">
                {PATTERN_SUGGESTIONS.filter((s) => !bv.preferred_patterns.includes(s)).map((s) => (
                  <button
                    key={s}
                    onClick={() => addPattern(s)}
                    className="text-xs border border-dashed border-border text-ink-secondary px-2.5 py-1 rounded-full hover:border-accent hover:text-accent transition-all"
                  >
                    + {s}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-2">
              <input
                value={patternInput}
                onChange={(e) => setPatternInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && patternInput.trim() && addPattern(patternInput.trim())}
                placeholder="Свой паттерн..."
                className="input-base flex-1 text-sm"
              />
              <button
                onClick={() => patternInput.trim() && addPattern(patternInput.trim())}
                disabled={!patternInput.trim()}
                className="btn-secondary flex items-center gap-1"
              >
                <Plus size={13} />
                Добавить
              </button>
            </div>
          </section>

          {/* Примеры постов */}
          <section className="card space-y-4">
            <h2 className="text-sm font-semibold text-ink">Примеры постов</h2>
            <p className="text-xs text-ink-secondary -mt-2">
              Твои лучшие посты — AI использует их как эталон стиля
            </p>

            <div className="space-y-3">
              {bv.example_posts.map((ex, i) => (
                <div key={i} className="relative bg-canvas rounded-nav p-3 pr-8">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className="text-[10px] font-medium text-accent bg-accent/10 px-2 py-0.5 rounded-full">
                      {PLATFORM_LABELS[ex.platform as Platform] ?? ex.platform}
                    </span>
                  </div>
                  <p className="text-xs text-ink leading-relaxed line-clamp-4">{ex.text}</p>
                  <button
                    onClick={() => deleteExampleMutation.mutate(i)}
                    className="absolute top-2.5 right-2.5 btn-ghost p-1 text-ink-secondary hover:text-red-500"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>

            {/* Добавить пример */}
            <div className="border border-dashed border-border rounded-nav p-4 space-y-3">
              <div className="flex gap-1.5 flex-wrap">
                {PLATFORM_LIST.map((p) => (
                  <button
                    key={p}
                    onClick={() => setExamplePlatform(p)}
                    className={cn(
                      "text-xs px-2.5 py-1 rounded-full border transition-all",
                      examplePlatform === p
                        ? "border-accent bg-accent/10 text-accent"
                        : "border-border text-ink-secondary hover:text-ink"
                    )}
                  >
                    {PLATFORM_LABELS[p]}
                  </button>
                ))}
              </div>
              <textarea
                value={exampleText}
                onChange={(e) => setExampleText(e.target.value)}
                placeholder="Вставь пример хорошего поста..."
                rows={4}
                className="input-base w-full resize-none text-sm leading-relaxed"
              />
              <button
                onClick={() => addExampleMutation.mutate({ text: exampleText, platform: examplePlatform })}
                disabled={!exampleText.trim() || addExampleMutation.isPending}
                className="btn-secondary flex items-center gap-1.5 text-sm"
              >
                {addExampleMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                Добавить пример
              </button>
            </div>
          </section>

          {/* System prompt */}
          <section className="card space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-ink">System Prompt</h2>
                {promptAge !== null ? (
                  <p className="text-xs text-ink-secondary mt-0.5">
                    Обновлён {promptAge}ч назад · {bv.system_prompt_cache?.length ?? 0} символов
                  </p>
                ) : (
                  <p className="text-xs text-amber-600 mt-0.5 flex items-center gap-1">
                    <Info size={11} />
                    Не сгенерирован — AI использует базовые настройки
                  </p>
                )}
              </div>
              <button
                onClick={() => regenerateMutation.mutate()}
                disabled={regenerateMutation.isPending}
                className="btn-secondary flex items-center gap-1.5 text-sm"
              >
                {regenerateMutation.isPending ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <RefreshCw size={13} />
                )}
                Пересобрать
              </button>
            </div>

            {bv.system_prompt_cache && (
              <div>
                <button
                  onClick={() => setShowPrompt((v) => !v)}
                  className="flex items-center gap-1.5 text-xs text-ink-secondary hover:text-ink"
                >
                  {showPrompt ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  {showPrompt ? "Скрыть" : "Показать промпт"}
                </button>
                {showPrompt && (
                  <pre className="mt-2 text-[11px] text-ink leading-relaxed bg-canvas rounded-nav p-3 overflow-x-auto max-h-60 overflow-y-auto whitespace-pre-wrap font-mono">
                    {bv.system_prompt_cache}
                  </pre>
                )}
              </div>
            )}
          </section>

        </div>
      </div>
    </div>
  )
}
