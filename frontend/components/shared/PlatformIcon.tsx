import { cn } from "@/lib/utils"
import type { Platform } from "@/lib/types"

const ICONS: Record<Platform, string> = {
  telegram: "✈",
  instagram: "📷",
  tiktok: "♪",
  youtube: "▶",
  linkedin: "in",
  x: "𝕏",
}

const BG: Record<Platform, string> = {
  telegram: "bg-[#0088cc]",
  instagram: "bg-gradient-to-br from-[#f9ce34] via-[#ee2a7b] to-[#6228d7]",
  tiktok: "bg-black",
  youtube: "bg-[#ff0000]",
  linkedin: "bg-[#0077b5]",
  x: "bg-black",
}

interface Props {
  platform: Platform
  size?: "sm" | "md"
  className?: string
}

export function PlatformIcon({ platform, size = "md", className }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-full text-white font-bold shrink-0",
        BG[platform],
        size === "sm" ? "w-5 h-5 text-[9px]" : "w-6 h-6 text-[11px]",
        className
      )}
      title={platform}
    >
      {ICONS[platform]}
    </span>
  )
}
