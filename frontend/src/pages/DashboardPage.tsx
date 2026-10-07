import { FileText, Plus, Search, Upload, X } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ResourceCard } from "@/components/ResourceCard";
import { ResourceCardSkeleton } from "@/components/ResourceCardSkeleton";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { useResources } from "@/hooks/useResources";
import { errorMessage } from "@/lib/utils";

export default function DashboardPage() {
  const { profile } = useAuth();
  const recent = useResources({ sort: "newest", page: 1 });
  const mine = useResources({ mine: true, sort: "newest", page: 1 });

  useEffect(() => {
    document.title = "Dashboard \u00b7 SMAReX";
  }, []);

  return (
    <div className="space-y-10">
      <section className="rounded-lg border bg-card p-6 sm:p-8">
        <h1 className="font-serif text-2xl sm:text-3xl">
          Welcome back, {profile?.full_name?.split(" ")[0] ?? "there"}.
        </h1>
        <p className="mt-2 text-muted-foreground">
          Find notes, past papers and references shared by other IIUM students.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          <Button asChild>
            <Link to="/library">
              <Search className="h-4 w-4" aria-hidden="true" />
              Browse the library
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/upload">
              <Upload className="h-4 w-4" aria-hidden="true" />
              Share a resource
            </Link>
          </Button>
        </div>
      </section>

      {/* My uploads */}
      <section aria-labelledby="mine-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 id="mine-heading" className="text-lg font-semibold">
            My uploads
          </h2>
          <Button asChild variant="ghost" size="sm">
            <Link to="/library?mine=true">
              View all
              <Plus className="h-4 w-4" aria-hidden="true" />
            </Link>
          </Button>
        </div>

        {mine.isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((key) => (
              <ResourceCardSkeleton key={key} />
            ))}
          </div>
        ) : mine.isError ? (
          <EmptyState title="Could not load your uploads" description={errorMessage(mine.error)} />
        ) : mine.data && mine.data.items.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {mine.data.items.map((resource) => (
              <ResourceCard key={resource.id} resource={resource} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={FileText}
            title="You have not uploaded anything yet"
            description="Share lecture notes or past papers so others can benefit."
            action={
              <Button asChild size="sm">
                <Link to="/upload">Upload your first resource</Link>
              </Button>
            }
          />
        )}
      </section>

      {/* Latest from the community */}
      <section aria-labelledby="recent-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 id="recent-heading" className="text-lg font-semibold">
            Recently added
          </h2>
          <Button asChild variant="ghost" size="sm">
            <Link to="/library">
              See all
              <Search className="h-4 w-4" aria-hidden="true" />
            </Link>
          </Button>
        </div>

        {recent.isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2, 3, 4, 5].map((key) => (
              <ResourceCardSkeleton key={key} />
            ))}
          </div>
        ) : recent.data && recent.data.items.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recent.data.items.slice(0, 6).map((resource) => (
              <ResourceCard key={resource.id} resource={resource} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={X}
            title="Nothing published yet"
            description="Be the first to share a resource with your batch."
          />
        )}
      </section>
    </div>
  );
}