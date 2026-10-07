import { BookmarkX } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorState } from "@/components/EmptyState";
import { ResourceCard } from "@/components/ResourceCard";
import { ResourceCardSkeleton } from "@/components/ResourceCardSkeleton";
import { Button } from "@/components/ui/button";
import { useSaved } from "@/hooks/useResources";
import { errorMessage } from "@/lib/utils";

export default function SavedPage() {
  const { data, isLoading, isError, error, refetch } = useSaved();

  useEffect(() => {
    document.title = "Saved \u00b7 SMAReX";
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-serif text-2xl sm:text-3xl">Saved resources</h1>
        <p className="text-muted-foreground">Bookmarks are private to your account.</p>
      </header>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, key) => (
            <ResourceCardSkeleton key={key} />
          ))}
        </div>
      ) : isError ? (
        <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          icon={BookmarkX}
          title="Nothing saved yet"
          description="Save a resource from its page to find it here later."
          action={
            <Button asChild size="sm">
              <Link to="/library">Browse the library</Link>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((entry) =>
            entry.resource ? (
              <ResourceCard key={entry.id} resource={entry.resource} />
            ) : null,
          )}
        </div>
      )}
    </div>
  );
}