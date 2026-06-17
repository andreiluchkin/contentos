"use client"

import { useState, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Search, Plus, X, Edit2, Save, Loader2, BookOpen, Tag, ChevronRight,
} from "lucide-react"
import { kbApi } from "@/lib/api"
import { cn } from "@/lib/utils"

interface KBItem {
  id: string
  item_type: string
  title: string
  body: string
  tags: string[]
  pillar_id: string | null
  source_post_id: string | null
  is_active: boolean
}

const ITEM_TYPE_LABELS: Record<string, string> = {
  note: "Заметка",
  case: "Кейс",
  post: "Пост",
  document: "Документ",
}

const ITEM_TYPE_COLORS: Record<string, string> = {
  note: "bg-blue-50 text-blue-700",
  case: "bg-green-50 text-green-700",
  post: "bg-accent/10 text-accent",
  document: "bg-amber-50 text-amber-700",
}

const ITEM_TYPES = ["note", "case", "post", "document"] as const

interface EditState {
  id: string | null  // null = new
  item_type: string
  title: string
  body: string
  tags: string
}

const EMPTY_EDIT: EditState = { id: null, item_type: "note", title: "", body: "", tags: "" }

export default function KnowledgeBasePage() {
  const qc = useQueryClient()

  const [search, setSearch] = useState("")
  const [filterType, setFilterType] = useState<string | null>(null)
  const [editItem, setEditItem] = useState<EditState | null>(null)
  const [selectedItem, setSelectedItem] = useState<KBItem | null>(null)

  const { data: items = [], isLoading } = useQuery<KBItem[]>({
    queryKey: ["kb", search, filterType],
    queryFn: () => kbApi.list({
      search: search || undefined,
      item_type: filterType || undefined,
    }),
  })

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => kbApi.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["kb"] }); setEditItem(null) },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: string } & Record<string, unknown>) =>
      kbApi.update(id, data),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ["kb"] })
      setEditItem(null)
      setSelectedItem(updated)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => kbApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["kb"] }); setSelectedItem(null) },
  })

  function openNew() {
    setEditItem({ ...EMPTY_EDIT })
    setSelectedItem(null)
  }

  function openEdit(item: KBItem) {
    setEditItem({
      id: item.id,
      item_type: item.item_type,
      title: item.title,
      body: item.body,
      tags: item.tags.join(", "),
    })
  }

  async function handleSave() {
    if (!editItem) return
    const payload = {
      item_type: editItem.item_type,
      title: editItem.title.trim(),
      body: editItem.body.trim(),
      tags: editItem.tags.split(/[,\s]+/).map((t) => t.trim()).filter(Boolean),
    }
    if (!payload.title || !payload.body) return

    if (editItem.id) {
      updateMutation.mutate({ id: editItem.id, ...payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending
  const isEditing = editItem !== null

  return (
    <div className="flex h-full overflow-hidden">
      {/* List panel */}
      <div className={cn(
        "flex flex-col border-r border-border bg-card transition-all",
        selectedItem || isEditing ? "w-72 shrink-0" : "flex-1"
      )}>
        {/* Header */}
        <div className="px-4 py-4 border-b border-border">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-sm font-semibold text-ink">Knowledge Base</h1>
            <button onClick={openNew} className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1">
              <Plus size={12} />
              Добавить
            </button>
          </div>

          {/* Search */}
          <div className="relative mb-3">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-secondary" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск..."
              className="input-base w-full pl-8 text-sm"
            />
          </div>

          {/* Type filter */}
          <div className="flex gap-1 flex-wrap">
            <button
              onClick={() => setFilterType(null)}
              className={cn(
                "text-[11px] px-2.5 py-1 rounded-full border transition-all",
                !filterType ? "border-accent bg-accent/10 text-accent" : "border-border text-ink-secondary hover:text-ink"
              )}
            >
              Все
            </button>
            {ITEM_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setFilterType(filterType === t ? null : t)}
                className={cn(
                  "text-[11px] px-2.5 py-1 rounded-full border transition-all",
                  filterType === t ? "border-accent bg-accent/10 text-accent" : "border-border text-ink-secondary hover:text-ink"
                )}
              >
                {ITEM_TYPE_LABELS[t]}
              </button>
            ))}
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-3 space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 bg-canvas rounded-nav animate-pulse" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-ink-secondary px-4 text-center">
              <BookOpen size={28} className="mb-3 opacity-30" />
              <p className="text-sm mb-1">База знаний пуста</p>
              <p className="text-xs">Добавь заметки, кейсы или импортируй опубликованные посты</p>
            </div>
          ) : (
            <div className="p-2 space-y-1">
              {items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => { setSelectedItem(item); setEditItem(null) }}
                  className={cn(
                    "w-full text-left p-3 rounded-nav transition-all group",
                    selectedItem?.id === item.id
                      ? "bg-accent/5 border border-accent/20"
                      : "hover:bg-canvas border border-transparent"
                  )}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className={cn(
                      "text-[10px] font-medium px-1.5 py-0.5 rounded",
                      ITEM_TYPE_COLORS[item.item_type] ?? "bg-gray-100 text-gray-600"
                    )}>
                      {ITEM_TYPE_LABELS[item.item_type] ?? item.item_type}
                    </span>
                    {item.source_post_id && (
                      <span className="text-[9px] text-ink-secondary/60">из поста</span>
                    )}
                  </div>
                  <p className="text-xs font-medium text-ink truncate">{item.title}</p>
                  <p className="text-[11px] text-ink-secondary mt-0.5 line-clamp-1">{item.body}</p>
                  {item.tags.length > 0 && (
                    <div className="flex gap-1 mt-1.5 flex-wrap">
                      {item.tags.slice(0, 3).map((tag) => (
                        <span key={tag} className="text-[9px] bg-canvas text-ink-secondary px-1.5 py-0.5 rounded">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="px-4 py-2 border-t border-border">
          <p className="text-xs text-ink-secondary">{items.length} записей</p>
        </div>
      </div>

      {/* Detail / Edit panel */}
      {(selectedItem || isEditing) && (
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Panel header */}
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-border bg-white shrink-0">
            <div className="flex items-center gap-2">
              {isEditing ? (
                <span className="text-sm font-medium text-ink">
                  {editItem?.id ? "Редактировать" : "Новая запись"}
                </span>
              ) : (
                <span className="text-sm font-medium text-ink truncate max-w-xs">
                  {selectedItem?.title}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5">
              {!isEditing && selectedItem && (
                <>
                  <button
                    onClick={() => openEdit(selectedItem)}
                    className="btn-ghost flex items-center gap-1 text-xs"
                  >
                    <Edit2 size={12} />
                    Изменить
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(selectedItem.id)}
                    disabled={deleteMutation.isPending}
                    className="btn-ghost text-xs text-red-500 hover:bg-red-50"
                  >
                    <X size={12} />
                  </button>
                </>
              )}
              {isEditing && (
                <>
                  <button
                    onClick={() => setEditItem(null)}
                    className="btn-ghost text-xs"
                  >
                    Отмена
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={isSaving || !editItem?.title.trim() || !editItem?.body.trim()}
                    className="btn-primary flex items-center gap-1.5 text-sm"
                  >
                    {isSaving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                    Сохранить
                  </button>
                </>
              )}
              <button
                onClick={() => { setSelectedItem(null); setEditItem(null) }}
                className="btn-ghost p-1.5"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-5">
            {isEditing && editItem ? (
              <div className="max-w-2xl space-y-4">
                {/* Type */}
                <div>
                  <label className="block text-xs font-medium text-ink-secondary mb-2">Тип</label>
                  <div className="flex gap-2">
                    {ITEM_TYPES.map((t) => (
                      <button
                        key={t}
                        onClick={() => setEditItem((prev) => prev ? { ...prev, item_type: t } : prev)}
                        className={cn(
                          "text-xs px-3 py-1.5 rounded-full border transition-all",
                          editItem.item_type === t
                            ? "border-accent bg-accent/10 text-accent"
                            : "border-border text-ink-secondary hover:text-ink"
                        )}
                      >
                        {ITEM_TYPE_LABELS[t]}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Title */}
                <div>
                  <label className="block text-xs font-medium text-ink-secondary mb-1.5">Заголовок</label>
                  <input
                    value={editItem.title}
                    onChange={(e) => setEditItem((prev) => prev ? { ...prev, title: e.target.value } : prev)}
                    placeholder="Название записи..."
                    className="input-base w-full"
                  />
                </div>

                {/* Body */}
                <div>
                  <label className="block text-xs font-medium text-ink-secondary mb-1.5">Содержание</label>
                  <textarea
                    value={editItem.body}
                    onChange={(e) => setEditItem((prev) => prev ? { ...prev, body: e.target.value } : prev)}
                    placeholder="Текст записи..."
                    rows={12}
                    className="input-base w-full resize-none text-sm leading-relaxed font-ui"
                  />
                </div>

                {/* Tags */}
                <div>
                  <label className="block text-xs font-medium text-ink-secondary mb-1.5">
                    Теги <span className="font-normal opacity-60">(через запятую или пробел)</span>
                  </label>
                  <div className="relative">
                    <Tag size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-secondary" />
                    <input
                      value={editItem.tags}
                      onChange={(e) => setEditItem((prev) => prev ? { ...prev, tags: e.target.value } : prev)}
                      placeholder="продажи, опыт, кейс..."
                      className="input-base w-full pl-8"
                    />
                  </div>
                </div>
              </div>
            ) : selectedItem ? (
              <div className="max-w-2xl">
                <div className="flex items-center gap-2 mb-4">
                  <span className={cn(
                    "text-xs font-medium px-2 py-0.5 rounded",
                    ITEM_TYPE_COLORS[selectedItem.item_type] ?? "bg-gray-100 text-gray-600"
                  )}>
                    {ITEM_TYPE_LABELS[selectedItem.item_type] ?? selectedItem.item_type}
                  </span>
                  {selectedItem.tags.map((tag) => (
                    <span key={tag} className="text-xs bg-canvas text-ink-secondary px-2 py-0.5 rounded-full">
                      #{tag}
                    </span>
                  ))}
                </div>

                <h2 className="text-base font-semibold text-ink mb-4">{selectedItem.title}</h2>

                <div className="text-sm text-ink leading-relaxed whitespace-pre-wrap">
                  {selectedItem.body}
                </div>

                {selectedItem.source_post_id && (
                  <div className="mt-6 pt-4 border-t border-border">
                    <p className="text-xs text-ink-secondary">Импортировано из опубликованного поста</p>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
