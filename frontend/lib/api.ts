import axios from "axios"

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? ""

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    "Content-Type": "application/json",
    ...(API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}),
  },
})

// --- Ideas ---
export const ideasApi = {
  list: (params?: Record<string, string>) =>
    api.get("/ideas", { params }).then((r) => r.data),
  get: (id: string) => api.get(`/ideas/${id}`).then((r) => r.data),
  approve: (id: string) => api.patch(`/ideas/${id}/approve`).then((r) => r.data),
  reject: (id: string, reason?: string) =>
    api.patch(`/ideas/${id}/reject`, { reason }).then((r) => r.data),
  batchApprove: (ids: string[]) =>
    api.post("/ideas/batch-approve", { idea_ids: ids }).then((r) => r.data),
  delete: (id: string) => api.delete(`/ideas/${id}`),
}

// --- Posts ---
export const postsApi = {
  list: (params?: Record<string, string | undefined>) =>
    api.get("/posts", { params }).then((r) => r.data),
  get: (id: string) => api.get(`/posts/${id}`).then((r) => r.data),
  create: (data: Record<string, unknown>) =>
    api.post("/posts", data).then((r) => r.data),
  update: (id: string, data: Record<string, unknown>) =>
    api.patch(`/posts/${id}`, data).then((r) => r.data),
  updateStatus: (id: string, status: string) =>
    api.patch(`/posts/${id}/status`, { status }).then((r) => r.data),
  schedule: (id: string, scheduledAt: string) =>
    api.patch(`/posts/${id}/schedule`, { scheduled_at: scheduledAt }).then((r) => r.data),
  unschedule: (id: string) =>
    api.delete(`/posts/${id}/schedule`).then((r) => r.data),
  delete: (id: string) => api.delete(`/posts/${id}`),
  duplicate: (id: string) => api.post(`/posts/${id}/duplicate`).then((r) => r.data),
  history: (id: string) => api.get(`/posts/${id}/history`).then((r) => r.data),
  batchGenerate: (data: Record<string, unknown>) =>
    api.post("/posts/batch-generate", data).then((r) => r.data),
}

// --- AI ---
export const aiApi = {
  generateDirect: (data: Record<string, unknown>) =>
    api.post("/ai/generate-post", data).then((r) => r.data),
  generateForPost: (postId: string) =>
    api.post(`/ai/posts/${postId}/generate`).then((r) => r.data),
  score: (postId: string) =>
    api.post(`/ai/posts/${postId}/score`).then((r) => r.data),
  improve: (postId: string, issues?: string[]) =>
    api.post(`/ai/posts/${postId}/improve`, { post_id: postId, score_issues: issues }).then((r) => r.data),
  scoreText: (body: string, platform: string) =>
    api.post("/ai/score", { body, platform }).then((r) => r.data),
}

// --- Calendar ---
export const calendarApi = {
  month: (year: number, month: number, platform?: string) =>
    api.get("/calendar/month", { params: { year, month, platform } }).then((r) => r.data),
  day: (date: string) =>
    api.get(`/calendar/day/${date}`).then((r) => r.data),
  week: (year: number, week: number) =>
    api.get("/calendar/week", { params: { year, week } }).then((r) => r.data),
  gaps: () => api.get("/calendar/gaps").then((r) => r.data),
  nextSlot: (accountId: string, after?: string) =>
    api.get("/calendar/next-slot", { params: { account_id: accountId, after } }).then((r) => r.data),
}

// --- Pillars ---
export const pillarsApi = {
  list: () => api.get("/pillars").then((r) => r.data),
  create: (data: Record<string, unknown>) =>
    api.post("/pillars", data).then((r) => r.data),
  update: (id: string, data: Record<string, unknown>) =>
    api.patch(`/pillars/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/pillars/${id}`),
}

// --- Accounts ---
export const accountsApi = {
  list: () => api.get("/accounts").then((r) => r.data),
  addTelegram: (data: Record<string, unknown>) =>
    api.post("/accounts/telegram", data).then((r) => r.data),
  addInstagram: (data: Record<string, unknown>) =>
    api.post("/accounts/instagram", data).then((r) => r.data),
  addTikTok: (data: Record<string, unknown>) =>
    api.post("/accounts/tiktok", data).then((r) => r.data),
  addYouTube: (data: Record<string, unknown>) =>
    api.post("/accounts/youtube", data).then((r) => r.data),
  addLinkedIn: (data: Record<string, unknown>) =>
    api.post("/accounts/linkedin", data).then((r) => r.data),
  addX: (data: Record<string, unknown>) =>
    api.post("/accounts/x", data).then((r) => r.data),
  refreshToken: (id: string) =>
    api.post(`/accounts/${id}/refresh-token`).then((r) => r.data),
  delete: (id: string) => api.delete(`/accounts/${id}`),
}

// --- Media ---
export const mediaApi = {
  list: (mediaType?: string) =>
    api.get("/media", { params: { media_type: mediaType } }).then((r) => r.data),
  get: (id: string) => api.get(`/media/${id}`).then((r) => r.data),
  upload: (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return api.post("/media/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data)
  },
  delete: (id: string) => api.delete(`/media/${id}`),
}

// --- Analytics ---
export const analyticsApi = {
  overview: () => api.get("/analytics/overview").then((r) => r.data),
  posts: (params?: Record<string, string | undefined>) =>
    api.get("/analytics/posts", { params }).then((r) => r.data),
  pillars: () => api.get("/analytics/pillars").then((r) => r.data),
  timeline: (days = 30) => api.get("/analytics/timeline", { params: { days } }).then((r) => r.data),
}

// --- Brand Voice ---
export const brandVoiceApi = {
  get: () => api.get("/brand-voice").then((r) => r.data),
  update: (data: Record<string, unknown>) =>
    api.put("/brand-voice", data).then((r) => r.data),
  addExample: (text: string, platform: string) =>
    api.post("/brand-voice/example-posts", { text, platform }).then((r) => r.data),
  deleteExample: (index: number) =>
    api.delete(`/brand-voice/example-posts/${index}`).then((r) => r.data),
  regeneratePrompt: () =>
    api.post("/brand-voice/regenerate-prompt").then((r) => r.data),
}

// --- Knowledge Base ---
export const kbApi = {
  list: (params?: Record<string, string | undefined>) =>
    api.get("/kb", { params }).then((r) => r.data),
  get: (id: string) => api.get(`/kb/${id}`).then((r) => r.data),
  create: (data: Record<string, unknown>) =>
    api.post("/kb", data).then((r) => r.data),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/kb/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/kb/${id}`),
  search: (query: string, limit = 5) =>
    api.post("/kb/search", { query, limit }).then((r) => r.data),
  importPost: (postId: string) =>
    api.post(`/kb/import-post/${postId}`).then((r) => r.data),
}

// --- Publishing ---
export const publishingApi = {
  publishNow: (id: string) => api.post(`/posts/${id}/publish-now`).then((r) => r.data),
  approve: (id: string) => api.post(`/posts/${id}/approve`).then((r) => r.data),
  reject: (id: string, reason?: string) =>
    api.post(`/posts/${id}/reject`, { reason }).then((r) => r.data),
  reviewQueue: () => api.get("/posts/review-queue").then((r) => r.data),
}

// --- Repurpose ---
export const repurposeApi = {
  list: () => api.get("/repurpose").then((r) => r.data),
  get: (id: string) => api.get(`/repurpose/${id}`).then((r) => r.data),
  uploadFile: (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return api.post("/repurpose/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data)
  },
  youtube: (url: string) =>
    api.post("/repurpose/youtube", { url }).then((r) => r.data),
  text: (text: string) =>
    api.post("/repurpose/text", { text }).then((r) => r.data),
  createPosts: (id: string, data: Record<string, unknown>) =>
    api.post(`/repurpose/${id}/create-posts`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/repurpose/${id}`),
}
