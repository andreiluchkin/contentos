import { cn, STATUS_LABELS, STATUS_COLORS } from "@/lib/utils"
import type { PipelineStatus } from "@/lib/types"

interface Props {
  status: PipelineStatus
  className?: string
}

export function StatusBadge({ status, className }: Props) {
  return (
    <span className={cn("status-badge", STATUS_COLORS[status], className)}>
      {STATUS_LABELS[status]}
    </span>
  )
}
