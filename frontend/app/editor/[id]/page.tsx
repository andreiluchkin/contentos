"use client"

import { useState, useEffect, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, Save, Sparkles, Eye, Loader2, Send } from "lucide-react"
import { usePost, useUpdatePost, useScorePost, useImprovePost, useGeneratePost, useAccounts } from "@/lib/queries"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { PlatformIcon } from "@/components/shared/PlatformIcon"
import { ContentScorePanel } from "@/components/editor/ContentScorePanel"
import { PlatformPreview } from "@/components/editor/PlatformPreview"
import { CONTENT_TYPE_LABELS, cn } from "@/lib/utils"
import type { ContentScore, SocialAccount } from "@/lib/types"

type RightPanel = "preview" | "score"

export default function EditorPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()

  const { data: post, isLoading } = usePost(id)
  const { data: accounts = [] } = useAccounts()
  const updatePost = useUpdatePost()
  const scorePost = useScorePost()
  const improvePost = useImprovePost()
  const generatePost = useGeneratePost()

  const [body, setBody] = useState("")
  const [rightPanel, setRightPanel] = useState<RightPanel>("preview")
  const [isDirty, setIsDirty] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)

  useEffect(() => {
    if (post) {
      setBody(post.body)
      setIsDirty(false)
    }
  }, [post])

  const handleBodyChange = useCallback((val: string) => {
    setBody(val)
    setIsDirty(true)
  }, [])

  async function handleSave() {
    if (!isDirty) return
    setIsSaving(true)
    try {
      await updatePost.mutateAsync({ id, data: { body } })
      setIsDirty(false)
    } finally {
      setIsSaving(false)
    }
  }

  async function handleGenerate() {
    if (!post) return
    setIsGenerating(true)
    try {
      await generatePost.mutateAsync(post.id)
    } finally {
      setIsGenerating(false)
    }
  }

  async function handleScore(): Promise<ContentScore> {
    // Сохраняем если есть несохранённые изменения
    if (isDirty) await handleSave()
    return scorePost.mutateAsync(id)
  }

  async function handleImprove(issues: string[]) {
    if (isDirty) await handleSave()
    await improvePost.mutateAsync({ postId: id, issues })
  }

  async function handleSendToReview() {
    if (isDirty) await handleSave()
    await updatePost.mutateAsync({ id, data: { status: "review" } })
  }

  const account = (accounts as SocialAccount[]).find(
    (a: SocialAccount) => a.id === post?.account_id
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={24} className="animate-spin text-ink-secondary" />
      </div>
    )
  }

  if (!post) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-ink-secondary">
        <p className="text-sm">Пост не найден</p>
        <button onClick={() => router.push("/backlog")} className="btn-ghost mt-3 text-sm">
          ← Backlog
        </button>
      </div>
    )
  }

  const charCount = body.length

  return (
    <div className="flex flex-col h-screen">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-3 bg-card border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push("/backlog")} className="btn-ghost p-2">
            <ArrowLeft size={16} />
          </button>
          <div className="flex items-center gap-2">
            <PlatformIcon platform={post.platform} size="sm" />
            <span className="text-sm font-medium text-ink hidden sm:block">
              {CONTENT_TYPE_LABELS[post.content_type as keyof typeof CONTENT_TYPE_LABELS] ?? post.content_type}
            </span>
            <StatusBadge status={post.status} />
          </div>
        </div>

        <div className="flex items-center gap-2">
          {post.status === "draft" || post.status === "idea_approved" ? (
            <button
              onClick={handleGenerate}
              disabled={isGenerating}
              className="btn-secondary flex items-center gap-1.5 text-sm"
            >
              {isGenerating ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <Sparkles size={13} />
              )}
              <span className="hidden sm:inline">Сгенерировать</span>
            </button>
          ) : null}

          <button
            onClick={handleSave}
            disabled={!isDirty || isSaving}
            className="btn-secondary flex items-center gap-1.5 text-sm"
          >
            {isSaving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
            <span className="hidden sm:inline">{isDirty ? "Сохранить" : "Сохранено"}</span>
          </button>

          {post.status !== "published" && (
            <button
              onClick={handleSendToReview}
              className="btn-primary flex items-center gap-1.5 text-sm"
            >
              <Send size={13} />
              <span className="hidden sm:inline">На проверку</span>
            </button>
          )}
        </div>
      </div>

      {/* Split-screen body */}
      <div className="flex flex-1 overflow-hidden">
        {/* LEFT — Editor */}
        <div className="flex flex-col flex-1 min-w-0 border-r border-border">
          <textarea
            value={body}
            onChange={(e) => handleBodyChange(e.target.value)}
            placeholder="Начни писать или нажми «Сгенерировать»..."
            className="flex-1 resize-none p-5 text-sm text-ink leading-relaxed bg-white outline-none font-ui placeholder:text-ink-secondary"
          />
          {/* Footer */}
          <div className="flex items-center justify-between px-5 py-2.5 border-t border-border bg-white shrink-0">
            <span className={cn("text-xs tabular-nums", charCount > 4096 ? "text-red-500" : "text-ink-secondary")}>
              {charCount.toLocaleString()} символов
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setRightPanel("preview")}
                className={cn("btn-ghost text-xs py-1.5 px-3", rightPanel === "preview" && "bg-black/5 text-ink")}
              >
                <Eye size={12} className="mr-1.5 inline" />
                Превью
              </button>
              <button
                onClick={() => setRightPanel("score")}
                className={cn("btn-ghost text-xs py-1.5 px-3", rightPanel === "score" && "bg-black/5 text-ink")}
              >
                <Sparkles size={12} className="mr-1.5 inline" />
                Score
                {post.content_score !== null && (
                  <span className={cn("ml-1.5 font-semibold", post.content_score >= 80 ? "text-green-600" : post.content_score >= 60 ? "text-amber-600" : "text-red-500")}>
                    {post.content_score}
                  </span>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT — Preview or Score */}
        <div className="w-[420px] shrink-0 hidden md:flex flex-col bg-canvas overflow-hidden">
          {rightPanel === "preview" ? (
            <PlatformPreview
              body={body}
              platform={post.platform}
              handle={account?.handle}
            />
          ) : (
            <ContentScorePanel
              post={{ ...post, body }}
              onScore={handleScore}
              onImprove={handleImprove}
            />
          )}
        </div>
      </div>
    </div>
  )
}
