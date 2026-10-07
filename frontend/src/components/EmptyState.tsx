import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

interface Props {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: Props) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-14 text-center", className)}>
      {Icon && (
        <div className="rounded-full bg-muted p-3">
          <Icon className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
        </div>
      )}
      <div className="space-y-1">
        <h3 className="font-semibold">{title}</h3>
        {description && (
          <p className="mx-auto max-w-md text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

interface ErrorProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ title = "Something went wrong", message, onRetry }: ErrorProps) {
  return (
    <div role="alert" className="flex flex-col items-center justify-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-6 py-12 text-center">
      <h3 className="font-semibold text-destructive">{title}</h3>
      <p className="mx-auto max-w-md text-sm text-muted-foreground">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md border border-input px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent"
        >
          Try again
        </button>
      )}
    </div>
  );
}