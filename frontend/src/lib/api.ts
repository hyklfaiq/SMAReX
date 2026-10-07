/**
 * Typed client for the SMAReX backend.
 *
 * Injects the current Supabase access token on every request so the API can
 * verify it. No secret ever lives in the browser: the service-role key and
 * the VirusTotal key stay on the server.
 */
import type {
  CommentOut,
  DownloadResponse,
  Page,
  ProfileMe,
  ProfileUpdate,
  RatingSummary,
  ResourceDetail,
  ResourceSummary,
} from "@/types";
import { supabase } from "@/lib/supabase";

const BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

export class ApiError extends Error {
  status: number;
  code: string;
  details?: Record<string, unknown>;

  constructor(
    status: number,
    code: string,
    message: string,
    details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function authHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(await authHeader()),
    ...((init.headers as Record<string, string>) ?? {}),
  };

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      0,
      "network_error",
      "We could not reach the server. Check your connection.",
    );
  }

  if (response.status === 204) return undefined as T;

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const error = (
      payload as {
        error?: { code?: string; message?: string; details?: Record<string, unknown> };
      }
    )?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "unknown_error",
      error?.message ?? "Something went wrong. Please try again.",
      error?.details,
    );
  }

  return payload as T;
}

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}
// ---------------------------------------------------------------------------
// Auth & profile
// ---------------------------------------------------------------------------
export const api = {
  getMe: () => request<ProfileMe>("/auth/me"),

  getAuthConfig: () =>
    request<{
      allowed_email_domains: string[];
      max_upload_mb: number;
    }>("/auth/config"),

  updateProfile: (payload: ProfileUpdate) =>
    request<ProfileMe>("/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  // -- resources ------------------------------------------------------------
  listResources: (params: {
    q?: string;
    kulliyyah?: string;
    subject?: string;
    category?: string;
    semester?: string;
    sort?: string;
    page?: number;
    pageSize?: number;
    mine?: boolean;
  }) => {
    const { pageSize, ...rest } = params;
    return request<Page<ResourceSummary>>(
      `/resources${query({ ...rest, page_size: pageSize })}`,
    );
  },

  getResource: (id: string) => request<ResourceDetail>(`/resources/${id}`),

  /**
   * Uploads metadata + PDF in one multipart request. The backend runs the full
   * pipeline and returns the published resource.
   */
  uploadResource: (formData: FormData) =>
    request<ResourceDetail>("/resources", { method: "POST", body: formData }),

  deleteResource: (id: string) =>
    request<{ message: string }>(`/resources/${id}`, { method: "DELETE" }),

  retrySummary: (id: string) =>
    request<ResourceDetail>(`/resources/${id}/summary/retry`, { method: "POST" }),

  downloadResource: async (id: string): Promise<DownloadResponse> => {
    const result = await request<DownloadResponse>(`/resources/${id}/download`);
    // Opens the signed URL without losing the app state.
    window.open(result.url, "_blank", "noopener,noreferrer");
    return result;
  },

  // -- comments -------------------------------------------------------------
  listComments: (resourceId: string) =>
    request<CommentOut[]>(`/resources/${resourceId}/comments`),

  addComment: (resourceId: string, comment: string) =>
    request<CommentOut>(`/resources/${resourceId}/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ comment }),
    }),

  deleteComment: (commentId: string) =>
    request<{ message: string }>(`/comments/${commentId}`, { method: "DELETE" }),

  // -- ratings --------------------------------------------------------------
  getRating: (resourceId: string) => request<RatingSummary>(`/resources/${resourceId}/rating`),

  rateResource: (resourceId: string, rating: number) =>
    request<RatingSummary>(`/resources/${resourceId}/rating`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating }),
    }),

  // -- saved ----------------------------------------------------------------
  listSaved: () =>
    request<{ id: string; resource_id: string; resource: ResourceSummary | null }[]>("/saved"),

  saveResource: (resourceId: string) =>
    request<{ message: string }>(`/resources/${resourceId}/save`, { method: "POST" }),

  unsaveResource: (resourceId: string) =>
    request<{ message: string }>(`/resources/${resourceId}/save`, { method: "DELETE" }),

  // -- admin ----------------------------------------------------------------
  adminStats: () =>
    request<{
      total_users: number;
      total_resources: number;
      safe_resources: number;
      rejected_uploads: number;
      total_downloads: number;
    }>("/admin/stats"),

  adminUsers: (q?: string) =>
    request<
      {
        id: string;
        full_name: string;
        email: string;
        role: string;
        is_active: boolean;
        kulliyyah: string | null;
        created_at: string | null;
      }[]
    >(`/admin/users${query({ q })}`),

  adminSetUserRole: (id: string, role: string, active?: boolean) =>
    request<{ message: string }>(`/admin/users/${id}/role${query({ role, active })}`, {
      method: "PUT",
    }),

  adminResources: (status?: string) =>
    request<
      {
        id: string;
        title: string;
        owner_name: string | null;
        file_name: string;
        security_status: string;
        publication_status: string;
        download_count: number;
        created_at: string | null;
      }[]
    >(`/admin/resources${query({ status })}`),

  adminDeleteResource: (id: string) =>
    request<{ message: string }>(`/admin/resources/${id}`, { method: "DELETE" }),

  adminSecurityLogs: (status?: string) =>
    request<
      {
        id: string;
        file_name: string;
        file_hash: string;
        scan_status: string;
        details: string | null;
        scan_date: string | null;
        scan_result: Record<string, unknown> | null;
      }[]
    >(`/admin/security-logs${query({ status })}`),
};