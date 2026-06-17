"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"
import { useAccounts, usePillars } from "@/lib/queries"
import { postsApi } from "@/lib/api"
import { CONTENT_TYPE_LABELS, PLATFORM_LABELS } from "@/lib/utils"
import type { SocialAccount, ContentType, Platform } from "@/lib/types"

const PLATFORMS: Platform[] = ["telegram", "instagram", "linkedin", "x", "tiktok", "youtube"]
const CONTENT_TYPES = Object.entries(CONTENT_TYPE_LABELS) as [ContentType, string][]

export default function NewPostPage() {
  const router = useRouter()
  const { data: accounts = [] } = useAccounts()
  const { data: pillars = [] } = usePillars()

  const [platform, setPlatform] = useState<Platform>("telegram")
  const [contentType, setContentType] = useState<ContentType>("opinion")
  const [accountId, setAccountId] = useState<string>("")
  const [isCreating, setIsCreating] = useState(false)

  const filteredAccounts = (accounts as SocialAccount[]).filter(
    (a: SocialAccount) => a.platform === platform
  )

  async function handleCreate() {
    const accId = accountId || filteredAccounts[0]?.id
    if (!accId) {
      alert("Добавь аккаунт для этой платформы в Настройках")
      return
    }
    setIsCreating(true)
    try {
      const post = await postsApi.create({
        account_id: accId,
        platform,
        content_type: contentType,
        body: "",
        status: "draft",
      })
      router.push(`/editor/${post.id}`)
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-10">
      <h1 className="text-xl font-semibold text-ink mb-6">Новый пост</h1>

      {/* Платформа */}
      <div className="mb-5">
        <label className="text-xs font-medium text-ink-secondary uppercase tracking-wide mb-2 block">
          Платформа
        </label>
        <div className="flex flex-wrap gap-2">
          {PLATFORMS.map((p) => (
            <button
              key={p}
              onClick={() => { setPlatform(p); setAccountId("") }}
              className={`platform-chip ${platform === p ? "bg-accent-light border-accent text-accent" : ""}`}
            >
              {PLATFORM_LABELS[p]}
            </button>
          ))}
        </div>
      </div>

      {/* Тип контента */}
      <div className="mb-5">
        <label className="text-xs font-medium text-ink-secondary uppercase tracking-wide mb-2 block">
          Тип контента
        </label>
        <div className="flex flex-wrap gap-2">
          {CONTENT_TYPES.map(([type, label]) => (
            <button
              key={type}
              onClick={() => setContentType(type)}
              className={`platform-chip ${contentType === type ? "bg-accent-light border-accent text-accent" : ""}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Аккаунт */}
      {filteredAccounts.length > 1 && (
        <div className="mb-6">
          <label className="text-xs font-medium text-ink-secondary uppercase tracking-wide mb-2 block">
            Аккаунт
          </label>
          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            className="input-base"
          >
            {filteredAccounts.map((a: SocialAccount) => (
              <option key={a.id} value={a.id}>{a.display_name} (@{a.handle})</option>
            ))}
          </select>
        </div>
      )}

      {filteredAccounts.length === 0 && (
        <div className="mb-6 p-3 bg-amber-50 rounded-nav text-xs text-amber-700">
          Нет подключённых аккаунтов для {PLATFORM_LABELS[platform]}.{" "}
          <a href="/settings/accounts" className="underline">Добавить аккаунт</a>
        </div>
      )}

      <button
        onClick={handleCreate}
        disabled={isCreating}
        className="btn-primary w-full flex items-center justify-center gap-2"
      >
        {isCreating ? (
          <><Loader2 size={15} className="animate-spin" />Создаю...</>
        ) : (
          "Создать пост"
        )}
      </button>
    </div>
  )
}
