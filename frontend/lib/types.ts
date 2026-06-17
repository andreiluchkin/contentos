export type PipelineStatus =
  | "inbox"
  | "idea_approved"
  | "draft"
  | "review"
  | "ready"
  | "scheduled"
  | "published"
  | "error"

export type Platform = "telegram" | "instagram" | "tiktok" | "youtube" | "linkedin" | "x"

export type ContentType =
  | "case"
  | "breakdown"
  | "how_to"
  | "opinion"
  | "roundup"
  | "story"
  | "observation"
  | "mistake"
  | "lesson"
  | "launch"

export interface ContentPillar {
  id: string
  name: string
  slug: string
  color: string
  description: string | null
  is_active: boolean
  sort_order: number
  created_at: string
}

export interface SocialAccount {
  id: string
  platform: Platform
  handle: string
  display_name: string
  avatar_url: string | null
  is_active: boolean
  token_expires_at: string | null
  optimal_posting_times: Record<string, string>
  created_at: string
}

export interface Idea {
  id: string
  title: string
  context: string | null
  source_url: string | null
  source_name: string | null
  suggested_platform: Platform | null
  suggested_content_type: ContentType | null
  relevance_score: number | null
  pillar_id: string | null
  status: PipelineStatus
  rejected_at: string | null
  rejection_reason: string | null
  approved_at: string | null
  created_at: string
  updated_at: string
}

export interface Post {
  id: string
  idea_id: string | null
  account_id: string
  pillar_id: string | null
  platform: Platform
  content_type: ContentType
  body: string
  hashtags: string[]
  media_ids: string[]
  platform_meta: Record<string, unknown>
  status: PipelineStatus
  content_score: number | null
  score_hook: number | null
  score_structure: number | null
  score_readability: number | null
  score_cta: number | null
  score_platform_fit: number | null
  score_issues: string[]
  score_calculated_at: string | null
  scheduled_at: string | null
  published_at: string | null
  external_post_id: string | null
  publish_error: string | null
  publish_attempts: number
  author_notes: string | null
  created_at: string
  updated_at: string
}

export interface ContentScore {
  content_score: number
  score_hook: number
  score_structure: number
  score_readability: number
  score_cta: number
  score_platform_fit: number
  score_issues: string[]
}
