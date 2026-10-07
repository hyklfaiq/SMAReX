import { Loader2, ShieldCheck } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/AuthContext";
import { ALLOWED_DOMAINS } from "@/lib/supabase";
import { errorMessage } from "@/lib/utils";

export default function LoginPage({ initialMode = "signin" }: { initialMode?: "signin" | "signup" }) {
  const { signIn, signUp, session, loading, configured } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [view, setView] = useState<"signin" | "signup">(initialMode);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const from =
    (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? "/dashboard";

  useEffect(() => {
    document.title = `${view === "signup" ? "Create account" : "Sign in"} \u00b7 SMAReX`;
  }, [view]);

  const switchView = (next: "signin" | "signup") => {
    setView(next);
    setError(null);
    setNotice(null);
  };

  if (!loading && session) return <Navigate to={from} replace />;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setNotice(null);

    const trimmedEmail = email.trim().toLowerCase();
    const domain = trimmedEmail.split("@")[1] ?? "";
    if (!ALLOWED_DOMAINS.includes(domain)) {
      setError(`SMAReX is limited to @${ALLOWED_DOMAINS[0]} accounts.`);
      return;
    }

    setBusy(true);
    try {
      if (view === "signup") {
        if (!fullName.trim()) throw new Error("Enter your full name.");
        if (password.length < 8) throw new Error("Password must be at least 8 characters.");
        if (password !== confirmPassword) throw new Error("Passwords do not match.");

        const { needsConfirmation } = await signUp(trimmedEmail, password, fullName.trim());
        if (needsConfirmation) {
          setNotice(
            `We sent a confirmation link to ${trimmedEmail}. Confirm your email, then sign in.`,
          );
          setView("signin");
          setPassword("");
          setConfirmPassword("");
        } else {
          navigate(from, { replace: true });
        }
      } else {
        await signIn(trimmedEmail, password);
        navigate(from, { replace: true });
      }
    } catch (err) {
      setError(
        errorMessage(
          err,
          view === "signup" ? "We could not create your account." : "We could not sign you in.",
        ),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-primary p-10 text-primary-foreground lg:flex">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary-foreground/15 font-bold">
            S
          </span>
          SMAReX
        </div>

        <div className="space-y-6">
          <h2 className="font-serif text-4xl leading-tight">
            Share knowledge.
            <br />
            Skip the noise.
          </h2>
          <p className="max-w-md text-primary-foreground/80">
            An academic resource exchange for IIUM students. Every PDF is scanned for
            malware and summarised automatically, so you know what you are downloading
            before you download it.
          </p>
          <ul className="space-y-2 text-sm text-primary-foreground/70">
            <li>VirusTotal-verified uploads</li>
            <li>AI-generated summaries and keywords</li>
            <li>Search by course, Kulliyyah and keyword</li>
          </ul>
        </div>

        <p className="text-xs text-primary-foreground/60">Restricted to IIUM Live accounts.</p>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-6">
          <div className="flex items-center gap-2 lg:hidden">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
              S
            </span>
            <span className="font-semibold">SMAReX</span>
          </div>

          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {view === "signup" ? "Create account" : "Sign in"}
            </h1>
            <p className="text-sm text-muted-foreground">
              {view === "signup"
                ? "Register with your IIUM Live email to start sharing."
                : "Use your IIUM Live account to continue."}
            </p>
          </div>

          {!configured && (
            <Card className="border-amber-500/40 bg-amber-500/5">
              <CardContent className="p-4 text-sm">
                Supabase is not configured. Create{" "}
                <code className="rounded bg-muted px-1 py-0.5 text-xs">.env.local</code> in the
                frontend folder and fill in your project URL and anon key.
              </CardContent>
            </Card>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {view === "signup" && (
              <div className="space-y-2">
                <Label htmlFor="full_name">Full name</Label>
                <Input
                  id="full_name"
                  type="text"
                  autoComplete="name"
                  required
                  placeholder="Ahmad bin Abdullah"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  maxLength={160}
                />
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="email">IIUM Live email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                placeholder="xxxxxxx@live.iium.edu.my"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                aria-describedby="email-hint"
              />
              <p id="email-hint" className="text-xs text-muted-foreground">
                Accepted domains: {ALLOWED_DOMAINS.join(", ")}
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete={view === "signup" ? "new-password" : "current-password"}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              {view === "signup" && (
                <p className="text-xs text-muted-foreground">At least 8 characters.</p>
              )}
            </div>

            {view === "signup" && (
              <div className="space-y-2">
                <Label htmlFor="confirm_password">Confirm password</Label>
                <Input
                  id="confirm_password"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                />
              </div>
            )}

            {notice && (
              <p
                role="status"
                className="rounded-md bg-emerald-500/10 px-3 py-2 text-sm text-emerald-600 dark:text-emerald-400"
              >
                {notice}
              </p>
            )}

            {error && (
              <p
                role="alert"
                className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={busy || !configured}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              {view === "signup" ? "Create account" : "Sign in"}
            </Button>
          </form>

          <p className="text-center text-sm text-muted-foreground">
            {view === "signup" ? (
              <>
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => switchView("signin")}
                  className="font-medium text-primary underline-offset-4 hover:underline"
                >
                  Sign in
                </button>
              </>
            ) : (
              <>
                No account yet?{" "}
                <button
                  type="button"
                  onClick={() => switchView("signup")}
                  className="font-medium text-primary underline-offset-4 hover:underline"
                >
                  Create one
                </button>
              </>
            )}
          </p>

          <p className="flex items-start gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            Sign-up is limited to {ALLOWED_DOMAINS.join(", ")} accounts. The domain is enforced
            by the database at registration and by the backend on every request.
          </p>
        </div>
      </div>
    </div>
  );
}