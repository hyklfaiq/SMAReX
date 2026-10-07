export type UserRole = "student" | "admin";

export type SecurityStatus =
  | "pending"
  | "scanning"
  | "safe"
  | "malicious"
  | "suspicious"
  | "error";

export type PublicationStatus =
  | "draft"
  | "processing"
  | "published"
  | "rejected"
  | "deleted";

export type AiSummaryStatus =
  | "pending"
  | "processing"
  | "completed"
  | "skipped"
  | "failed";

export interface ProfilePublic {
  id: string;
  full_name: string;
  kulliyyah: string | null;
  programme: string | null;
  avatar_url: string | null;
}

export interface ProfileMe extends ProfilePublic {
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string | null;
}

export interface ProfileUpdate {
  full_name?: string;
  /** `null` clears the field; the backend treats it as "not specified". */
  kulliyyah?: string | null;
  programme?: string | null;
}

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface Page<T> {
  items: T[];
  meta: PageMeta;
}

export interface ResourceSummary {
  id: string;
  title: string;
  description: string;
  subject: string;
  kulliyyah: string;
  category: string;
  semester: string | null;
  tags: string[];
  file_size: number;
  security_status: SecurityStatus;
  publication_status: PublicationStatus;
  ai_summary_status: AiSummaryStatus;
  download_count: number;
  view_count: number;
  rating_avg: number;
  rating_count: number;
  created_at: string | null;
  updated_at: string | null;
  owner: ProfilePublic | null;
}

export interface ResourceDetail extends ResourceSummary {
  file_name: string;
  file_type: string;
  page_count: number | null;
  ai_summary: string | null;
  ai_keywords: string[];
  ai_model: string | null;
  ai_summary_error: string | null;
  owner_id: string;
  is_owner: boolean;
}

export interface DownloadResponse {
  url: string;
  file_name: string;
  expires_in: number;
}

export interface CommentOut {
  id: string;
  resource_id: string;
  comment: string;
  is_hidden: boolean;
  created_at: string | null;
  updated_at: string | null;
  author: ProfilePublic | null;
  can_delete: boolean;
}

export interface RatingSummary {
  resource_id: string;
  average: number;
  count: number;
  my_rating: number | null;
}

export interface SavedEntry {
  id: string;
  resource_id: string;
  resource: ResourceSummary | null;
}