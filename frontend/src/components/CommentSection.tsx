import { Loader2, MessageSquare, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/EmptyState";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
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
import { useAddComment, useComments, useDeleteComment } from "@/hooks/useResources";
import { errorMessage, formatDate, initials } from "@/lib/utils";

interface Props {
  resourceId: string;
}

export function CommentSection({ resourceId }: Props) {
  const { data, isLoading, isError, error } = useComments(resourceId);
  const addComment = useAddComment(resourceId);
  const removeComment = useDeleteComment(resourceId);

  const [text, setText] = useState("");
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;

    try {
      await addComment.mutateAsync(text.trim());
      setText("");
      toast.success("Comment posted");
    } catch (err) {
      toast.error(errorMessage(err, "Could not post your comment."));
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    try {
      await removeComment.mutateAsync(pendingDelete);
      toast.success("Comment deleted");
    } catch (err) {
      toast.error(errorMessage(err, "Could not delete that comment."));
    } finally {
      setPendingDelete(null);
    }
  }

  return (
    <section aria-labelledby="comments-heading" className="space-y-4">
      <h2 id="comments-heading" className="text-lg font-semibold">
        Comments{data ? ` (${data.length})` : ""}
      </h2>

      <form onSubmit={submit} className="space-y-2">
        <label htmlFor="new-comment" className="sr-only">
          Add a comment
        </label>
        <Textarea
          id="new-comment"
          rows={3}
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Ask a question or leave a note for other students..."
          maxLength={4000}
        />
        <div className="flex justify-end">
          <Button type="submit" size="sm" disabled={!text.trim() || addComment.isPending}>
            {addComment.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
            Post comment
          </Button>
        </div>
      </form>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading comments...</p>
      ) : isError ? (
        <p className="text-sm text-destructive">{errorMessage(error)}</p>
      ) : !data || data.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title="No comments yet"
          description="Start the conversation."
        />
      ) : (
        <ul className="space-y-4">
          {data.map((comment) => (
            <li key={comment.id} className="flex gap-3">
              <Avatar>
                <AvatarFallback>{initials(comment.author?.full_name)}</AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">
                    {comment.author?.full_name ?? "Unknown"}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {formatDate(comment.created_at)}
                  </span>
                </div>
                <p className="whitespace-pre-wrap text-sm text-foreground">{comment.comment}</p>
              </div>
              {comment.can_delete && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Delete comment"
                  onClick={() => setPendingDelete(comment.id)}
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      <AlertDialog open={Boolean(pendingDelete)} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this comment?</AlertDialogTitle>
            <AlertDialogDescription>
              This cannot be undone. The comment will be removed for everyone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void confirmDelete()}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}