import { Loader2, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { KULLIYYAH } from "@/lib/constants";
import { errorMessage, formatDate, initials } from "@/lib/utils";

export default function ProfilePage() {
  const { profile, isAdmin, refreshProfile } = useAuth();

  const [fullName, setFullName] = useState(profile?.full_name ?? "");
  const [kulliyyah, setKulliyyah] = useState(profile?.kulliyyah ?? "");
  const [programme, setProgramme] = useState(profile?.programme ?? "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    document.title = "Profile \u00b7 SMAReX";
  }, []);

  useEffect(() => {
    setFullName(profile?.full_name ?? "");
    setKulliyyah(profile?.kulliyyah ?? "");
    setProgramme(profile?.programme ?? "");
  }, [profile]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      await api.updateProfile({
        full_name: fullName.trim() || undefined,
        kulliyyah: kulliyyah || null,
        programme: programme || null,
      });
      await refreshProfile();
      toast.success("Profile updated");
    } catch (err) {
      toast.error(errorMessage(err, "Could not save your profile."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <h1 className="font-serif text-2xl sm:text-3xl">Profile</h1>
        <p className="text-muted-foreground">
          Your academic details help other students know who shared a resource.
        </p>
      </header>

      <Card>
        <CardContent className="flex items-center gap-4 p-6">
          <Avatar className="h-16 w-16">
            <AvatarFallback className="text-lg">{initials(profile?.full_name)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0 space-y-1">
            <p className="truncate text-lg font-medium">{profile?.full_name}</p>
            <p className="truncate text-sm text-muted-foreground">{profile?.email}</p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Badge variant={isAdmin ? "default" : "secondary"}>
                {isAdmin ? "Administrator" : "Student"}
              </Badge>
              {profile?.created_at && (
                <span className="text-xs text-muted-foreground">
                  Joined {formatDate(profile.created_at)}
                </span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <form onSubmit={save}>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="full_name">Full name</Label>
              <Input
                id="full_name"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                maxLength={160}
                autoComplete="name"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="kulliyyah">Kulliyyah</Label>
              <select
                id="kulliyyah"
                value={kulliyyah}
                onChange={(event) => setKulliyyah(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="">Not specified</option>
                {KULLIYYAH.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="programme">Programme</Label>
              <Input
                id="programme"
                value={programme}
                onChange={(event) => setProgramme(event.target.value)}
                maxLength={200}
                placeholder="BSc Computer Science"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" value={profile?.email ?? ""} disabled />
              <p className="text-xs text-muted-foreground">
                Your email is tied to your IIUM Live account and cannot be changed here.
              </p>
            </div>

            <Button type="submit" disabled={saving}>
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Save className="h-4 w-4" aria-hidden="true" />
              )}
              Save changes
            </Button>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}