"use client"

import { useState, useEffect, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, Save, Eye, Loader2, Send, Layers } from "lucide-react"
import { usePost, useUpdatePost, useScorePost, useImprovePost, useAccounts } from "@/lib/queries"
import { aiApi } from "@/lib/api"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { PlatformIcon } from "@/components/shared/PlatformIcon"
import { ContentScorePanel } from "@/components/editor/ContentScorePanel"
import { PlatformPreview } from "@/components/editor/PlatformPreview"
import { PlatformTabs } from "@/components/editor/PlatformTabs"
import { CONTENT_TYPE_LABELS, PLATFORM_LABELS, cn } from "@/lib/utils"
import type { ContentScore, SocialAccount, Platform } from "@/lib/types"

type RightPanel = "preview" | "score"

// Достаём дополнительные платформы из platform_meta.platform_bodies
function getExtraPlatforms(post: ReturnType<typeof usePost>["data"]): Platform[] {
  if (!post) return []
  const bodies = post.platform_meta?.platform_bodies as Record<string, string> | undefined
  if (!bodies) return []
  return Object.keys(bodies).filter((p) => p !== post.platform) as Platform[]
}

function getAllPlatforms(post: ReturnType<typeof usePost>["data"]): Platform[] {
  if (!post) return []
  const primary = post.platform as Platform
  const extra = getExtraPlatforms(post)
  return [primary, ...extra.filter((p) => p !== primary)]
}

function getPlatformBodies(post: ReturnType<typeof usePost>["data"]): Record<Platform, string> {
  if (!post) return {} as Record<Platform, string>
  const primary = post.platform as Platform
  const stored = (post.platform_meta?.platform_bodies as Record<string, string>) ?? {}
  return { [primary]: post.body, ...stored } as Record<Platform, string>
}

function getPlatformHashtags(post: ReturnType<typeof usePost>["data"]): Record<Platform, string[]> {
  if (!post) return {} as Record<Platform, string[]>
  const primary = post.platform as Platform
  const stored = (post.platform_meta?.platform_hashtags as Record<string, string[]>) ?? {}
  return { [primary]: post.hashtags ?? [], ...stored } as Record<Platform, string[]>
}

export default function EditorPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()

  const { data: post, isLoading } = usePost(id)
  const { data: accounts = [] } = useAccounts()
  const updatePost = useUpdatePost()
  const scorePost = useScorePost()
  const improvePost = useImprovePost()

  // Мультиплатформный стейт
  const [platformBodies, setPlatformBodies] = useState<Record<Platform, string>>({} as Record<Platform, string>)
  const [platformHashtags, setPlatformHashtags] = useState<Record<Platform, string[]>>({} as Record<Platform, string[]>)
  const [activePreviewPlatform, setActivePreviewPlatform] = useState<Platform | null>(null)

  // Режим: одна платформа или мультиплатформа
  const [multiMode, setMultiMode] = useState(false)

  const [rightPanel, setRightPanel] = useState<RightPanel>("preview")
  const [isDirty, setIsDirty] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [generatingPlatform, setGeneratingPlatform] = useState<Platform | null>(null)

  useEffect(() => {
    if (post) {
      setPlatformBodies(getPlatformBodies(post))
      setPlatformHashtags(getPlatformHashtags(post))
      setActivePreviewPlatform(post.platform as Platform)
      const extra = getExtraPlatforms(post)
      if (extra.length > 0) setMultiMode(true)
      setIsDirty(false)
    }
  }, [post])

  const handleTabChange = useCallback((platform: Platform, body: string, hashtags: string[]) => {
    setPlatformBodies((prev) => ({ ...prev, [platform]: body }))
    setPlatformHashtags((prev) => ({ ...prev, [platform]: hashtags }))
    setActivePreviewPlatform(platform)
    setIsDirty(true)
  }, [])

  const handleSingleBodyChange = useCallback((val: string) => {
    if (!post) return
    setPlatformBodies((prev) => ({ ...prev, [post.platform as Platform]: val }))
    setIsDirty(true)
  }, [post])

  async function handleSave() {
    if (!post || !isDirty) return
    setIsSaving(true)
    try {
      const primary = post.platform as Platform
      const primaryBody = platformBodies[primary] ?? ""
      const primaryHashtags = platformHashtags[primary] ?? []

      // Сохраняем дополнительные платформы в platform_meta
      const allPlatforms = getAllPlatforms(post)
      const platformBodiesForMeta: Record<string, string> = {}
      const platformHashtagsForMeta: Record<string, string[]> = {}
      for (const p of allPlatforms) {
        if (p !== primary) {
          platformBodiesForMeta[p] = platformBodies[p] ?? ""
          platformHashtagsForMeta[p] = platformHashtags[p] ?? []
        }
      }

      const currentMeta = post.platform_meta ?? {}
      await updatePost.mutateAsync({
        id,
        data: {
          body: primaryBody,
          hashtags: primaryHashtags,
          platform_meta: {
            ...currentMeta,
            platform_bodies: platformBodiesForMeta,
            platform_hashtags: platformHashtagsForMeta,
          },
        },
      })
      setIsDirty(false)
    } finally {
      setIsSaving(false)
    }
  }

  async function handleGenerate(platform: Platform) {
    if (!post) return
    setGeneratingPlatform(platform)
    try {
      // Используем прямую генерацию для платформы
      const result = await aiApi.generateDirect({
        topic: post.title ?? post.body?.slice(0, 100),
        platform,
        content_type: post.content_type,
      })
      const body = result.body ?? result.text ?? ""
      const hashtags = result.hashtags ?? []
      setPlatformBodies((prev) => ({ ...prev, [platform]: body }))
      setPlatformHashtags((prev) => ({ ...prev, [platform]: hashtags }))
      setIsDirty(true)
    } catch (e) {
      console.error("Generate failed:", e)
    } finally {
      setGeneratingPlatform(null)
    }
  }

  async function handleScore(): Promise<ContentScore> {
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

  const primaryPlatform = post.platform as Platform
  const allPlatforms = getAllPlatforms(post)
  const primaryBody = platformBodies[primaryPlatform] ?? ""
  const previewPlatform = activePreviewPlatform ?? primaryPlatform

  // Список платформ для добавления
  const availablePlatformsToAdd: Platform[] = (
    ["telegram", "instagram", "linkedin", "x", "tiktok", "youtube"] as Platform[]
  ).filter((p) => !allPlatforms.includes(p))

  return (
    <div className="flex flex-col h-screen">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-3 bg-card border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push("/backlog")} className="btn-ghost p-2">
            <ArrowLeft size={16} />
          </button>
          <div className="flex items-center gap-2">
            <PlatformIcon platform={primaryPlatform} size="sm" />
            <span className="text-sm font-medium text-ink hidden sm:block">
              {CONTENT_TYPE_LABELS[post.content_type as keyof typeof CONTENT_TYPE_LABELS] ?? post.content_type}
            </span>
            <StatusBadge status={post.status} />
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Переключить мультиплатформу */}
          <button
            onClick={() => setMultiMode((v) => !v)}
            className={cn(
              "btn-ghost flex items-center gap-1.5 text-xs py-1.5 px-2.5",
              multiMode && "bg-accent/10 text-accent"
            )}
            title="Мультиплатформный режим"
          >
            <Layers size={13} />
            <span className="hidden sm:inline">Мульти</span>
          </button>

          {/* Добавить платформу */}
          {multiMode && availablePlatformsToAdd.length > 0 && (
            <div className="relative group">
              <button className="btn-ghost text-xs py-1.5 px-2.5">
                + Платформа
              </button>
              <div className="absolute right-0 top-full mt-1 bg-white border border-border rounded-card shadow-sm z-20 min-w-[140px] py-1 hidden group-hover:block">
                {availablePlatformsToAdd.map((p) => (
                  <button
                    key={p}
                    onClick={() => {
                      setPlatformBodies((prev) => ({ ...prev, [p]: "" }))
                      setPlatformHashtags((prev) => ({ ...prev, [p]: [] }))
                      setIsDirty(true)
                    }}
                    className="flex items-center gap-2 w-full text-left px-3 py-1.5 text-xs text-ink hover:bg-canvas"
                  >
                    <PlatformIcon platform={p} size="sm" />
                    {PLATFORM_LABELS[p]}
                  </button>
                ))}
              </div>
            </div>
          )}

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
        {multiMode ? (
          <PlatformTabs
            platforms={allPlatforms}
            primaryPlatform={primaryPlatform}
            initialBodies={platformBodies}
            initialHashtags={platformHashtags}
            onTabChange={handleTabChange}
            onGenerate={handleGenerate}
            generatingPlatform={generatingPlatform}
            readOnly={post.status === "published"}
          />
        ) : (
          <div className="flex flex-col flex-1 min-w-0 border-r border-border">
            <textarea
              value={primaryBody}
              onChange={(e) => handleSingleBodyChange(e.target.value)}
              placeholder="Начни писать или нажми «Сгенерировать»..."
              disabled={post.status === "published"}
              className="flex-1 resize-none p-5 text-sm text-ink leading-relaxed bg-white outline-none font-ui placeholder:text-ink-secondary disabled:opacity-60"
            />
            <div className="flex items-center justify-between px-5 py-2.5 border-t border-border bg-white shrink-0">
              <span className={cn(
                "text-xs tabular-nums",
                primaryBody.length > 4096 ? "text-red-500" : "text-ink-secondary"
              )}>
                {primaryBody.length.toLocaleString()} символов
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
                  Score
                  {post.content_score !== null && (
                    <span className={cn(
                      "ml-1.5 font-semibold",
                      post.content_score >= 80 ? "text-green-600" :
                      post.content_score >= 60 ? "text-amber-600" : "text-red-500"
                    )}>
                      {post.content_score}
                    </span>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* RIGHT — Preview or Score (только в одиночном режиме) */}
        {!multiMode && (
          <div className="w-[420px] shrink-0 hidden md:flex flex-col bg-canvas overflow-hidden">
            {rightPanel === "preview" ? (
              <PlatformPreview
                body={primaryBody}
                platform={previewPlatform}
                handle={account?.handle}
              />
            ) : (
              <ContentScorePanel
                post={{ ...post, body: primaryBody }}
                onScore={handleScore}
                onImprove={handleImprove}
              />
            )}
          </div>
        )}

        {/* В мультирежиме превью справа для активной вкладки */}
        {multiMode && (
          <div className="w-[380px] shrink-0 hidden lg:flex flex-col bg-canvas overflow-hidden border-l border-border">
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border bg-white shrink-0">
              <Eye size={13} className="text-ink-secondary" />
              <span className="text-xs font-medium text-ink-secondary">
                Превью — {PLATFORM_LABELS[previewPlatform]}
              </span>
            </div>
            <PlatformPreview
              body={platformBodies[previewPlatform] ?? ""}
              platform={previewPlatform}
              handle={account?.handle}
            />
          </div>
        )}
      </div>
    </div>
  )
}
