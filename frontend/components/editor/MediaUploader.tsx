"use client"

import { useState, useRef, useCallback } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Upload, X, Loader2, Image as ImageIcon, Film, Mic } from "lucide-react"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

interface MediaFile {
  id: string
  filename: string
  media_type: string
  mime_type: string
  size_bytes: number
  presigned_url: string | null
  width: number | null
  height: number | null
}

interface MediaUploaderProps {
  mediaIds: string[]
  onChange: (ids: string[]) => void
  maxFiles?: number
  accept?: string
  label?: string
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function MediaTypeIcon({ type }: { type: string }) {
  if (type === "image") return <ImageIcon size={14} className="text-blue-500" />
  if (type === "video") return <Film size={14} className="text-purple-500" />
  return <Mic size={14} className="text-green-500" />
}

export function MediaUploader({
  mediaIds,
  onChange,
  maxFiles = 9,
  accept = "image/*,video/*,audio/*",
  label = "Медиафайлы",
}: MediaUploaderProps) {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)

  // Загружаем мета по уже прикреплённым ID
  const { data: attachedFiles = [] } = useQuery<MediaFile[]>({
    queryKey: ["media-attached", mediaIds],
    queryFn: async () => {
      if (!mediaIds.length) return []
      const results = await Promise.all(
        mediaIds.map((id) => api.get(`/media/${id}`).then((r) => r.data))
      )
      return results
    },
    enabled: mediaIds.length > 0,
    staleTime: 60_000,
  })

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append("file", file)
      const resp = await api.post("/media/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      return resp.data as MediaFile
    },
    onSuccess: (media) => {
      qc.invalidateQueries({ queryKey: ["media-attached"] })
      onChange([...mediaIds, media.id])
    },
  })

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files) return
      const remaining = maxFiles - mediaIds.length
      Array.from(files)
        .slice(0, remaining)
        .forEach((f) => uploadMutation.mutate(f))
    },
    [mediaIds, maxFiles, uploadMutation]
  )

  function removeMedia(id: string) {
    onChange(mediaIds.filter((mid) => mid !== id))
  }

  const canAdd = mediaIds.length < maxFiles

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-ink-secondary">{label}</span>
        <span className="text-[10px] text-ink-secondary/60">
          {mediaIds.length}/{maxFiles}
        </span>
      </div>

      {/* Превью прикреплённых файлов */}
      {attachedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {attachedFiles.map((file) => (
            <div
              key={file.id}
              className="relative group w-20 h-20 rounded-nav overflow-hidden bg-canvas border border-border"
            >
              {file.media_type === "image" && file.presigned_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={file.presigned_url}
                  alt={file.filename}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="flex flex-col items-center justify-center h-full gap-1 text-ink-secondary">
                  <MediaTypeIcon type={file.media_type} />
                  <span className="text-[9px] text-center px-1 truncate w-full text-center">
                    {file.filename.slice(0, 12)}
                  </span>
                  <span className="text-[9px] opacity-60">{formatSize(file.size_bytes)}</span>
                </div>
              )}
              <button
                onClick={() => removeMedia(file.id)}
                className="absolute top-0.5 right-0.5 w-5 h-5 rounded-full bg-black/60 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X size={10} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Upload zone */}
      {canAdd && (
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setIsDragging(false)
            handleFiles(e.dataTransfer.files)
          }}
          onClick={() => fileRef.current?.click()}
          className={cn(
            "flex items-center justify-center gap-2 py-3 rounded-nav border-2 border-dashed cursor-pointer transition-all text-xs",
            isDragging
              ? "border-accent bg-accent/5 text-accent"
              : "border-border text-ink-secondary hover:border-border-strong hover:bg-canvas"
          )}
        >
          <input
            ref={fileRef}
            type="file"
            multiple
            accept={accept}
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
          {uploadMutation.isPending ? (
            <Loader2 size={14} className="animate-spin text-accent" />
          ) : (
            <Upload size={14} />
          )}
          <span>
            {uploadMutation.isPending
              ? "Загружаем..."
              : "Перетащи или кликни"}
          </span>
        </div>
      )}
    </div>
  )
}
