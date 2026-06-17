"use client"

import { useState } from "react"
import { RefreshCw, Zap } from "lucide-react"
import { useIdeas, useApproveIdea, useRejectIdea, useBatchApprove, usePillars } from "@/lib/queries"
import { IdeaCard } from "@/components/inbox/IdeaCard"
import type { Idea, ContentPillar } from "@/lib/types"

export default function InboxPage() {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const { data: ideas = [], isLoading, refetch } = useIdeas({ status: "inbox" })
  const { data: pillars = [] } = usePillars()
  const approve = useApproveIdea()
  const reject = useRejectIdea()
  const batchApprove = useBatchApprove()

  const pillarMap = Object.fromEntries(
    (pillars as ContentPillar[]).map((p: ContentPillar) => [p.id, p])
  )

  function toggleSelect(id: string, checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev)
      checked ? next.add(id) : next.delete(id)
      return next
    })
  }

  function toggleAll() {
    if (selected.size === ideas.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set((ideas as Idea[]).map((i: Idea) => i.id)))
    }
  }

  async function handleBatchApprove() {
    if (!selected.size) return
    await batchApprove.mutateAsync(Array.from(selected))
    setSelected(new Set())
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-ink">Inbox</h1>
          <p className="text-sm text-ink-secondary mt-0.5">
            {isLoading ? "Загрузка..." : `${ideas.length} новых идей`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => refetch()} className="btn-ghost" title="Обновить">
            <RefreshCw size={15} />
          </button>
          {selected.size > 0 && (
            <button
              onClick={handleBatchApprove}
              disabled={batchApprove.isPending}
              className="btn-primary flex items-center gap-2"
            >
              <Zap size={14} />
              Одобрить ({selected.size})
            </button>
          )}
        </div>
      </div>

      {/* Select all */}
      {ideas.length > 0 && (
        <div className="flex items-center gap-2 mb-3 px-1">
          <input
            type="checkbox"
            checked={selected.size === ideas.length && ideas.length > 0}
            onChange={toggleAll}
            className="w-4 h-4 accent-accent cursor-pointer"
          />
          <span className="text-xs text-ink-secondary">
            {selected.size === ideas.length ? "Снять всё" : "Выбрать все"}
          </span>
        </div>
      )}

      {/* Ideas list */}
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card p-4 animate-pulse">
              <div className="h-4 bg-gray-100 rounded w-3/4 mb-2" />
              <div className="h-3 bg-gray-100 rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : ideas.length === 0 ? (
        <div className="text-center py-16 text-ink-secondary">
          <div className="text-4xl mb-3">📭</div>
          <p className="text-sm font-medium">Inbox пуст</p>
          <p className="text-xs mt-1">Новые идеи появятся здесь автоматически</p>
        </div>
      ) : (
        <div className="space-y-3">
          {(ideas as Idea[]).map((idea: Idea) => (
            <IdeaCard
              key={idea.id}
              idea={idea}
              pillar={pillarMap[idea.pillar_id ?? ""]}
              selected={selected.has(idea.id)}
              onSelect={toggleSelect}
              onApprove={(id) => approve.mutate(id)}
              onReject={(id) => reject.mutate({ id })}
            />
          ))}
        </div>
      )}
    </div>
  )
}
