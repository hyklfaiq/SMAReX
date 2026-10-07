/** Shared UI vocabulary: filter options, formatting, small helpers. */

/** Kulliyyah list, matching what IIUM offers. Free text in the DB, curated here. */
export const KULLIYYAH = [
  "Kulliyyah Al-Falah",
  "Kulliyyah of Islamic Revealed Knowledge and Human Sciences",
  "Kulliyyah Mu'allim",
  "Kulliyyah of Languages and Literature",
  "Kulliyyah of Economics and Management",
  "Kulliyyah of Laws",
  "Kulliyyah of Medicine",
  "Kulliyyah of Engineering",
  "Kulliyyah of Architecture, Planning and Urban Development",
  "Kulliyyah of Information Technology",
  "Kulliyyah of Business and Economics",
] as const;

export const CATEGORIES = [
  { slug: "lecture_notes", label: "Lecture Notes" },
  { slug: "past_paper", label: "Past Paper" },
  { slug: "tutorial", label: "Tutorial / Assignment" },
  { slug: "lab_manual", label: "Lab Manual" },
  { slug: "textbook", label: "Textbook / Book" },
  { slug: "research_paper", label: "Research Paper" },
  { slug: "slide_deck", label: "Slide Deck" },
  { slug: "thesis", label: "Thesis / Dissertation" },
  { slug: "checklist", label: "Checklist / Cheat Sheet" },
  { slug: "other", label: "Other" },
] as const;

export const SEMESTERS = [
  { value: "semester_1", label: "Semester 1" },
  { value: "semester_2", label: "Semester 2" },
  { value: "semester_3", label: "Semester 3" },
  { value: "semester_4", label: "Semester 4" },
  { value: "semester_5", label: "Semester 5" },
  { value: "semester_6", label: "Semester 6" },
  { value: "semester_7", label: "Semester 7" },
  { value: "semester_8", label: "Semester 8" },
  { value: "not_applicable", label: "Not applicable" },
] as const;

export const SORT_OPTIONS = [
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "rating", label: "Highest rated" },
  { value: "downloads", label: "Most downloaded" },
  { value: "relevance", label: "Best match" },
] as const;

export const MAX_UPLOAD_MB = 25;

/** Human label for a category slug. */
export function categoryLabel(slug: string): string {
  return CATEGORIES.find((c) => c.slug === slug)?.label ?? slug.replace(/_/g, " ");
}