"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import {
  CheckCircle2,
  XCircle,
  PenLine,
  Send,
  Loader2,
  Clock,
  ClipboardList,
} from "lucide-react"
import { publishingApi } from "@/lib/api"
import { PlatformIcon } from "@/components/shared/PlatformIcon"
import { ScoreBadge } from "@/components/shared/ScoreBadge"
import { CONTENT_TYPE_LABELS, PLATFORM_LABELS, cn } from "@/lib/utils"
import type { Platform, ContentType } from "@/lib/types"

interface ReviewPost {
  id: string
  platform: string
  content_type: string
  body: string
  body_preview: string
  content_score: number | null
  created_at: string | null
  account_handle: string | null
  account_display: string | null
  hashtags: string[]
  pillar_id: string | null
}

function formatDate(iso: string | null): string {
  if (!iso) return ""
  const d = new Date(iso)
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
}

export default function ReviewPage() {
  const router = useRouter()
  const qc = useQueryClient()
  const [rejectingId, setRejectingId] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState("")
  const [publishingId, setPublishingId] = useState<string | null>(null)

  const { data: posts = [], isLoading } = useQuery<ReviewPost[]>({
    queryKey: ["review-queue"],
    queryFn: publishingApi.reviewQueue,
    refetchInterval: 30_000,
  })

  const approveMutation = useMutation({
    mutationFn: (id: string) => publishingApi.approve(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["review-queue"] }),
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      publishingApi.reject(id, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["review-queue"] })
      setRejectingId(null)
      setRejectReason("")
    },
  })

  const publishNowMutation = useMutation({
    mutationFn: (id: string) => publishingApi.publishNow(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["review-queue"] })
      setPublishingId(null)
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={24} className="animate-spin text-ink-secondary" />
      </div>
    )
  }

  return (
    <div className="overflow-y-auto h-full px-4 py-6">
      <div className="max-w-2xl mx-auto space-y-6">

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink mb-1">Очередь проверки</h1>
            <p className="text-sm text-ink-secondary">
              {posts.length > 0
                ? `${posts.length} ${posts.length === 1 ? "пост" : "постов"} ждёт проверки`
                : "Нет постов на проверке"}
            </p>
          </div>
        </div>

        {posts.length === 0 ? (
          <div className="card text-center py-16 text-ink-secondary">
            <ClipboardList size={36} className="mx-auto mb-3 opacity-25" />
            <p className="text-sm font-medium">Всё чисто</p>
            <p className="text-xs mt-1">Посты на проверке появятся здесь</p>
          </div>
        ) : (
          <div className="space-y-3">
            {posts.map((post) => (
              <div key={post.id} className="card space-y-3">
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <PlatformIcon platform={post.platform as Platform} size="sm" />
                    <span className="text-xs font-medium text-ink">
                      {post.account_display ?? post.account_handle ?? post.platform}
                    </span>
                    <span className="text-xs text-ink-secondary">
                      {CONTENT_TYPE_LABELS[post.content_type as ContentType] ?? post.content_type}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {post.content_score !== null && <ScoreBadge score={post.content_score} />}
                    {post.created_at && (
                      <span className="flex items-center gap-1 text-[10px] text-ink-secondary">
                        <Clock size={10} />
                        {formatDate(post.created_at)}
                      </span>
                    )}
                  </div>
                </div>

                {/* Body */}
                <p className="text-sm text-ink leading-relaxed whitespace-pre-wrap line-clamp-6">
                  {post.body_preview}
                  {post.body.length > 200 && "…"}
                </p>

                {/* Hashtags */}
                {post.hashtags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {post.hashtags.slice(0, 8).map((tag) => (
                      <span key={tag} className="text-[10px] text-accent bg-accent/8 rounded-full px-2 py-0.5">
                        #{tag}
                      </span>
                    ))}
                    {post.hashtags.length > 8 && (
                      <span className="text-[10px] text-ink-secondary">+{post.hashtags.length - 8}</span>
                    )}
                  </div>
                )}

                {/* Reject reason input */}
                {rejectingId === post.id && (
                  <div className="space-y-2">
                    <input
                      autoFocus
                      type="text"
                      placeholder="Причина (необязательно)"
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") rejectMutation.mutate({ id: post.id, reason: rejectReason })
                        if (e.key === "Escape") { setRejectingId(null); setRejectReason("") }
                      }}
                      className="w-full px-3 py-2 text-sm border border-border rounded-nav bg-canvas text-ink placeholder:text-ink-secondary focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => rejectMutation.mutate({ id: post.id, reason: rejectReason })}
                        disabled={rejectMutation.isPending}
                        className="btn-primary text-xs py-1.5 px-3"
                      >
                        {rejectMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : "Отправить в Draft"}
                      </button>
                      <button
                        onClick={() => { setRejectingId(null); setRejectReason("") }}
                        className="btn-ghost text-xs py-1.5 px-3"
                      >
                        Отмена
                      </button>
                    </div>
                  </div>
                )}

                {/* Actions */}
                {rejectingId !== post.id && (
                  <div className="flex items-center gap-2 pt-1">
                    <button
                      onClick={() => approveMutation.mutate(post.id)}
                      disabled={approveMutation.isPending}
                      className="btn-primary flex items-center gap-1.5 text-xs py-1.5 px-3"
                    >
                      {approveMutation.isPending
                        ? <Loader2 size={12} className="animate-spin" />
                        : <CheckCircle2 size={12} />}
                      Одобрить
                    </button>

                    <button
                      onClick={() => {
                        publishNowMutation.mutate(post.id)
                        setPublishingId(post.id)
                      }}
                      disabled={publishNowMutation.isPending && publishingId === post.id}
                      className="btn-secondary flex items-center gap-1.5 text-xs py-1.5 px-3"
                    >
                      {publishNowMutation.isPending && publishingId === post.id
                        ? <Loader2 size={12} className="animate-spin" />
                        : <Send size={12} />}
                      Опубликовать сейчас
                    </button>

                    <button
                      onClick={() => router.push(`/editor/${post.id}`)}
                      className="btn-ghost flex items-center gap-1.5 text-xs py-1.5 px-3"
                    >
                      <PenLine size={12} />
                      Редактировать
                    </button>

                    <button
                      onClick={() => { setRejectingId(post.id); setRejectReason("") }}
                      className="btn-ghost flex items-center gap-1.5 text-xs py-1.5 px-3 text-red-500 hover:bg-red-50"
                    >
                      <XCircle size={12} />
                      Отклонить
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
