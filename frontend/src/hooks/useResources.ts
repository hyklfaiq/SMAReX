/**
 * Data hooks.
 *
 * Every list and detail view is a thin wrapper over the API client through
 * TanStack Query, so caching, refetching and loading states stay consistent
 * across pages.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ResourceDetail, ResourceSummary } from "@/types";

export interface ResourceFilters {
  q?: string;
  kulliyyah?: string;
  subject?: string;
  category?: string;
  semester?: string;
  sort?: string;
  page?: number;
  mine?: boolean;
}

export function useResources(filters: ResourceFilters) {
  return useQuery({
    queryKey: ["resources", filters],
    queryFn: () => api.listResources({ ...filters, pageSize: 12 }),
  });
}

export function useResource(id: string | undefined) {
  return useQuery({
    queryKey: ["resource", id],
    queryFn: () => api.getResource(id!),
    enabled: Boolean(id),
  });
}

export function useComments(resourceId: string | undefined) {
  return useQuery({
    queryKey: ["comments", resourceId],
    queryFn: () => api.listComments(resourceId!),
    enabled: Boolean(resourceId),
  });
}

export function useAddComment(resourceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (comment: string) => api.addComment(resourceId, comment),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["comments", resourceId] });
    },
  });
}

export function useDeleteComment(resourceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (commentId: string) => api.deleteComment(commentId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["comments", resourceId] });
    },
  });
}

export function useRating(resourceId: string | undefined) {
  return useQuery({
    queryKey: ["rating", resourceId],
    queryFn: () => api.getRating(resourceId!),
    enabled: Boolean(resourceId),
  });
}

export function useRate(resourceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (rating: number) => api.rateResource(resourceId, rating),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["rating", resourceId] });
      void client.invalidateQueries({ queryKey: ["resource", resourceId] });
      void client.invalidateQueries({ queryKey: ["resources"] });
    },
  });
}

export function useSaved() {
  return useQuery({ queryKey: ["saved"], queryFn: () => api.listSaved() });
}

export function useToggleSave(resourceId: string, isSaved: boolean) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => (isSaved ? api.unsaveResource(resourceId) : api.saveResource(resourceId)),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["saved"] });
      void client.invalidateQueries({ queryKey: ["resource", resourceId] });
    },
  });
}

export function useDeleteResource() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteResource(id),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["resources"] });
      void client.invalidateQueries({ queryKey: ["saved"] });
    },
  });
}

export function useRetrySummary() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.retrySummary(id),
    onSuccess: (_data, id) => {
      void client.invalidateQueries({ queryKey: ["resource", id] });
      void client.invalidateQueries({ queryKey: ["resources"] });
    },
  });
}

// -- admin ----------------------------------------------------------------
export const useAdminStats = () =>
  useQuery({ queryKey: ["admin", "stats"], queryFn: () => api.adminStats() });

export const useAdminUsers = (q?: string) =>
  useQuery({ queryKey: ["admin", "users", q], queryFn: () => api.adminUsers(q) });

export const useAdminResources = (status?: string) =>
  useQuery({
    queryKey: ["admin", "resources", status],
    queryFn: () => api.adminResources(status),
  });

export const useAdminSecurityLogs = (status?: string) =>
  useQuery({
    queryKey: ["admin", "security-logs", status],
    queryFn: () => api.adminSecurityLogs(status),
  });

export function useAdminActions() {
  const client = useQueryClient();
  const invalidate = () => {
    void client.invalidateQueries({ queryKey: ["admin"] });
    void client.invalidateQueries({ queryKey: ["resources"] });
  };
  return {
    setUserRole: useMutation({
      mutationFn: ({ id, role, active }: { id: string; role: string; active?: boolean }) =>
        api.adminSetUserRole(id, role, active),
      onSuccess: invalidate,
    }),
    deleteResource: useMutation({
      mutationFn: (id: string) => api.adminDeleteResource(id),
      onSuccess: invalidate,
    }),
  };
}

export type { ResourceDetail, ResourceSummary };