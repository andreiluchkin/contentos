import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { ideasApi, postsApi, pillarsApi, accountsApi, aiApi } from "./api"

// --- Pillars ---

export function usePillars() {
  return useQuery({ queryKey: ["pillars"], queryFn: pillarsApi.list })
}

// --- Accounts ---

export function useAccounts() {
  return useQuery({ queryKey: ["accounts"], queryFn: accountsApi.list })
}

// --- Ideas ---

export function useIdeas(params?: Record<string, string>) {
  return useQuery({
    queryKey: ["ideas", params],
    queryFn: () => ideasApi.list(params),
  })
}

export function useApproveIdea() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => ideasApi.approve(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ideas"] }),
  })
}

export function useRejectIdea() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      ideasApi.reject(id, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ideas"] }),
  })
}

export function useBatchApprove() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (ids: string[]) => ideasApi.batchApprove(ids),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ideas"] }),
  })
}

// --- Posts ---

export function usePosts(params?: Record<string, string | undefined>) {
  return useQuery({
    queryKey: ["posts", params],
    queryFn: () => postsApi.list(params),
  })
}

export function usePost(id: string) {
  return useQuery({
    queryKey: ["post", id],
    queryFn: () => postsApi.get(id),
    enabled: !!id,
  })
}

export function useUpdatePost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      postsApi.update(id, data),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["post", id] })
      qc.invalidateQueries({ queryKey: ["posts"] })
    },
  })
}

export function useUpdatePostStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      postsApi.updateStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["posts"] }),
  })
}

export function useSchedulePost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, scheduledAt }: { id: string; scheduledAt: string }) =>
      postsApi.schedule(id, scheduledAt),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["post", id] })
      qc.invalidateQueries({ queryKey: ["posts"] })
    },
  })
}

export function useDeletePost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => postsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["posts"] }),
  })
}

// --- AI ---

export function useScorePost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (postId: string) => aiApi.score(postId),
    onSuccess: (_, postId) => qc.invalidateQueries({ queryKey: ["post", postId] }),
  })
}

export function useImprovePost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ postId, issues }: { postId: string; issues?: string[] }) =>
      aiApi.improve(postId, issues),
    onSuccess: (_, { postId }) => {
      // Score пересчитается через Celery — polling через 3 сек
      setTimeout(() => qc.invalidateQueries({ queryKey: ["post", postId] }), 3000)
    },
  })
}

export function useGeneratePost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (postId: string) => aiApi.generateForPost(postId),
    onSuccess: (_, postId) => {
      setTimeout(() => qc.invalidateQueries({ queryKey: ["post", postId] }), 2000)
    },
  })
}
