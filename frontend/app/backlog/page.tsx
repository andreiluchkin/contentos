"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Plus, ChevronDown } from "lucide-react"
import { usePosts, useUpdatePostStatus, usePillars, useAccounts } from "@/lib/queries"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { PlatformIcon } from "@/components/shared/PlatformIcon"
import { ScoreBadge } from "@/components/shared/ScoreBadge"
import { formatDate, CONTENT_TYPE_LABELS, STATUS_LABELS } from "@/lib/utils"
import type { Post, PipelineStatus, ContentPillar, SocialAccount } from "@/lib/types"

const STATUSES: PipelineStatus[] = ["draft", "review", "ready", "scheduled", "error"]

export default function BacklogPage() {
  const router = useRouter()
  const [statusFilter, setStatusFilter] = useState<string>("draft,review,ready")
  const [platformFilter, setPlatformFilter] = useState<string | undefined>()

  const { data: posts = [], isLoading } = usePosts({
    status: statusFilter,
    platform: platformFilter,
  })
  const { data: pillars = [] } = usePillars()
  const { data: accounts = [] } = useAccounts()
  const updateStatus = useUpdatePostStatus()

  const pillarMap = Object.fromEntries(
    (pillars as ContentPillar[]).map((p: ContentPillar) => [p.id, p])
  )

  const statusCounts = (posts as Post[]).reduce(
    (acc: Record<string, number>, p: Post) => {
      acc[p.status] = (acc[p.status] ?? 0) + 1
      return acc
    },
    {}
  )

  return (
    <div className="px-4 py-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-ink">Backlog</h1>
          <p className="text-sm text-ink-secondary mt-0.5">
            {isLoading ? "Загрузка..." : `${(posts as Post[]).length} постов`}
          </p>
        </div>
        <button onClick={() => router.push("/editor")} className="btn-primary flex items-center gap-2">
          <Plus size={15} />
          Новый пост
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {/* Status filter chips */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            onClick={() => setStatusFilter("draft,review,ready,scheduled,error")}
            className={`platform-chip ${statusFilter.includes(",") && statusFilter.split(",").length > 3 ? "bg-accent-light border-accent text-accent" : ""}`}
          >
            Все
          </button>
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`platform-chip ${statusFilter === s ? "bg-accent-light border-accent text-accent" : ""}`}
            >
              {STATUS_LABELS[s]}
              {statusCounts[s] ? (
                <span className="ml-1 text-xs opacity-60">{statusCounts[s]}</span>
              ) : null}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-10 bg-gray-50 rounded animate-pulse" />
            ))}
          </div>
        ) : (posts as Post[]).length === 0 ? (
          <div className="text-center py-16 text-ink-secondary">
            <div className="text-4xl mb-3">📋</div>
            <p className="text-sm font-medium">Постов нет</p>
            <p className="text-xs mt-1">Одобри идеи в Inbox или создай пост вручную</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left text-xs font-medium text-ink-secondary px-4 py-3">Пост</th>
                <th className="text-left text-xs font-medium text-ink-secondary px-3 py-3 hidden sm:table-cell">Тип</th>
                <th className="text-left text-xs font-medium text-ink-secondary px-3 py-3">Статус</th>
                <th className="text-left text-xs font-medium text-ink-secondary px-3 py-3 hidden md:table-cell">Дата</th>
                <th className="text-left text-xs font-medium text-ink-secondary px-3 py-3">Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(posts as Post[]).map((post: Post) => {
                const pillar = pillarMap[post.pillar_id ?? ""]
                return (
                  <tr
                    key={post.id}
                    onClick={() => router.push(`/editor/${post.id}`)}
                    className="hover:bg-canvas cursor-pointer transition-colors group"
                  >
                    {/* Превью поста */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <PlatformIcon platform={post.platform} size="sm" />
                        <div className="min-w-0">
                          <p className="text-sm text-ink truncate max-w-[280px] group-hover:text-accent transition-colors">
                            {post.body.slice(0, 80) || "Пустой черновик"}
                          </p>
                          {pillar && (
                            <span
                              className="text-xs"
                              style={{ color: pillar.color }}
                            >
                              {pillar.name}
                            </span>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Тип */}
                    <td className="px-3 py-3 hidden sm:table-cell">
                      <span className="text-xs text-ink-secondary">
                        {CONTENT_TYPE_LABELS[post.content_type] ?? post.content_type}
                      </span>
                    </td>

                    {/* Статус */}
                    <td className="px-3 py-3">
                      <StatusBadge status={post.status} />
                    </td>

                    {/* Дата */}
                    <td className="px-3 py-3 hidden md:table-cell">
                      <span className="text-xs text-ink-secondary">
                        {post.scheduled_at
                          ? formatDate(post.scheduled_at)
                          : formatDate(post.created_at)}
                      </span>
                    </td>

                    {/* Score */}
                    <td className="px-3 py-3">
                      <ScoreBadge score={post.content_score} size="sm" />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
