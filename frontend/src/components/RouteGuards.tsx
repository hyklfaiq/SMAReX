/**
 * Route guards.
 *
 * `ProtectedRoute` blocks unauthenticated visitors and remembers where they
 * were going; `AdminRoute` additionally enforces the admin role, so a student
 * cannot reach admin screens even by typing the URL.
 */
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/contexts/AuthContext";

function FullPageLoader({ label }: { label: string }) {
  return (
    <div className="grid min-h-screen place-items-center">
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" aria-hidden="true" />
        <p className="text-sm">{label}</p>
      </div>
    </div>
  );
}

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  const location = useLocation();

  if (loading) return <FullPageLoader label="Restoring your session…" />;
  if (!session) return <Navigate to="/login" state={{ from: location }} replace />;

  return <>{children}</>;
}

export function AdminRoute({ children }: { children: ReactNode }) {
  const { session, profile, loading, isAdmin } = useAuth();

  if (loading) return <FullPageLoader label="Checking your access…" />;
  if (!session) return <Navigate to="/login" replace />;
  if (!profile) return <FullPageLoader label="Loading your profile…" />;
  if (!isAdmin) return <Navigate to="/dashboard" replace />;

  return <>{children}</>;
}