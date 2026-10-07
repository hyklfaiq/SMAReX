import { Star } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

interface Props {
  value?: number | null;
  count?: number;
  onChange?: (value: number) => void;
  readOnly?: boolean;
  size?: number;
  className?: string;
}

export function RatingStars({ value, count, onChange, readOnly, size = 16, className }: Props) {
  const [hovered, setHovered] = useState<number | null>(null);
  const shown = hovered ?? value ?? 0;
  const interactive = !readOnly && Boolean(onChange);

  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      <div
        className="flex items-center"
        role={interactive ? "radiogroup" : "img"}
        aria-label={value ? `Rated ${value} out of 5` : "Not yet rated"}
        onMouseLeave={() => setHovered(null)}
      >
        {[1, 2, 3, 4, 5].map((star) => {
          const filled = star <= shown;
          const StarIcon = (
            <Star
              style={{ width: size, height: size }}
              className={cn(
                filled ? "fill-amber-400 text-amber-400" : "text-muted-foreground/40",
              )}
              aria-hidden="true"
            />
          );

          if (!interactive) {
            return (
              <span key={star} className="inline-flex">
                {StarIcon}
              </span>
            );
          }

          return (
            <button
              key={star}
              type="button"
              role="radio"
              aria-checked={value === star}
              aria-label={`Rate ${star} out of 5`}
              onMouseEnter={() => setHovered(star)}
              onClick={() => onChange?.(star)}
              className="rounded p-0.5 transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {StarIcon}
            </button>
          );
        })}
      </div>

      {count !== undefined && (
        <span className="text-xs text-muted-foreground">
          {value ? value.toFixed(1) : "—"} {count === 1 ? "(1 rating)" : `(${count} ratings)`}
        </span>
      )}
    </div>
  );
}