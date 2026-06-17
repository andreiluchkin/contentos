"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { Inbox, LayoutList, Calendar, Mic2, Plus } from "lucide-react"
import { cn } from "@/lib/utils"

const TABS = [
  { href: "/inbox", icon: Inbox, label: "Inbox" },
  { href: "/backlog", icon: LayoutList, label: "Backlog" },
  { href: "/calendar", icon: Calendar, label: "Календарь" },
  { href: "/brand-voice", icon: Mic2, label: "Voice" },
]

export function MobileNav() {
  const pathname = usePathname()
  const router = useRouter()

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-card border-t border-border z-50">
      <div className="flex items-center justify-around px-2 py-2 relative">
        {TABS.slice(0, 2).map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex flex-col items-center gap-1 px-4 py-1.5 rounded-nav min-w-[56px]",
              pathname === href || pathname.startsWith(href + "/")
                ? "text-accent"
                : "text-ink-secondary"
            )}
          >
            <Icon size={20} strokeWidth={1.75} />
            <span className="text-[10px] font-medium">{label}</span>
          </Link>
        ))}

        {/* FAB — центральная кнопка создания поста */}
        <button
          onClick={() => router.push("/editor")}
          className="flex items-center justify-center w-12 h-12 rounded-full bg-accent text-white shadow-button -translate-y-2 transition-transform active:scale-95"
          aria-label="Создать пост"
        >
          <Plus size={22} strokeWidth={2} />
        </button>

        {TABS.slice(2).map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex flex-col items-center gap-1 px-4 py-1.5 rounded-nav min-w-[56px]",
              pathname === href || pathname.startsWith(href + "/")
                ? "text-accent"
                : "text-ink-secondary"
            )}
          >
            <Icon size={20} strokeWidth={1.75} />
            <span className="text-[10px] font-medium">{label}</span>
          </Link>
        ))}
      </div>
    </nav>
  )
}
