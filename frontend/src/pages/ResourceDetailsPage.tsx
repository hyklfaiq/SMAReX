import {
  ArrowLeft,
  Bookmark,
  BookmarkCheck,
  Download,
  FileText,
  Loader2,
  RefreshCw,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { CommentSection } from "@/components/CommentSection";
import { ErrorState } from "@/components/EmptyState";
import { RatingStars } from "@/components/RatingStars";
import { SecurityBadge, SummaryBadge } from "@/components/StatusBadge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import {
  useDeleteResource,
  useRating,
  useRate,
  useResource,
  useRetrySummary,
  useSaved,
  useToggleSave,
} from "@/hooks/useResources";
import { categoryLabel } from "@/lib/constants";
import { errorMessage, formatBytes, formatDate } from "@/lib/utils";

export default function ResourceDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();

  const { data: resource, isLoading, isError, error, refetch } = useResource(id);
  const { data: rating } = useRating(id);
  const { data: saved } = useSaved();
  const toggleSave = useToggleSave(id ?? "", false);
  const rate = useRate(id ?? "");
  const remove = useDeleteResource();
  const retry = useRetrySummary();

  const [confirmDelete, setConfirmDelete] = useState(false);

  const isSaved = Boolean(saved?.some((entry) => entry.resource_id === id));
  const canModify = Boolean(resource && (resource.is_owner || isAdmin));

  useEffect(() => {
    if (resource) document.title = `${resource.title} \u00b7 SMAReX`;
  }, [resource]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (isError || !resource) {
    return (
      <ErrorState
        title="Resource unavailable"
        message={errorMessage(error, "That resource could not be found.")}
        onRetry={() => void refetch()}
      />
    );
  }

  async function handleDownload() {
    try {
      await api.downloadResource(resource!.id);
      toast.success("Download started");
      void refetch();
    } catch (err) {
      toast.error(errorMessage(err, "The download could not start."));
    }
  }

  async function handleSave() {
    try {
      await toggleSave.mutateAsync();
      toast.success(isSaved ? "Removed from saved" : "Saved to your library");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function handleRate(value: number) {
    try {
      await rate.mutateAsync(value);
      toast.success("Thanks for rating");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function handleRetry() {
    try {
      await retry.mutateAsync(resource!.id);
      toast.success("Summary regenerated");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function handleDelete() {
    try {
      await remove.mutateAsync(resource!.id);
      toast.success("Resource deleted");
      navigate("/library", { replace: true });
    } catch (err) {
      toast.error(errorMessage(err));
      setConfirmDelete(false);
    }
  }

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-3">
        <Link to="/library">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to library
        </Link>
      </Button>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {/* Header */}
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{categoryLabel(resource.category)}</Badge>
              <SecurityBadge status={resource.security_status} />
              <SummaryBadge status={resource.ai_summary_status} />
            </div>

            <h1 className="font-serif text-2xl leading-tight sm:text-3xl">{resource.title}</h1>

            <p className="text-sm text-muted-foreground">
              {resource.subject} \u00b7 {resource.kulliyyah}
              {resource.semester ? ` \u00b7 ${resource.semester.replace("semester_", "Semester ")}` : ""}
            </p>

            {resource.description && (
              <p className="whitespace-pre-wrap text-muted-foreground">{resource.description}</p>
            )}

            {resource.tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {resource.tags.map((tag) => (
                  <Badge key={tag} variant="muted" className="font-normal">
                    {tag}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* AI summary */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles className="h-4 w-4 text-amber-500" aria-hidden="true" />
                AI summary
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {resource.ai_summary ? (
                <p className="whitespace-pre-wrap text-sm leading-relaxed">
                  {resource.ai_summary}
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No summary was generated for this document.
                </p>
              )}

              {resource.ai_summary_status === "failed" && resource.ai_summary_error && (
                <p className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
                  {resource.ai_summary_error}
                  {canModify && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="ml-2 h-auto p-0 text-xs"
                      onClick={() => void handleRetry()}
                      disabled={retry.isPending}
                    >
                      {retry.isPending ? (
                        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
                      ) : (
                        <RefreshCw className="h-3 w-3" aria-hidden="true" />
                      )}
                      Try again
                    </Button>
                  )}
                </p>
              )}

              {resource.ai_keywords.length > 0 && (
                <>
                  <Separator />
                  <div>
                    <p className="mb-2 text-xs font-medium text-muted-foreground">Keywords</p>
                    <div className="flex flex-wrap gap-1.5">
                      {resource.ai_keywords.map((keyword) => (
                        <Badge key={keyword} variant="outline" className="font-normal">
                          {keyword}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {resource.ai_model && (
                <p className="text-xs text-muted-foreground">
                  Generated with <code className="text-[11px]">{resource.ai_model}</code>
                </p>
              )}
            </CardContent>
          </Card>

          <Separator />

          {/* Comments */}
          <CommentSection resourceId={resource.id} />
        </div>

        {/* Sidebar */}
        <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
          <Card>
            <CardContent className="space-y-4 p-5">
              <div className="flex items-center gap-2 text-sm">
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="truncate" title={resource.file_name}>
                  {resource.file_name}
                </span>
              </div>

              <dl className="space-y-1 text-xs text-muted-foreground">
                <div className="flex justify-between">
                  <dt>Size</dt>
                  <dd>{formatBytes(resource.file_size)}</dd>
                </div>
                {resource.page_count && (
                  <div className="flex justify-between">
                    <dt>Pages</dt>
                    <dd>{resource.page_count}</dd>
                  </div>
                )}
                <div className="flex justify-between">
                  <dt>Downloads</dt>
                  <dd>{resource.download_count}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Uploaded</dt>
                  <dd>{formatDate(resource.created_at)}</dd>
                </div>
              </dl>

              <div className="space-y-2">
                <Button
                  className="w-full"
                  onClick={() => void handleDownload()}
                  disabled={
                    resource.publication_status !== "published" ||
                    resource.security_status !== "safe"
                  }
                >
                  <Download className="h-4 w-4" aria-hidden="true" />
                  Download
                </Button>

                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => void handleSave()}
                  disabled={toggleSave.isPending}
                >
                  {isSaved ? (
                    <BookmarkCheck className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Bookmark className="h-4 w-4" aria-hidden="true" />
                  )}
                  {isSaved ? "Saved" : "Save"}
                </Button>
              </div>

              {resource.publication_status !== "published" && (
                <p className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
                  This resource is not published yet, so it cannot be downloaded.
                </p>
              )}

              {canModify && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full text-destructive hover:bg-destructive/10 hover:text-destructive"
                  onClick={() => setConfirmDelete(true)}
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                  Delete resource
                </Button>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Rate this resource</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <RatingStars
                value={rating?.my_rating ?? null}
                count={rating?.count}
                onChange={(value) => void handleRate(value)}
              />
              {rating?.average ? (
                <p className="text-xs text-muted-foreground">
                  Average {rating.average.toFixed(1)} out of 5
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">Be the first to rate this.</p>
              )}
            </CardContent>
          </Card>

          {resource.owner && (
            <Card>
              <CardContent className="p-5 text-sm">
                <p className="font-medium">{resource.owner.full_name}</p>
                {resource.owner.programme && (
                  <p className="text-xs text-muted-foreground">{resource.owner.programme}</p>
                )}
                {resource.owner.kulliyyah && (
                  <p className="text-xs text-muted-foreground">{resource.owner.kulliyyah}</p>
                )}
              </CardContent>
            </Card>
          )}
        </aside>
      </div>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this resource?</AlertDialogTitle>
            <AlertDialogDescription>
              The stored PDF and its metadata will be removed permanently. This cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => void handleDelete()}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete permanently
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}