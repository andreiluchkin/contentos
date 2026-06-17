"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import { TrendingUp, TrendingDown, Minus, Eye, Heart, MessageCircle, Share2, BarChart2, Loader2 } from "lucide-react"
import { api } from "@/lib/api"
import { PlatformIcon } from "@/components/shared/PlatformIcon"
import { ScoreBadge } from "@/components/shared/ScoreBadge"
import { PLATFORM_LABELS, CONTENT_TYPE_LABELS, scoreColor, cn } from "@/lib/utils"
import type { Platform, ContentType } from "@/lib/types"

interface Overview {
  total_posts: number
  published_posts: number
  avg_content_score: number | null
  posts_this_week: number
  posts_last_week: number
  top_platform: string | null
  platform_counts: Record<string, number>
  status_counts: Record<string, number>
}

interface PostMetric {
  id: string
  platform: string
  content_type: string
  body_preview: string
  content_score: number | null
  views: number
  likes: number
  comments: number
  shares: number
  published_at: string | null
  pillar_id: string | null
}

interface PillarStat {
  pillar_id: string
  pillar_name: string
  pillar_color: string
  total_posts: number
  published_posts: number
  avg_score: number | null
}

interface DayStat {
  date: string
  count: number
  published: number
  avg_score: number | null
}

type SortBy = "score" | "views" | "likes" | "recent"

const PLATFORM_COLORS: Record<string, string> = {
  telegram: "#0088cc",
  instagram: "#e1306c",
  tiktok: "#000000",
  youtube: "#ff0000",
  linkedin: "#0077b5",
  x: "#1da1f2",
}

function Trend({ current, previous }: { current: number; previous: number }) {
  if (previous === 0) return null
  const diff = current - previous
  const pct = Math.round(Math.abs(diff / previous) * 100)
  if (diff > 0) return (
    <span className="flex items-center gap-0.5 text-green-600 text-xs font-medium">
      <TrendingUp size={11} /> +{pct}%
    </span>
  )
  if (diff < 0) return (
    <span className="flex items-center gap-0.5 text-red-500 text-xs font-medium">
      <TrendingDown size={11} /> -{pct}%
    </span>
  )
  return <span className="text-ink-secondary text-xs"><Minus size={11} /></span>
}

function MiniBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="h-1.5 bg-canvas rounded-full overflow-hidden flex-1">
      <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
    </div>
  )
}

// Спарклайн: SVG линия из массива чисел
function Sparkline({ data, color = "#7a40ed" }: { data: number[]; color?: string }) {
  if (data.length < 2) return null
  const max = Math.max(...data, 1)
  const w = 80
  const h = 24
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w
    const y = h - (v / max) * h
    return `${x},${y}`
  }).join(" ")

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}

export default function AnalyticsPage() {
  const router = useRouter()
  const [sortBy, setSortBy] = useState<SortBy>("score")
  const [platformFilter, setPlatformFilter] = useState<string | null>(null)

  const { data: overview, isLoading: overviewLoading } = useQuery<Overview>({
    queryKey: ["analytics-overview"],
    queryFn: () => api.get("/analytics/overview").then((r) => r.data),
  })

  const { data: posts = [], isLoading: postsLoading } = useQuery<PostMetric[]>({
    queryKey: ["analytics-posts", sortBy, platformFilter],
    queryFn: () => api.get("/analytics/posts", {
      params: { sort_by: sortBy, platform: platformFilter || undefined, limit: 20 },
    }).then((r) => r.data),
  })

  const { data: pillars = [] } = useQuery<PillarStat[]>({
    queryKey: ["analytics-pillars"],
    queryFn: () => api.get("/analytics/pillars").then((r) => r.data),
  })

  const { data: timeline = [] } = useQuery<DayStat[]>({
    queryKey: ["analytics-timeline"],
    queryFn: () => api.get("/analytics/timeline", { params: { days: 30 } }).then((r) => r.data),
  })

  const timelineCounts = timeline.map((d) => d.count)
  const maxDay = Math.max(...timelineCounts, 1)

  const platformList = Object.entries(overview?.platform_counts ?? {}).sort((a, b) => b[1] - a[1])
  const totalPlatforms = platformList.reduce((s, [, c]) => s + c, 0)

  if (overviewLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={24} className="animate-spin text-ink-secondary" />
      </div>
    )
  }

  return (
    <div className="overflow-y-auto h-full px-4 py-6">
      <div className="max-w-4xl mx-auto space-y-6">

        <div>
          <h1 className="text-xl font-semibold text-ink mb-1">Аналитика</h1>
          <p className="text-sm text-ink-secondary">Производительность контента</p>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            {
              label: "Всего постов",
              value: overview?.total_posts ?? 0,
              sub: `${overview?.published_posts ?? 0} опубликовано`,
            },
            {
              label: "За эту неделю",
              value: overview?.posts_this_week ?? 0,
              trend: { current: overview?.posts_this_week ?? 0, previous: overview?.posts_last_week ?? 0 },
            },
            {
              label: "Средний Score",
              value: overview?.avg_content_score ? `${overview.avg_content_score}` : "—",
              valueClass: overview?.avg_content_score ? scoreColor(overview.avg_content_score) : "",
            },
            {
              label: "Топ платформа",
              value: overview?.top_platform
                ? PLATFORM_LABELS[overview.top_platform as Platform] ?? overview.top_platform
                : "—",
            },
          ].map((card, i) => (
            <div key={i} className="card">
              <p className="text-xs text-ink-secondary mb-1">{card.label}</p>
              <p className={cn("text-2xl font-bold text-ink", card.valueClass)}>
                {card.value}
              </p>
              {card.sub && <p className="text-xs text-ink-secondary mt-0.5">{card.sub}</p>}
              {card.trend && (
                <div className="mt-1">
                  <Trend current={card.trend.current} previous={card.trend.previous} />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Timeline sparkline */}
        {timeline.length > 0 && (
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-ink">Активность за 30 дней</h2>
              <Sparkline data={timelineCounts} />
            </div>
            <div className="flex gap-px h-16 items-end">
              {timeline.map((day) => {
                const h = maxDay > 0 ? Math.round((day.count / maxDay) * 100) : 0
                return (
                  <div
                    key={day.date}
                    className="flex-1 group relative"
                    title={`${day.date}: ${day.count} постов`}
                  >
                    <div
                      className="w-full rounded-t-sm transition-colors bg-accent/30 hover:bg-accent/70"
                      style={{ height: `${Math.max(h, day.count > 0 ? 8 : 2)}%` }}
                    />
                    <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 hidden group-hover:block bg-ink text-white text-[9px] px-1.5 py-0.5 rounded whitespace-nowrap z-10">
                      {day.date.slice(5)}: {day.count}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-4">
          {/* Платформы */}
          <div className="card">
            <h2 className="text-sm font-semibold text-ink mb-4">По платформам</h2>
            <div className="space-y-3">
              {platformList.map(([platform, count]) => (
                <div key={platform} className="flex items-center gap-2">
                  <PlatformIcon platform={platform as Platform} size="sm" />
                  <span className="text-xs text-ink w-20 truncate">
                    {PLATFORM_LABELS[platform as Platform] ?? platform}
                  </span>
                  <MiniBar
                    value={count}
                    max={totalPlatforms}
                    color={PLATFORM_COLORS[platform] ?? "#7a40ed"}
                  />
                  <span className="text-xs tabular-nums text-ink-secondary w-6 text-right">{count}</span>
                </div>
              ))}
              {platformList.length === 0 && (
                <p className="text-xs text-ink-secondary text-center py-4">Нет данных</p>
              )}
            </div>
          </div>

          {/* Контент-столбы */}
          <div className="card">
            <h2 className="text-sm font-semibold text-ink mb-4">Контент-столбы</h2>
            <div className="space-y-3">
              {pillars.map((p) => (
                <div key={p.pillar_id} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{ backgroundColor: p.pillar_color }}
                      />
                      <span className="text-xs text-ink">{p.pillar_name}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-ink-secondary">
                      {p.avg_score && (
                        <span className={cn("font-medium", scoreColor(p.avg_score))}>
                          {p.avg_score}
                        </span>
                      )}
                      <span>{p.total_posts}</span>
                    </div>
                  </div>
                  <MiniBar
                    value={p.published_posts}
                    max={p.total_posts || 1}
                    color={p.pillar_color}
                  />
                </div>
              ))}
              {pillars.length === 0 && (
                <p className="text-xs text-ink-secondary text-center py-4">Нет столбов</p>
              )}
            </div>
          </div>
        </div>

        {/* Топ посты */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-ink">Посты</h2>
            <div className="flex items-center gap-2">
              {/* Фильтр платформы */}
              <div className="flex gap-1">
                <button
                  onClick={() => setPlatformFilter(null)}
                  className={cn(
                    "text-[11px] px-2 py-1 rounded-full border transition-all",
                    !platformFilter ? "border-accent bg-accent/10 text-accent" : "border-border text-ink-secondary hover:text-ink"
                  )}
                >
                  Все
                </button>
                {Object.keys(overview?.platform_counts ?? {}).map((p) => (
                  <button
                    key={p}
                    onClick={() => setPlatformFilter(platformFilter === p ? null : p)}
                    className={cn(
                      "text-[11px] px-2 py-1 rounded-full border transition-all",
                      platformFilter === p ? "border-accent bg-accent/10 text-accent" : "border-border text-ink-secondary hover:text-ink"
                    )}
                  >
                    {PLATFORM_LABELS[p as Platform] ?? p}
                  </button>
                ))}
              </div>

              {/* Сортировка */}
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortBy)}
                className="text-xs border border-border rounded-nav px-2 py-1 bg-white text-ink"
              >
                <option value="score">По Score</option>
                <option value="views">По просмотрам</option>
                <option value="likes">По лайкам</option>
                <option value="recent">Новые</option>
              </select>
            </div>
          </div>

          {postsLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => <div key={i} className="h-14 bg-canvas rounded-nav animate-pulse" />)}
            </div>
          ) : posts.length === 0 ? (
            <div className="text-center py-8 text-ink-secondary">
              <BarChart2 size={28} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">Нет опубликованных постов</p>
            </div>
          ) : (
            <div className="space-y-1.5">
              {posts.map((post) => (
                <button
                  key={post.id}
                  onClick={() => router.push(`/editor/${post.id}`)}
                  className="w-full text-left p-3 rounded-nav hover:bg-canvas transition-colors group"
                >
                  <div className="flex items-start gap-3">
                    <PlatformIcon platform={post.platform as Platform} size="sm" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-ink line-clamp-1 group-hover:text-accent transition-colors">
                        {post.body_preview || "—"}
                      </p>
                      <p className="text-[10px] text-ink-secondary mt-0.5">
                        {CONTENT_TYPE_LABELS[post.content_type as ContentType] ?? post.content_type}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0 text-[11px] text-ink-secondary">
                      {post.content_score !== null && (
                        <ScoreBadge score={post.content_score} />
                      )}
                      {(post.views > 0 || post.likes > 0) && (
                        <>
                          <span className="flex items-center gap-0.5">
                            <Eye size={10} /> {post.views.toLocaleString()}
                          </span>
                          <span className="flex items-center gap-0.5">
                            <Heart size={10} /> {post.likes.toLocaleString()}
                          </span>
                          {post.comments > 0 && (
                            <span className="flex items-center gap-0.5">
                              <MessageCircle size={10} /> {post.comments}
                            </span>
                          )}
                          {post.shares > 0 && (
                            <span className="flex items-center gap-0.5">
                              <Share2 size={10} /> {post.shares}
                            </span>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
