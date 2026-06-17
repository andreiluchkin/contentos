"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Inbox,
  LayoutList,
  PenLine,
  Calendar,
  Repeat2,
  Mic2,
  BookOpen,
  Settings,
} from "lucide-react"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { href: "/inbox", icon: Inbox, label: "Inbox" },
  { href: "/backlog", icon: LayoutList, label: "Backlog" },
  { href: "/editor", icon: PenLine, label: "Редактор" },
  { href: "/calendar", icon: Calendar, label: "Календарь" },
  { href: "/repurpose", icon: Repeat2, label: "Repurpose" },
  { href: "/brand-voice", icon: Mic2, label: "Brand Voice" },
  { href: "/knowledge-base", icon: BookOpen, label: "База знаний" },
]

export function Sidebar() {
  const pathname = usePathname()

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
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const isActive = pathname === href || pathname.startsWith(href + "/")
          return (
            <Link
              key={href}
              href={href}
              className={cn("sidebar-link", isActive && "sidebar-link-active")}
            >
              <Icon size={16} strokeWidth={1.75} />
              <span>{label}</span>
            </Link>
          )
        })}
      </nav>

      {/* Settings */}
      <div className="px-3 py-3 border-t border-border">
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
      </div>
    </aside>
  )
}
