"use client"

import { useState, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Loader2, LogIn } from "lucide-react"
import { login } from "@/lib/auth"

function LoginForm() {
  const router = useRouter()
  const params = useSearchParams()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      await login(username, password)
      const from = params.get("from") ?? "/inbox"
      router.replace(from)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Ошибка входа")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-canvas flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-ink tracking-tight">
            Content<span className="text-accent">OS</span>
          </h1>
          <p className="text-sm text-ink-secondary mt-1">Войдите чтобы продолжить</p>
        </div>

        <div className="card">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-ink-secondary">Логин</label>
              <input
                type="text"
                autoComplete="username"
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-3 py-2.5 text-sm border border-border rounded-nav bg-white text-ink placeholder:text-ink-secondary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition"
                placeholder="admin"
                required
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-ink-secondary">Пароль</label>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2.5 text-sm border border-border rounded-nav bg-white text-ink placeholder:text-ink-secondary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition"
                placeholder="••••••••"
                required
              />
            </div>

            {error && (
              <p className="text-xs text-red-500 bg-red-50 px-3 py-2 rounded-nav">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 py-2.5"
            >
              {loading ? <Loader2 size={15} className="animate-spin" /> : <LogIn size={15} />}
              {loading ? "Входим..." : "Войти"}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  )
}
