import { BookOpen, Download, FileText } from "lucide-react";
import { Link } from "react-router-dom";

import { RatingStars } from "@/components/RatingStars";
import { SummaryBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatBytes, formatDate } from "@/lib/utils";
import type { ResourceSummary } from "@/types";

export function ResourceCard({ resource }: { resource: ResourceSummary }) {
  return (
    <Card className="group relative flex h-full flex-col transition-shadow hover:shadow-md">
      <CardHeader className="space-y-2 pb-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{resource.category.replace(/_/g, " ")}</Badge>
          {resource.ai_summary_status === "completed" && <SummaryBadge status="completed" />}
        </div>

        <CardTitle className="text-base leading-snug">
          <Link
            to={`/resources/${resource.id}`}
            className="line-clamp-2 after:absolute after:inset-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {resource.title}
          </Link>
        </CardTitle>

        <p className="line-clamp-2 text-sm text-muted-foreground">
          {resource.description || "No description provided."}
        </p>
      </CardHeader>

      <CardContent className="mt-auto space-y-3 pt-0">
        <dl className="space-y-1 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <BookOpen className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <dd className="truncate">{resource.subject}</dd>
          </div>
          <div className="flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <dd className="truncate">
              {resource.kulliyyah}
              {resource.semester ? ` · ${resource.semester.replace("semester_", "Sem ")}` : ""}
            </dd>
          </div>
        </dl>

        <div className="flex flex-wrap gap-1">
          {resource.tags.slice(0, 3).map((tag) => (
            <Badge key={tag} variant="muted" className="font-normal">
              {tag}
            </Badge>
          ))}
        </div>

        <div className="flex items-center justify-between border-t pt-3">
          <RatingStars value={resource.rating_avg} count={resource.rating_count} readOnly />
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Download className="h-3.5 w-3.5" aria-hidden="true" />
            <span>{resource.download_count}</span>
            <span className="sr-only">downloads</span>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          {formatBytes(resource.file_size)} · {formatDate(resource.created_at)}
          {resource.owner ? ` · ${resource.owner.full_name}` : ""}
        </p>
      </CardContent>
    </Card>
  );
}