"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import {
  Inbox,
  LayoutList,
  PenLine,
  Calendar,
  Repeat2,
  Mic2,
  BookOpen,
  BarChart2,
  ClipboardCheck,
  Settings,
  LogOut,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { publishingApi } from "@/lib/api"
import { logout } from "@/lib/auth"

const NAV_ITEMS = [
  { href: "/inbox", icon: Inbox, label: "Inbox" },
  { href: "/backlog", icon: LayoutList, label: "Backlog" },
  { href: "/review", icon: ClipboardCheck, label: "Проверка", badge: true },
  { href: "/editor", icon: PenLine, label: "Редактор" },
  { href: "/calendar", icon: Calendar, label: "Календарь" },
  { href: "/repurpose", icon: Repeat2, label: "Repurpose" },
  { href: "/brand-voice", icon: Mic2, label: "Brand Voice" },
  { href: "/knowledge-base", icon: BookOpen, label: "База знаний" },
  { href: "/analytics", icon: BarChart2, label: "Аналитика" },
]

export function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()

  async function handleLogout() {
    await logout()
    router.push("/login")
  }

  const { data: reviewQueue = [] } = useQuery<unknown[]>({
    queryKey: ["review-queue"],
    queryFn: publishingApi.reviewQueue,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
  const reviewCount = reviewQueue.length

  return (
    <aside className="hidden md:flex flex-col w-[220px] shrink-0 bg-card border-r border-border h-screen">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-border">
        <span className="text-base font-semibold text-ink tracking-tight">
          Content<span className="text-accent">OS</span>
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ href, icon: Icon, label, badge }) => {
          const isActive = pathname === href || pathname.startsWith(href + "/")
          const count = badge && href === "/review" ? reviewCount : 0
          return (
            <Link
              key={href}
              href={href}
              className={cn("sidebar-link", isActive && "sidebar-link-active")}
            >
              <Icon size={16} strokeWidth={1.75} />
              <span className="flex-1">{label}</span>
              {count > 0 && (
                <span className="ml-auto text-[10px] font-semibold bg-accent text-white rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1">
                  {count}
                </span>
              )}
            </Link>
          )
        })}
      </nav>

      {/* Settings + Logout */}
      <div className="px-3 py-3 border-t border-border space-y-0.5">
        <Link
          href="/settings"
          className={cn(
            "sidebar-link",
            pathname.startsWith("/settings") && "sidebar-link-active"
          )}
        >
          <Settings size={16} strokeWidth={1.75} />
          <span>Настройки</span>
        </Link>
        <button
          onClick={handleLogout}
          className="sidebar-link w-full text-left text-ink-secondary hover:text-red-500"
        >
          <LogOut size={16} strokeWidth={1.75} />
          <span>Выйти</span>
        </button>
      </div>
    </aside>
  )
}
