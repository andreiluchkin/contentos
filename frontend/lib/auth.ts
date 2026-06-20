const TOKEN_KEY = "access_token"

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem(TOKEN_KEY)
}

export function setAccessToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
  // Также кладём в cookie для middleware (без httpOnly — читается JS)
  document.cookie = `access_token=${token}; path=/; max-age=3600; SameSite=Lax`
}

export function clearAccessToken() {
  localStorage.removeItem(TOKEN_KEY)
  document.cookie = "access_token=; path=/; max-age=0"
}

export async function refreshAccessToken(): Promise<string | null> {
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
    if (!res.ok) return null
    const data = await res.json()
    setAccessToken(data.access_token)
    return data.access_token
  } catch {
    return null
  }
}

export async function login(username: string, password: string): Promise<string> {
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
    credentials: "include",
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? "Invalid credentials")
  }
  const data = await res.json()
  setAccessToken(data.access_token)
  return data.access_token
}

export async function logout() {
  const token = getAccessToken()
  if (token) {
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    }).catch(() => {})
  }
  clearAccessToken()
}
