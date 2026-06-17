import { cn, scoreColor, scoreBg } from "@/lib/utils"

interface Props {
  score: number | null
  size?: "sm" | "md"
}

export function ScoreBadge({ score, size = "md" }: Props) {
  if (score === null) return null

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-badge font-semibold tabular-nums",
        scoreColor(score),
        scoreBg(score),
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm"
      )}
    >
      {score}
    </span>
  )
}
