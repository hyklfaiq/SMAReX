/**
 * Supabase client used for authentication ONLY.
 *
 * The anon key is designed to be public, but the browser must never talk to
 * the database directly: all data access goes through the FastAPI backend,
 * which enforces authorisation and uses the service-role key server-side.
 */
import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const isSupabaseConfigured = Boolean(url && anonKey);

if (!isSupabaseConfigured) {
  console.warn(
    "[SMAReX] Supabase is not configured. Copy .env.example to .env and fill in " +
      "VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.",
  );
}

export const supabase = createClient(
  url ?? "http://localhost:54321",
  anonKey ?? "public-anon-key-placeholder",
  {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      storageKey: "smarex.auth",
    },
  },
);

/** Email domains accepted by this deployment, shown on the login screen. */
export const ALLOWED_DOMAINS = ["live.iium.edu.my"];
