import { SearchX, SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { EmptyState, ErrorState } from "@/components/EmptyState";
import { ResourceCard } from "@/components/ResourceCard";
import { ResourceCardSkeleton } from "@/components/ResourceCardSkeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useDebounced } from "@/hooks/useDebounced";
import { useResources } from "@/hooks/useResources";
import { CATEGORIES, KULLIYYAH, SEMESTERS, SORT_OPTIONS } from "@/lib/constants";
import { errorMessage } from "@/lib/utils";

const ALL = "__all__";

export default function LibraryPage() {
  const [params, setParams] = useSearchParams();
  const mine = params.get("mine") === "true";

  const [search, setSearch] = useState(params.get("q") ?? "");
  const [kulliyyah, setKulliyyah] = useState(params.get("kulliyyah") ?? ALL);
  const [category, setCategory] = useState(params.get("category") ?? ALL);
  const [semester, setSemester] = useState(params.get("semester") ?? ALL);
  const [sort, setSort] = useState(params.get("sort") ?? "newest");
  const [page, setPage] = useState(1);

  const debouncedSearch = useDebounced(search, 350);
  const { data, isLoading, isError, error, refetch } = useResources({
    q: debouncedSearch || undefined,
    kulliyyah: kulliyyah === ALL ? undefined : kulliyyah,
    category: category === ALL ? undefined : category,
    semester: semester === ALL ? undefined : semester,
    sort,
    page,
    mine,
  });

  // Filters live in the URL so a filtered library can be shared or bookmarked.
  useEffect(() => {
    const next = new URLSearchParams();
    if (debouncedSearch) next.set("q", debouncedSearch);
    if (kulliyyah !== ALL) next.set("kulliyyah", kulliyyah);
    if (category !== ALL) next.set("category", category);
    if (semester !== ALL) next.set("semester", semester);
    if (sort !== "newest") next.set("sort", sort);
    if (mine) next.set("mine", "true");
    setParams(next, { replace: true });
  }, [debouncedSearch, kulliyyah, category, semester, sort, mine, setParams]);

  useEffect(() => {
    document.title = mine ? "My uploads \u00b7 SMAReX" : "Library \u00b7 SMAReX";
    setPage(1);
  }, [debouncedSearch, kulliyyah, category, semester, sort, mine]);

  const hasFilters =
    Boolean(debouncedSearch) || kulliyyah !== ALL || category !== ALL || semester !== ALL;

  const clearFilters = () => {
    setSearch("");
    setKulliyyah(ALL);
    setCategory(ALL);
    setSemester(ALL);
    setSort("newest");
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-serif text-2xl sm:text-3xl">
          {mine ? "My uploads" : "Resource library"}
        </h1>
        <p className="text-muted-foreground">
          {mine
            ? "Everything you have shared, including anything still processing."
            : "Every file here has passed a VirusTotal scan and been published."}
        </p>
      </header>

      {/* Search */}
      <div className="relative">
        <SearchX
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by title, subject, course or keyword..."
          className="pl-9"
          aria-label="Search resources"
          type="search"
        />
      </div>

      {/* Filters */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-1.5">
          <Label htmlFor="filter-kulliyyah" className="text-xs text-muted-foreground">
            Kulliyyah
          </Label>
          <Select value={kulliyyah} onValueChange={setKulliyyah}>
            <SelectTrigger id="filter-kulliyyah">
              <SelectValue placeholder="All" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All Kulliyyahs</SelectItem>
              {KULLIYYAH.map((item) => (
                <SelectItem key={item} value={item}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="filter-category" className="text-xs text-muted-foreground">
            Resource type
          </Label>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger id="filter-category">
              <SelectValue placeholder="All" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All types</SelectItem>
              {CATEGORIES.map((item) => (
                <SelectItem key={item.slug} value={item.slug}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="filter-semester" className="text-xs text-muted-foreground">
            Semester
          </Label>
          <Select value={semester} onValueChange={setSemester}>
            <SelectTrigger id="filter-semester">
              <SelectValue placeholder="All" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All semesters</SelectItem>
              {SEMESTERS.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="filter-sort" className="text-xs text-muted-foreground">
            Sort by
          </Label>
          <Select value={sort} onValueChange={setSort}>
            <SelectTrigger id="filter-sort">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <p aria-live="polite">
          {data ? `${data.meta.total} resource${data.meta.total === 1 ? "" : "s"} found` : "Loading..."}
        </p>
        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
            Clear filters
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, key) => (
            <ResourceCardSkeleton key={key} />
          ))}
        </div>
      ) : isError ? (
        <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title={hasFilters ? "No resources match your filters" : "No resources yet"}
          description={
            hasFilters
              ? "Try a broader search or clear the filters."
              : "Be the first to share something with your batch."
          }
          action={
            hasFilters ? (
              <Button size="sm" variant="outline" onClick={clearFilters}>
                Clear filters
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((resource) => (
            <ResourceCard key={resource.id} resource={resource} />
          ))}
        </div>
      )}

      {data && data.meta.total_pages > 1 && (
        <nav aria-label="Pagination" className="flex items-center justify-center gap-3 pt-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!data.meta.has_previous}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {data.meta.page} of {data.meta.total_pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={!data.meta.has_next}
            onClick={() => setPage((current) => current + 1)}
          >
            Next
          </Button>
        </nav>
      )}
    </div>
  );
}