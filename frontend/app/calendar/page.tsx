"use client"

import { useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { ChevronLeft, ChevronRight, Plus, X } from "lucide-react"
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameMonth, isToday, getDay } from "date-fns"
import { ru } from "date-fns/locale"
import { calendarApi } from "@/lib/api"
import { PlatformIcon } from "@/components/shared/PlatformIcon"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { cn } from "@/lib/utils"
import type { Platform, PipelineStatus } from "@/lib/types"

interface DayData {
  total: number
  platforms: Platform[]
  pillars: { id: string; count: number }[]
  has_error: boolean
  is_gap: boolean
}

interface DayPost {
  id: string
  platform: Platform
  content_type: string
  body_preview: string
  status: PipelineStatus
  scheduled_at: string | null
  content_score: number | null
  pillar_id: string | null
}

const WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

const PLATFORM_DOT_COLORS: Record<Platform, string> = {
  telegram: "#0088cc",
  instagram: "#e1306c",
  tiktok: "#000000",
  youtube: "#ff0000",
  linkedin: "#0077b5",
  x: "#000000",
}

export default function CalendarPage() {
  const router = useRouter()
  const [current, setCurrent] = useState(new Date())
  const [selectedDay, setSelectedDay] = useState<string | null>(null)

  const year = current.getFullYear()
  const month = current.getMonth() + 1

  const { data: monthData, isLoading } = useQuery({
    queryKey: ["calendar-month", year, month],
    queryFn: () => calendarApi.month(year, month),
  })

  const { data: dayData } = useQuery({
    queryKey: ["calendar-day", selectedDay],
    queryFn: () => calendarApi.day(selectedDay!),
    enabled: !!selectedDay,
  })

  const days: Record<string, DayData> = monthData?.days ?? {}

  const firstDay = startOfMonth(current)
  const lastDay = endOfMonth(current)
  const allDays = eachDayOfInterval({ start: firstDay, end: lastDay })

  // Пустые ячейки перед первым числом (ISO: понедельник = 0)
  const startWeekday = (getDay(firstDay) + 6) % 7
  const leadingEmpties = Array(startWeekday).fill(null)

  const handleDayClick = useCallback((dateStr: string) => {
    setSelectedDay((prev) => (prev === dateStr ? null : dateStr))
  }, [])

  return (
    <div className="flex h-full overflow-hidden">
      {/* Основная сетка */}
      <div className="flex-1 px-4 py-6 min-w-0 overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold text-ink capitalize">
              {format(current, "LLLL yyyy", { locale: ru })}
            </h1>
            {monthData && (
              <p className="text-sm text-ink-secondary mt-0.5">
                {monthData.total_posts} постов · {monthData.gap_count} пустых дней
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setCurrent(prev => { const d = new Date(prev); d.setMonth(d.getMonth() - 1); return d; }); setSelectedDay(null) }}
              className="btn-ghost p-2"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              onClick={() => { setCurrent(new Date()); setSelectedDay(null) }}
              className="btn-secondary text-sm px-3 py-1.5"
            >
              Сегодня
            </button>
            <button
              onClick={() => { setCurrent(prev => { const d = new Date(prev); d.setMonth(d.getMonth() + 1); return d; }); setSelectedDay(null) }}
              className="btn-ghost p-2"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

        {/* Заголовки дней недели */}
        <div className="grid grid-cols-7 mb-1">
          {WEEKDAY_LABELS.map((label) => (
            <div key={label} className="text-center text-xs font-medium text-ink-secondary py-2">
              {label}
            </div>
          ))}
        </div>

        {/* Сетка дней */}
        {isLoading ? (
          <div className="grid grid-cols-7 gap-1">
            {Array(35).fill(null).map((_, i) => (
              <div key={i} className="h-20 bg-white rounded-sm animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-7 gap-1">
            {leadingEmpties.map((_, i) => (
              <div key={`e-${i}`} className="h-20" />
            ))}

            {allDays.map((day) => {
              const dateStr = format(day, "yyyy-MM-dd")
              const data = days[dateStr]
              const isSelected = selectedDay === dateStr
              const todayDay = isToday(day)
              const isGap = data?.is_gap && !data.total
              const hasError = data?.has_error

              return (
                <button
                  key={dateStr}
                  onClick={() => handleDayClick(dateStr)}
                  className={cn(
                    "h-20 p-2 rounded-sm text-left transition-all duration-100 border flex flex-col justify-between",
                    todayDay ? "bg-accent-light border-accent" : "bg-white border-transparent",
                    isSelected && "ring-2 ring-accent shadow-sm",
                    isGap && "border-red-200 bg-red-50",
                    hasError && !isGap && "border-red-300",
                    "hover:border-border-strong hover:shadow-sm"
                  )}
                >
                  <span className={cn(
                    "text-sm font-medium",
                    todayDay ? "text-accent" : "text-ink",
                    !isSameMonth(day, current) && "opacity-40"
                  )}>
                    {format(day, "d")}
                  </span>

                  <div>
                    {data && data.total > 0 ? (
                      <>
                        <div className="flex gap-0.5 flex-wrap mb-0.5">
                          {data.platforms.slice(0, 5).map((p, i) => (
                            <span
                              key={i}
                              className="w-2 h-2 rounded-full shrink-0"
                              style={{ backgroundColor: PLATFORM_DOT_COLORS[p] ?? "#888" }}
                            />
                          ))}
                        </div>
                        <p className="text-[10px] text-ink-secondary tabular-nums">
                          {data.total} {data.total === 1 ? "пост" : "поста"}
                        </p>
                      </>
                    ) : isGap ? (
                      <p className="text-[10px] text-red-400 font-medium">Пусто</p>
                    ) : null}
                  </div>
                </button>
              )
            })}
          </div>
        )}

        {/* Легенда */}
        <div className="flex items-center gap-4 mt-4 text-xs text-ink-secondary">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm bg-accent-light border border-accent inline-block" />
            Сегодня
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm bg-red-50 border border-red-200 inline-block" />
            Нет контента
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm bg-white border border-red-300 inline-block" />
            Ошибка
          </span>
        </div>
      </div>

      {/* Боковая панель дня */}
      {selectedDay && (
        <div className="w-72 shrink-0 border-l border-border bg-card flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <div>
              <p className="text-sm font-semibold text-ink">
                {format(new Date(selectedDay + "T12:00:00"), "d MMMM", { locale: ru })}
              </p>
              <p className="text-xs text-ink-secondary">
                {dayData?.posts?.length ?? "—"} постов
              </p>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => router.push("/editor")}
                className="flex items-center gap-1 text-xs btn-ghost py-1.5 px-2"
              >
                <Plus size={12} />
                Добавить
              </button>
              <button onClick={() => setSelectedDay(null)} className="btn-ghost p-1.5">
                <X size={14} />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {!dayData ? (
              <div className="p-3 space-y-2">
                {[1, 2].map((i) => (
                  <div key={i} className="h-16 bg-canvas rounded-nav animate-pulse" />
                ))}
              </div>
            ) : dayData.posts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-ink-secondary">
                <p className="text-sm mb-4">Нет постов</p>
                <button
                  onClick={() => router.push("/editor")}
                  className="btn-primary text-sm flex items-center gap-2"
                >
                  <Plus size={13} />
                  Создать
                </button>
              </div>
            ) : (
              <div className="p-3 space-y-2">
                {(dayData.posts as DayPost[]).map((post: DayPost) => (
                  <button
                    key={post.id}
                    onClick={() => router.push(`/editor/${post.id}`)}
                    className="w-full text-left p-3 rounded-nav bg-canvas hover:bg-border-strong/30 transition-colors group"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1.5">
                        <PlatformIcon platform={post.platform} size="sm" />
                        <span className="text-xs text-ink-secondary font-medium">
                          {post.scheduled_at
                            ? format(new Date(post.scheduled_at), "HH:mm")
                            : "—"}
                        </span>
                      </div>
                      <StatusBadge status={post.status} />
                    </div>
                    <p className="text-xs text-ink line-clamp-2 group-hover:text-accent transition-colors">
                      {post.body_preview || "Пустой черновик"}
                    </p>
                    {post.content_score !== null && (
                      <p className={cn(
                        "text-[10px] font-semibold mt-1",
                        post.content_score >= 80 ? "text-green-600" :
                        post.content_score >= 60 ? "text-amber-600" : "text-red-500"
                      )}>
                        Score {post.content_score}
                      </p>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
