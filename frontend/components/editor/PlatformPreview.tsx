import type { Platform } from "@/lib/types"

interface Props {
  body: string
  platform: Platform
  handle?: string
}

export function PlatformPreview({ body, platform, handle }: Props) {
  if (platform === "telegram") {
    return (
      <div className="bg-[#efeff4] rounded-card p-4 h-full overflow-y-auto">
        <div className="max-w-sm mx-auto">
          <div className="bg-white rounded-[20px] rounded-tl-[4px] p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-full bg-[#0088cc] flex items-center justify-center text-white text-xs font-bold">
                C
              </div>
              <span className="text-xs font-semibold text-[#19171c]">
                {handle ?? "ContentOS"}
              </span>
            </div>
            <p className="text-sm text-[#19171c] whitespace-pre-wrap leading-relaxed">
              {body || <span className="text-gray-300">Текст поста появится здесь...</span>}
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (platform === "linkedin") {
    return (
      <div className="bg-[#f3f2ef] rounded-card p-4 h-full overflow-y-auto">
        <div className="max-w-sm mx-auto bg-white rounded-lg p-5 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-[#0077b5] flex items-center justify-center text-white text-sm font-bold">
              A
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900">{handle ?? "Author"}</p>
              <p className="text-xs text-gray-500">Content Creator</p>
            </div>
          </div>
          <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
            {body || <span className="text-gray-300">Текст поста появится здесь...</span>}
          </p>
        </div>
      </div>
    )
  }

  if (platform === "x") {
    return (
      <div className="bg-black rounded-card p-4 h-full overflow-y-auto">
        <div className="max-w-sm mx-auto bg-black border border-gray-800 rounded-2xl p-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-full bg-gray-700 shrink-0" />
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-bold text-white">{handle ?? "Author"}</span>
                <span className="text-xs text-gray-500">@handle</span>
              </div>
              <p className="text-sm text-white whitespace-pre-wrap leading-relaxed">
                {body?.slice(0, 280) || <span className="text-gray-600">Текст поста...</span>}
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Generic preview для остальных платформ
  return (
    <div className="bg-canvas rounded-card p-6 h-full overflow-y-auto">
      <div className="bg-white rounded-card p-5 shadow-card">
        <p className="text-xs text-ink-secondary mb-3 uppercase tracking-wide font-medium">
          {platform}
        </p>
        <p className="text-sm text-ink whitespace-pre-wrap leading-relaxed">
          {body || <span className="text-gray-300">Текст поста появится здесь...</span>}
        </p>
      </div>
    </div>
  )
}
