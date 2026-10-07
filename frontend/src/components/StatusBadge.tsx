import { Badge } from "@/components/ui/badge";
import type { AiSummaryStatus, SecurityStatus } from "@/types";

const SECURITY: Record<SecurityStatus, { label: string; variant: "success" | "warning" | "destructive" | "muted" }> = {
  safe: { label: "Scanned", variant: "success" },
  scanning: { label: "Scanning", variant: "warning" },
  pending: { label: "Pending", variant: "muted" },
  malicious: { label: "Blocked", variant: "destructive" },
  suspicious: { label: "Held for review", variant: "warning" },
  error: { label: "Scan error", variant: "destructive" },
};

export function SecurityBadge({ status }: { status: SecurityStatus }) {
  const config = SECURITY[status] ?? SECURITY.pending;
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

const SUMMARY: Record<AiSummaryStatus, { label: string; variant: "success" | "warning" | "destructive" | "muted" }> = {
  completed: { label: "AI summary", variant: "success" },
  processing: { label: "Summarising", variant: "warning" },
  pending: { label: "Summary pending", variant: "muted" },
  skipped: { label: "No summary", variant: "muted" },
  failed: { label: "Summary unavailable", variant: "destructive" },
};

export function SummaryBadge({ status }: { status: AiSummaryStatus }) {
  const config = SUMMARY[status] ?? SUMMARY.pending;
  return <Badge variant={config.variant}>{config.label}</Badge>;
}