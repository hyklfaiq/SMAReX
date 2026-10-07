import { CheckCircle2, FileUp, Loader2, ShieldAlert, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { CATEGORIES, KULLIYYAH, MAX_UPLOAD_MB, SEMESTERS } from "@/lib/constants";
import { cn, errorMessage, formatBytes } from "@/lib/utils";



/** Mirrors the backend pipeline so the user knows what happens next. */
const STEPS = [
  "Validating the PDF",
  "Scanning with VirusTotal",
  "Storing the file safely",
  "Extracting text",
  "Generating the AI summary",
  "Publishing",
] as const;

export default function UploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [subject, setSubject] = useState("");
  const [kulliyyah, setKulliyyah] = useState("");
  const [category, setCategory] = useState("");
  const [semester, setSemester] = useState("");
  const [tags, setTags] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Upload \u00b7 SMAReX";
  }, []);

  const localError = validate();
  const ready = file !== null && localError === null;

  function validate(): string | null {
    if (!file) return null;
    if (!file.name.toLowerCase().endsWith(".pdf")) return "Only PDF files can be uploaded.";
    if (file.type && file.type !== "application/pdf" && file.type !== "application/x-pdf") {
      return "That file is not a PDF.";
    }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      return `Files must be smaller than ${MAX_UPLOAD_MB} MB.`;
    }
    return null;
  }

  function pickFile(selected: File | null) {
    setError(null);
    if (!selected) {
      setFile(null);
      return;
    }
    setFile(selected);
    // Pre-fill the title from the filename so students type less.
    if (!title) {
      setTitle(selected.name.replace(/\.pdf$/i, "").replace(/[_-]+/g, " ").slice(0, 300));
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file || !ready) return;

    setBusy(true);
    setError(null);

    const form = new FormData();
    form.append("file", file);
    form.append("title", title.trim());
    form.append("description", description.trim());
    form.append("subject", subject.trim());
    form.append("kulliyyah", kulliyyah);
    form.append("category", category);
    if (semester) form.append("semester", semester);
    if (tags.trim()) form.append("tags", tags.trim());

    try {
      const result = await api.uploadResource(form);

      toast.success("Resource published");
      if (result.ai_summary_status === "completed") {
        toast.message("An AI summary was generated automatically.");
      } else if (result.ai_summary_status === "skipped") {
        toast.message("No text could be extracted, so no summary was generated.");
      } else if (result.ai_summary_status === "failed") {
        toast.message("The file was published, but the summary could not be generated.");
      }
      navigate(`/resources/${result.id}`);
    } catch (err) {
      // Rejections carry a specific, user-safe reason from the pipeline.
      if (err instanceof ApiError && err.code === "malicious_file_rejected") {
        toast.error("File rejected", {
          description: "It was not stored and no other user can access it.",
        });
      }
      setError(errorMessage(err, "The upload failed. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="font-serif text-2xl sm:text-3xl">Share a resource</h1>
        <p className="text-muted-foreground">
          Your PDF is scanned for malware before anything is stored. If it fails the scan it
          is never published.
        </p>
      </header>

      {/* Pipeline explainer */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">What happens when you upload</CardTitle>
          <CardDescription>Each step runs in order.</CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
            {STEPS.map((step, index) => (
              <li key={step} className="flex items-center gap-2">
                <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-secondary text-[11px] font-semibold text-secondary-foreground">
                  {index + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <form onSubmit={handleSubmit} className="space-y-6" noValidate>
        {/* File */}
        <div className="space-y-2">
          <Label htmlFor="file">PDF file</Label>
          <label
            htmlFor="file"
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors",
              "hover:bg-accent/50 focus-within:ring-2 focus-within:ring-ring",
              localError && file ? "border-destructive" : "border-input",
            )}
          >
            <FileUp className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
            {file ? (
              <>
                <span className="font-medium">{file.name}</span>
                <span className="text-xs text-muted-foreground">{formatBytes(file.size)}</span>
              </>
            ) : (
              <>
                <span className="font-medium">Choose a PDF</span>
                <span className="text-xs text-muted-foreground">
                  Maximum {MAX_UPLOAD_MB} MB
                </span>
              </>
            )}
          </label>
          <input
            ref={inputRef}
            id="file"
            type="file"
            accept="application/pdf,.pdf"
            className="sr-only"
            onChange={(event) => pickFile(event.target.files?.[0] ?? null)}
          />
          {localError && (
            <p role="alert" className="flex items-center gap-1.5 text-sm text-destructive">
              <XCircle className="h-4 w-4" aria-hidden="true" />
              {localError}
            </p>
          )}
        </div>

        {/* Metadata */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              required
              minLength={3}
              maxLength={300}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Week 3: Sorting Algorithms"
            />
          </div>

          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              rows={3}
              maxLength={8000}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What is covered in this resource?"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="subject">Subject / course</Label>
            <Input
              id="subject"
              required
              minLength={2}
              maxLength={200}
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              placeholder="CS 2410"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="kulliyyah">Kulliyyah</Label>
            <Select value={kulliyyah} onValueChange={setKulliyyah}>
              <SelectTrigger id="kulliyyah">
                <SelectValue placeholder="Select a Kulliyyah" />
              </SelectTrigger>
              <SelectContent>
                {KULLIYYAH.map((item) => (
                  <SelectItem key={item} value={item}>
                    {item}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="category">Resource type</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger id="category">
                <SelectValue placeholder="Select a type" />
              </SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((item) => (
                  <SelectItem key={item.slug} value={item.slug}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="semester">Semester (optional)</Label>
            <Select value={semester} onValueChange={setSemester}>
              <SelectTrigger id="semester">
                <SelectValue placeholder="Not applicable" />
              </SelectTrigger>
              <SelectContent>
                {SEMESTERS.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="tags">Tags (comma separated)</Label>
            <Input
              id="tags"
              value={tags}
              onChange={(event) => setTags(event.target.value)}
              placeholder="algorithms, sorting, week3"
            />
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm"
          >
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
            <div>
              <p className="font-medium text-destructive">Upload not completed</p>
              <p className="text-muted-foreground">{error}</p>
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="submit"
            disabled={!ready || busy || !title.trim() || !subject.trim() || !kulliyyah || !category}
          >
            {busy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                Scanning and publishing...
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                Upload and publish
              </>
            )}
          </Button>
          <p className="text-xs text-muted-foreground">
            Uploads can take up to a minute while VirusTotal analyses the file.
          </p>
        </div>
      </form>
    </div>
  );
}