import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { format, formatDistanceToNow } from "date-fns"
import { ru } from "date-fns/locale"
import type { PipelineStatus, Platform, ContentType } from "./types"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | null): string {
  if (!date) return "—"
  return format(new Date(date), "d MMM, HH:mm", { locale: ru })
}

export function formatDateShort(date: string | null): string {
  if (!date) return "—"
  return format(new Date(date), "d MMM", { locale: ru })
}

export function formatRelative(date: string | null): string {
  if (!date) return "—"
  return formatDistanceToNow(new Date(date), { addSuffix: true, locale: ru })
}

export const STATUS_LABELS: Record<PipelineStatus, string> = {
  inbox: "Inbox",
  idea_approved: "Одобрена",
  draft: "Черновик",
  review: "На проверке",
  ready: "Готов",
  scheduled: "Запланирован",
  published: "Опубликован",
  error: "Ошибка",
}

export const STATUS_COLORS: Record<PipelineStatus, string> = {
  inbox: "bg-gray-100 text-gray-600",
  idea_approved: "bg-blue-50 text-blue-700",
  draft: "bg-amber-50 text-amber-700",
  review: "bg-purple-50 text-purple-700",
  ready: "bg-green-50 text-green-700",
  scheduled: "bg-accent-light text-accent",
  published: "bg-green-100 text-green-800",
  error: "bg-red-50 text-red-700",
}

export const PLATFORM_LABELS: Record<Platform, string> = {
  telegram: "Telegram",
  instagram: "Instagram",
  tiktok: "TikTok",
  youtube: "YouTube",
  linkedin: "LinkedIn",
  x: "X",
}

export const PLATFORM_COLORS: Record<Platform, string> = {
  telegram: "#0088cc",
  instagram: "#e1306c",
  tiktok: "#000000",
  youtube: "#ff0000",
  linkedin: "#0077b5",
  x: "#000000",
}

export const CONTENT_TYPE_LABELS: Record<ContentType, string> = {
  case: "Кейс",
  breakdown: "Разбор",
  how_to: "Инструкция",
  opinion: "Мнение",
  roundup: "Подборка",
  story: "История",
  observation: "Наблюдение",
  mistake: "Ошибка",
  lesson: "Урок",
  launch: "Запуск",
}

export function scoreColor(score: number | null): string {
  if (score === null) return "text-ink-secondary"
  if (score >= 80) return "text-green-600"
  if (score >= 60) return "text-amber-600"
  return "text-red-500"
}

export function scoreBg(score: number | null): string {
  if (score === null) return "bg-gray-100"
  if (score >= 80) return "bg-green-50"
  if (score >= 60) return "bg-amber-50"
  return "bg-red-50"
}
