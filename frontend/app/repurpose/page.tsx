"use client"

import { useState, useRef, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Mic, Link2, FileText, Upload, Loader2, CheckCircle2,
  AlertCircle, Sparkles, Plus, X, RefreshCw, ChevronDown, ChevronUp,
} from "lucide-react"
import { repurposeApi } from "@/lib/api"
import { useAccounts } from "@/lib/queries"
import { PLATFORM_LABELS, CONTENT_TYPE_LABELS, cn } from "@/lib/utils"
import type { Platform, ContentType, SocialAccount } from "@/lib/types"

type InputMode = "file" | "youtube" | "text"

interface ExtractedIdea {
  title: string
  context: string
  suggested_content_type: ContentType
}

interface RepurposeJob {
  id: string
  source_type: string
  source_youtube_url: string | null
  transcription: string | null
  extracted_ideas: ExtractedIdea[]
  status: string
  error: string | null
  created_at: string
  completed_at: string | null
}

const STATUS_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  pending:      { label: "В очереди",       color: "text-ink-secondary", icon: <Loader2 size={14} className="animate-spin" /> },
  transcribing: { label: "Транскрипция...", color: "text-blue-600",      icon: <Loader2 size={14} className="animate-spin" /> },
  transcribed:  { label: "Анализ...",       color: "text-purple-600",    icon: <Loader2 size={14} className="animate-spin" /> },
  extracting:   { label: "Идеи...",         color: "text-accent",        icon: <Loader2 size={14} className="animate-spin" /> },
  done:         { label: "Готово",          color: "text-green-600",     icon: <CheckCircle2 size={14} /> },
  error:        { label: "Ошибка",          color: "text-red-500",       icon: <AlertCircle size={14} /> },
}

const SOURCE_TYPE_LABELS: Record<string, string> = {
  voice_note:  "Голосовая заметка",
  video_file:  "Видео",
  youtube_url: "YouTube",
  text:        "Текст",
}

export default function RepurposePage() {
  const qc = useQueryClient()
  const { data: accounts = [] } = useAccounts()

  const [mode, setMode] = useState<InputMode>("file")
  const [youtubeUrl, setYoutubeUrl] = useState("")
  const [textInput, setTextInput] = useState("")
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [activeJob, setActiveJob] = useState<RepurposeJob | null>(null)
  const [selectedIdeas, setSelectedIdeas] = useState<Set<number>>(new Set())
  const [createPlatform, setCreatePlatform] = useState<Platform>("telegram")
  const [createContentType, setCreateContentType] = useState<ContentType>("story")
  const [createAccountId, setCreateAccountId] = useState("")
  const [expandedTranscript, setExpandedTranscript] = useState<string | null>(null)

  const { data: jobs = [], isLoading } = useQuery<RepurposeJob[]>({
    queryKey: ["repurpose-jobs"],
    queryFn: () => repurposeApi.list(),
    refetchInterval: (query) => {
      const data = query.state.data as RepurposeJob[] | undefined
      const hasActive = data?.some((j) => !["done", "error"].includes(j.status))
      return hasActive ? 3000 : false
    },
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => repurposeApi.uploadFile(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["repurpose-jobs"] }),
  })

  const youtubeMutation = useMutation({
    mutationFn: (url: string) => repurposeApi.youtube(url),
    onSuccess: () => { setYoutubeUrl(""); qc.invalidateQueries({ queryKey: ["repurpose-jobs"] }) },
  })

  const textMutation = useMutation({
    mutationFn: (text: string) => repurposeApi.text(text),
    onSuccess: () => { setTextInput(""); qc.invalidateQueries({ queryKey: ["repurpose-jobs"] }) },
  })

  const createPostsMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: string } & Record<string, unknown>) =>
      repurposeApi.createPosts(id, data),
    onSuccess: () => {
      setActiveJob(null)
      setSelectedIdeas(new Set())
    },
  })

  const deleteJobMutation = useMutation({
    mutationFn: (id: string) => repurposeApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["repurpose-jobs"] }),
  })

  const handleFile = useCallback((file: File) => {
    const isMedia = file.type.startsWith("audio/") || file.type.startsWith("video/")
    if (!isMedia) {
      alert("Поддерживаются только аудио и видео файлы")
      return
    }
    uploadMutation.mutate(file)
  }, [uploadMutation])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  function toggleIdea(idx: number) {
    setSelectedIdeas((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  function selectAll(job: RepurposeJob) {
    setSelectedIdeas(new Set(job.extracted_ideas.map((_, i) => i)))
  }

  async function handleCreatePosts() {
    if (!activeJob || !createAccountId) return
    await createPostsMutation.mutateAsync({
      id: activeJob.id,
      account_id: createAccountId,
      platform: createPlatform,
      content_type: createContentType,
      idea_indices: selectedIdeas.size > 0 ? Array.from(selectedIdeas) : null,
    })
  }

  const platformList = (["telegram", "instagram", "linkedin", "x", "tiktok", "youtube"] as Platform[])

  return (
    <div className="flex h-full overflow-hidden">
      {/* Main area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-2xl mx-auto">
          <h1 className="text-xl font-semibold text-ink mb-1">Repurpose</h1>
          <p className="text-sm text-ink-secondary mb-6">
            Голосовая заметка, видео или YouTube → идеи для постов
          </p>

          {/* Input panel */}
          <div className="card mb-6">
            {/* Mode tabs */}
            <div className="flex gap-0.5 mb-5 bg-canvas rounded-nav p-1">
              {(["file", "youtube", "text"] as InputMode[]).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium rounded-[10px] transition-all",
                    mode === m ? "bg-white shadow-sm text-ink" : "text-ink-secondary hover:text-ink"
                  )}
                >
                  {m === "file" && <Mic size={12} />}
                  {m === "youtube" && <Link2 size={12} />}
                  {m === "text" && <FileText size={12} />}
                  {m === "file" ? "Файл" : m === "youtube" ? "YouTube" : "Текст"}
                </button>
              ))}
            </div>

            {/* File drop zone */}
            {mode === "file" && (
              <div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "border-2 border-dashed rounded-card p-10 text-center cursor-pointer transition-all",
                  isDragging ? "border-accent bg-accent/5" : "border-border hover:border-border-strong hover:bg-canvas"
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="audio/*,video/*"
                  className="hidden"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
                />
                {uploadMutation.isPending ? (
                  <div className="flex flex-col items-center gap-2 text-ink-secondary">
                    <Loader2 size={24} className="animate-spin" />
                    <p className="text-sm">Загружаем файл...</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2 text-ink-secondary">
                    <Upload size={28} className={isDragging ? "text-accent" : ""} />
                    <p className="text-sm font-medium text-ink">Перетащи или кликни</p>
                    <p className="text-xs">MP3, M4A, WAV, OGG, MP4, MOV · до 200 МБ</p>
                  </div>
                )}
              </div>
            )}

            {/* YouTube input */}
            {mode === "youtube" && (
              <div className="space-y-3">
                <input
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  placeholder="https://youtube.com/watch?v=..."
                  className="input-base w-full"
                />
                <button
                  onClick={() => youtubeMutation.mutate(youtubeUrl)}
                  disabled={!youtubeUrl || youtubeMutation.isPending}
                  className="btn-primary w-full flex items-center justify-center gap-2"
                >
                  {youtubeMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                  Извлечь идеи
                </button>
              </div>
            )}

            {/* Text input */}
            {mode === "text" && (
              <div className="space-y-3">
                <textarea
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  placeholder="Вставь готовый текст — интервью, статью, транскрипт..."
                  rows={8}
                  className="input-base w-full resize-none text-sm leading-relaxed"
                />
                <div className="flex items-center justify-between">
                  <span className="text-xs text-ink-secondary">{textInput.length} символов</span>
                  <button
                    onClick={() => textMutation.mutate(textInput)}
                    disabled={textInput.length < 50 || textMutation.isPending}
                    className="btn-primary flex items-center gap-2"
                  >
                    {textMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                    Извлечь идеи
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Jobs list */}
          {isLoading ? (
            <div className="space-y-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-20 bg-white rounded-card animate-pulse" />
              ))}
            </div>
          ) : jobs.length === 0 ? (
            <div className="text-center py-12 text-ink-secondary">
              <Mic size={32} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">Пока нет заданий. Загрузи файл выше.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {jobs.map((job) => {
                const meta = STATUS_META[job.status] ?? STATUS_META.pending
                const isExpanded = expandedTranscript === job.id
                const isDone = job.status === "done"

                return (
                  <div key={job.id} className="card">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={cn("flex items-center gap-1 shrink-0", meta.color)}>
                          {meta.icon}
                          <span className="text-xs font-medium">{meta.label}</span>
                        </span>
                        <span className="text-xs text-ink-secondary">·</span>
                        <span className="text-xs text-ink-secondary truncate">
                          {SOURCE_TYPE_LABELS[job.source_type] ?? job.source_type}
                          {job.source_youtube_url && (
                            <span className="ml-1 opacity-60 truncate">
                              {job.source_youtube_url.slice(0, 40)}...
                            </span>
                          )}
                        </span>
                      </div>
                      <button
                        onClick={() => deleteJobMutation.mutate(job.id)}
                        className="btn-ghost p-1 shrink-0 text-ink-secondary hover:text-red-500"
                      >
                        <X size={13} />
                      </button>
                    </div>

                    {job.error && (
                      <p className="text-xs text-red-500 mt-2 bg-red-50 rounded-nav px-3 py-2">
                        {job.error}
                      </p>
                    )}

                    {job.transcription && (
                      <div className="mt-3">
                        <button
                          onClick={() => setExpandedTranscript(isExpanded ? null : job.id)}
                          className="flex items-center gap-1.5 text-xs text-ink-secondary hover:text-ink transition-colors"
                        >
                          {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                          Транскрипция ({job.transcription.length} символов)
                        </button>
                        {isExpanded && (
                          <p className="text-xs text-ink leading-relaxed mt-2 bg-canvas rounded-nav p-3 max-h-40 overflow-y-auto">
                            {job.transcription}
                          </p>
                        )}
                      </div>
                    )}

                    {isDone && job.extracted_ideas.length > 0 && (
                      <div className="mt-4">
                        <div className="flex items-center justify-between mb-2">
                          <p className="text-xs font-semibold text-ink">
                            Идеи ({job.extracted_ideas.length})
                          </p>
                          <button
                            onClick={() => { setActiveJob(job); selectAll(job) }}
                            className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5"
                          >
                            <Plus size={11} />
                            Создать посты
                          </button>
                        </div>
                        <div className="space-y-2">
                          {job.extracted_ideas.map((idea, i) => (
                            <div key={i} className="flex items-start gap-2.5 p-3 bg-canvas rounded-nav">
                              <span className="text-[10px] font-bold text-ink-secondary/60 mt-0.5 shrink-0">
                                #{i + 1}
                              </span>
                              <div className="min-w-0">
                                <p className="text-xs font-medium text-ink mb-0.5">{idea.title}</p>
                                <p className="text-[11px] text-ink-secondary leading-relaxed line-clamp-2">
                                  {idea.context}
                                </p>
                                <span className="inline-block mt-1.5 text-[10px] bg-accent/10 text-accent px-2 py-0.5 rounded-full">
                                  {CONTENT_TYPE_LABELS[idea.suggested_content_type] ?? idea.suggested_content_type}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {!isDone && job.status !== "error" && (
                      <div className="mt-3 h-1 bg-canvas rounded-full overflow-hidden">
                        <div className="h-full bg-accent rounded-full animate-pulse w-3/4" />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Right panel — создать посты */}
      {activeJob && (
        <div className="w-80 shrink-0 border-l border-border bg-card flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <p className="text-sm font-semibold text-ink">Создать посты</p>
            <button onClick={() => setActiveJob(null)} className="btn-ghost p-1.5">
              <X size={14} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Выбор идей */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-medium text-ink">Выбери идеи</p>
                <button
                  onClick={() => {
                    if (selectedIdeas.size === activeJob.extracted_ideas.length) {
                      setSelectedIdeas(new Set())
                    } else {
                      selectAll(activeJob)
                    }
                  }}
                  className="text-xs text-accent hover:underline"
                >
                  {selectedIdeas.size === activeJob.extracted_ideas.length ? "Снять всё" : "Выбрать все"}
                </button>
              </div>
              <div className="space-y-1.5">
                {activeJob.extracted_ideas.map((idea, i) => (
                  <button
                    key={i}
                    onClick={() => toggleIdea(i)}
                    className={cn(
                      "w-full text-left p-2.5 rounded-nav text-xs transition-all border",
                      selectedIdeas.has(i)
                        ? "border-accent bg-accent/5 text-ink"
                        : "border-transparent bg-canvas text-ink-secondary hover:text-ink hover:bg-border-strong/20"
                    )}
                  >
                    <span className="font-medium">{idea.title}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Платформа */}
            <div>
              <p className="text-xs font-medium text-ink mb-2">Платформа</p>
              <div className="grid grid-cols-3 gap-1">
                {platformList.map((p) => (
                  <button
                    key={p}
                    onClick={() => setCreatePlatform(p)}
                    className={cn(
                      "py-1.5 px-2 rounded-nav text-xs font-medium border transition-all",
                      createPlatform === p
                        ? "border-accent bg-accent/5 text-accent"
                        : "border-border text-ink-secondary hover:border-border-strong hover:text-ink"
                    )}
                  >
                    {PLATFORM_LABELS[p]}
                  </button>
                ))}
              </div>
            </div>

            {/* Аккаунт */}
            <div>
              <p className="text-xs font-medium text-ink mb-2">Аккаунт</p>
              <select
                value={createAccountId}
                onChange={(e) => setCreateAccountId(e.target.value)}
                className="input-base w-full text-sm"
              >
                <option value="">— выбрать —</option>
                {(accounts as SocialAccount[])
                  .filter((a) => a.platform === createPlatform)
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.display_name} (@{a.handle})
                    </option>
                  ))}
              </select>
            </div>

            {/* Тип контента */}
            <div>
              <p className="text-xs font-medium text-ink mb-2">Тип контента</p>
              <select
                value={createContentType}
                onChange={(e) => setCreateContentType(e.target.value as ContentType)}
                className="input-base w-full text-sm"
              >
                {Object.entries(CONTENT_TYPE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="p-4 border-t border-border">
            <button
              onClick={handleCreatePosts}
              disabled={!createAccountId || createPostsMutation.isPending}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {createPostsMutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <RefreshCw size={14} />
              )}
              Создать {selectedIdeas.size || activeJob.extracted_ideas.length} постов
            </button>
            <p className="text-[10px] text-ink-secondary text-center mt-2">
              AI сгенерирует тексты автоматически
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
