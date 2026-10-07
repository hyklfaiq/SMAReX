/**
 * Authentication context.
 *
 * Supabase owns the session; the backend owns authorisation. On sign-in the
 * browser calls /auth/me to load the profile and role, and the IIUM domain
 * restriction is enforced server-side on every request.
 */
import type { Session, User } from "@supabase/supabase-js";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiError, api } from "@/lib/api";
import { isSupabaseConfigured, supabase } from "@/lib/supabase";
import type { ProfileMe } from "@/types";

interface AuthValue {
  session: Session | null;
  user: User | null;
  profile: ProfileMe | null;
  loading: boolean;
  isAdmin: boolean;
  configured: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (
    email: string,
    password: string,
    fullName: string,
  ) => Promise<{ needsConfirmation: boolean }>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<ProfileMe | null>(null);
  const [loading, setLoading] = useState(true);

  const loadProfile = useCallback(async (current: Session | null) => {
    if (!current) {
      setProfile(null);
      return;
    }
    try {
      setProfile(await api.getMe());
    } catch (error) {
      // A token the backend refuses (expired, or a non-IIUM domain) must not
      // leave a half-authenticated session behind.
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        await supabase.auth.signOut();
        setProfile(null);
      } else {
        console.error("Could not load profile", error);
      }
    }
  }, []);

  useEffect(() => {
    if (!isSupabaseConfigured) {
      setLoading(false);
      return;
    }

    supabase.auth.getSession().then(async ({ data }) => {
      setSession(data.session);
      await loadProfile(data.session);
      setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
      void loadProfile(next);
    });

    return () => listener.subscription.unsubscribe();
  }, [loadProfile]);

  const signIn = useCallback(async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      // Never reveal which half of the credential was wrong.
      throw new Error(
        error.message.toLowerCase().includes("invalid")
          ? "Incorrect email or password."
          : error.message,
      );
    }
  }, []);

  const signUp = useCallback(
    async (email: string, password: string, fullName: string) => {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          // The database trigger (0006) reads full_name from this metadata to
          // build the profiles row, and rejects any non-IIUM Live domain.
          data: { full_name: fullName },
        },
      });
      if (error) {
        throw new Error(error.message);
      }
      // With email confirmation enabled Supabase returns no session yet; the
      // account only becomes usable after the confirmation link is followed.
      return { needsConfirmation: !data.session };
    },
    [],
  );

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    setProfile(null);
    setSession(null);
  }, []);

  const refreshProfile = useCallback(async () => {
    await loadProfile(session);
  }, [loadProfile, session]);

  const value = useMemo<AuthValue>(
    () => ({
      session,
      user: session?.user ?? null,
      profile,
      loading,
      isAdmin: profile?.role === "admin",
      configured: isSupabaseConfigured,
      signIn,
      signUp,
      signOut,
      refreshProfile,
    }),
    [session, profile, loading, signIn, signUp, signOut, refreshProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}