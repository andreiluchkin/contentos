"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Plus, X, RefreshCw, Loader2, CheckCircle2, AlertCircle, ChevronDown,
} from "lucide-react"
import { accountsApi } from "@/lib/api"
import { PlatformIcon } from "@/components/shared/PlatformIcon"
import { PLATFORM_LABELS, cn } from "@/lib/utils"
import type { Platform, SocialAccount } from "@/lib/types"

type ConnectPlatform = "telegram" | "instagram" | "tiktok" | "youtube" | "linkedin" | "x"

interface FormField {
  key: string
  label: string
  placeholder: string
  type?: "text" | "password"
  hint?: string
}

const PLATFORM_FORMS: Record<ConnectPlatform, { fields: FormField[]; guide: string }> = {
  telegram: {
    guide: "Создай бота через @BotFather, добавь его администратором в канал",
    fields: [
      { key: "handle", label: "Username канала", placeholder: "mychannel (без @)" },
      { key: "display_name", label: "Название", placeholder: "Мой канал" },
      { key: "bot_token", label: "Bot Token", placeholder: "1234567890:AAF...", type: "password" },
      { key: "chat_id", label: "Chat ID", placeholder: "-1001234567890", hint: "Отправь /start боту и узнай через @userinfobot" },
    ],
  },
  instagram: {
    guide: "Нужен Professional аккаунт. Получи Long-lived токен через Facebook Developer Console",
    fields: [
      { key: "handle", label: "Instagram username", placeholder: "myaccount (без @)" },
      { key: "display_name", label: "Название", placeholder: "Мой Instagram" },
      { key: "ig_user_id", label: "Instagram User ID", placeholder: "17841400000000000" },
      { key: "access_token", label: "Access Token", placeholder: "EAABs...", type: "password" },
      { key: "facebook_page_id", label: "Facebook Page ID (опционально)", placeholder: "123456789" },
    ],
  },
  tiktok: {
    guide: "Нужен TikTok for Business аккаунт. Авторизуй через TikTok Developer Portal",
    fields: [
      { key: "handle", label: "TikTok username", placeholder: "myaccount (без @)" },
      { key: "display_name", label: "Название", placeholder: "Мой TikTok" },
      { key: "open_id", label: "Open ID", placeholder: "xxx" },
      { key: "access_token", label: "Access Token", placeholder: "act.xxx", type: "password" },
      { key: "refresh_token", label: "Refresh Token", placeholder: "rft.xxx", type: "password" },
    ],
  },
  youtube: {
    guide: "Получи токены через Google Cloud Console → YouTube Data API v3 → OAuth 2.0",
    fields: [
      { key: "handle", label: "Channel handle / ID", placeholder: "@mychannel или UCxxxxxx" },
      { key: "display_name", label: "Название", placeholder: "Мой YouTube канал" },
      { key: "channel_id", label: "Channel ID", placeholder: "UCxxxxxxxxxxxxxxxxxx" },
      { key: "access_token", label: "Access Token", placeholder: "ya29.xxx", type: "password" },
      { key: "refresh_token", label: "Refresh Token", placeholder: "1//xxx", type: "password" },
    ],
  },
  linkedin: {
    guide: "Создай приложение в LinkedIn Developer Portal, получи токен через OAuth 2.0 (scopes: r_liteprofile, w_member_social)",
    fields: [
      { key: "handle", label: "Profile slug", placeholder: "ivan-petrov или company-name" },
      { key: "display_name", label: "Название", placeholder: "Мой LinkedIn" },
      { key: "person_urn", label: "Person URN", placeholder: "urn:li:person:XXXXXXXX", hint: "Получи через GET /v2/me после авторизации" },
      { key: "access_token", label: "Access Token", placeholder: "AQV...", type: "password" },
      { key: "refresh_token", label: "Refresh Token (если есть)", placeholder: "AQX..." },
    ],
  },
  x: {
    guide: "Создай проект в X Developer Portal, используй OAuth 2.0 PKCE (scopes: tweet.read, tweet.write, users.read, offline.access)",
    fields: [
      { key: "handle", label: "X username", placeholder: "myaccount (без @)" },
      { key: "display_name", label: "Название", placeholder: "Мой X" },
      { key: "user_id", label: "User ID", placeholder: "1234567890", hint: "Числовой ID, получи через GET /2/users/me" },
      { key: "access_token", label: "Access Token", placeholder: "xxx", type: "password" },
      { key: "refresh_token", label: "Refresh Token", placeholder: "xxx", type: "password" },
    ],
  },
}

const CONNECT_PLATFORMS: ConnectPlatform[] = ["telegram", "instagram", "tiktok", "youtube", "linkedin", "x"]

export default function SettingsPage() {
  const qc = useQueryClient()
  const [connectingPlatform, setConnectingPlatform] = useState<ConnectPlatform | null>(null)
  const [formValues, setFormValues] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)

  const { data: accounts = [], isLoading } = useQuery<SocialAccount[]>({
    queryKey: ["accounts"],
    queryFn: () => accountsApi.list(),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => accountsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  })

  const refreshMutation = useMutation({
    mutationFn: (id: string) => accountsApi.refreshToken(id),
  })

  const connectMutation = useMutation({
    mutationFn: async ({ platform, values }: { platform: ConnectPlatform; values: Record<string, string> }) => {
      switch (platform) {
        case "telegram": return accountsApi.addTelegram(values)
        case "instagram": return accountsApi.addInstagram(values)
        case "tiktok": return accountsApi.addTikTok(values)
        case "youtube": return accountsApi.addYouTube(values)
        case "linkedin": return accountsApi.addLinkedIn(values)
        case "x": return accountsApi.addX(values)
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts"] })
      setConnectingPlatform(null)
      setFormValues({})
      setFormError(null)
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Ошибка подключения"
      setFormError(msg)
    },
  })

  function handleFormSubmit() {
    if (!connectingPlatform) return
    setFormError(null)
    connectMutation.mutate({ platform: connectingPlatform, values: formValues })
  }

  function openConnect(platform: ConnectPlatform) {
    setConnectingPlatform(platform)
    setFormValues({})
    setFormError(null)
  }

  const tokenExpiresIn = (account: SocialAccount) => {
    if (!account.token_expires_at) return null
    const diffMs = new Date(account.token_expires_at).getTime() - Date.now()
    if (diffMs < 0) return "истёк"
    const diffH = Math.round(diffMs / 3600000)
    if (diffH < 24) return `${diffH}ч`
    return `${Math.round(diffH / 24)}д`
  }

  const formConfig = connectingPlatform ? PLATFORM_FORMS[connectingPlatform] : null

  return (
    <div className="overflow-y-auto h-full px-4 py-6">
      <div className="max-w-2xl mx-auto space-y-6">

        <div>
          <h1 className="text-xl font-semibold text-ink mb-1">Настройки</h1>
          <p className="text-sm text-ink-secondary">Управление аккаунтами социальных сетей</p>
        </div>

        {/* Connected accounts */}
        <section className="card">
          <h2 className="text-sm font-semibold text-ink mb-4">Подключённые аккаунты</h2>

          {isLoading ? (
            <div className="space-y-2">
              {[1, 2].map((i) => <div key={i} className="h-14 bg-canvas rounded-nav animate-pulse" />)}
            </div>
          ) : (accounts as SocialAccount[]).length === 0 ? (
            <p className="text-sm text-ink-secondary text-center py-6">
              Нет подключённых аккаунтов
            </p>
          ) : (
            <div className="space-y-2">
              {(accounts as SocialAccount[]).map((account) => {
                const expiry = tokenExpiresIn(account)
                const isExpired = expiry === "истёк"
                return (
                  <div key={account.id} className="flex items-center justify-between p-3 bg-canvas rounded-nav">
                    <div className="flex items-center gap-3">
                      <PlatformIcon platform={account.platform as Platform} size="sm" />
                      <div>
                        <p className="text-sm font-medium text-ink">{account.display_name}</p>
                        <p className="text-xs text-ink-secondary">@{account.handle}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {expiry && (
                        <span className={cn(
                          "text-[10px] px-2 py-0.5 rounded-full",
                          isExpired ? "bg-red-50 text-red-600" : "bg-green-50 text-green-700"
                        )}>
                          {isExpired ? <AlertCircle size={10} className="inline mr-0.5" /> : <CheckCircle2 size={10} className="inline mr-0.5" />}
                          {expiry}
                        </span>
                      )}
                      <button
                        onClick={() => refreshMutation.mutate(account.id)}
                        disabled={refreshMutation.isPending}
                        title="Обновить токен"
                        className="btn-ghost p-1.5 text-ink-secondary hover:text-ink"
                      >
                        <RefreshCw size={13} className={refreshMutation.isPending ? "animate-spin" : ""} />
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(account.id)}
                        className="btn-ghost p-1.5 text-ink-secondary hover:text-red-500"
                      >
                        <X size={13} />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </section>

        {/* Connect new */}
        <section className="card">
          <h2 className="text-sm font-semibold text-ink mb-4">Подключить аккаунт</h2>

          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 mb-4">
            {CONNECT_PLATFORMS.map((p) => (
              <button
                key={p}
                onClick={() => openConnect(p)}
                className={cn(
                  "flex flex-col items-center gap-1.5 py-3 px-2 rounded-nav border transition-all text-xs",
                  connectingPlatform === p
                    ? "border-accent bg-accent/5 text-accent"
                    : "border-border text-ink-secondary hover:border-border-strong hover:text-ink"
                )}
              >
                <PlatformIcon platform={p as Platform} size="sm" />
                <span>{PLATFORM_LABELS[p as Platform]}</span>
              </button>
            ))}
          </div>

          {/* Connect form */}
          {connectingPlatform && formConfig && (
            <div className="border border-border rounded-nav p-4 space-y-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-ink flex items-center gap-1.5">
                    <PlatformIcon platform={connectingPlatform as Platform} size="sm" />
                    Подключить {PLATFORM_LABELS[connectingPlatform as Platform]}
                  </p>
                  <p className="text-xs text-ink-secondary mt-0.5">{formConfig.guide}</p>
                </div>
                <button onClick={() => setConnectingPlatform(null)} className="btn-ghost p-1 shrink-0">
                  <X size={13} />
                </button>
              </div>

              <div className="space-y-3">
                {formConfig.fields.map((field) => (
                  <div key={field.key}>
                    <label className="block text-xs font-medium text-ink-secondary mb-1">
                      {field.label}
                    </label>
                    <input
                      type={field.type ?? "text"}
                      value={formValues[field.key] ?? ""}
                      onChange={(e) => setFormValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                      placeholder={field.placeholder}
                      className="input-base w-full text-sm"
                    />
                    {field.hint && (
                      <p className="text-[10px] text-ink-secondary mt-1">{field.hint}</p>
                    )}
                  </div>
                ))}
              </div>

              {formError && (
                <p className="text-xs text-red-500 bg-red-50 px-3 py-2 rounded-nav">
                  {formError}
                </p>
              )}

              <button
                onClick={handleFormSubmit}
                disabled={connectMutation.isPending}
                className="btn-primary w-full flex items-center justify-center gap-2"
              >
                {connectMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                Подключить
              </button>
            </div>
          )}
        </section>

      </div>
    </div>
  )
}
