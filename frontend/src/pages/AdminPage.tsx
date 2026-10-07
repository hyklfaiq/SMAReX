import { FileWarning, Search, ShieldAlert, Trash2, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/EmptyState";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDebounced } from "@/hooks/useDebounced";
import {
  useAdminActions,
  useAdminResources,
  useAdminSecurityLogs,
  useAdminStats,
  useAdminUsers,
} from "@/hooks/useResources";
import { errorMessage, formatDate } from "@/lib/utils";

export default function AdminPage() {
  useEffect(() => {
    document.title = "Admin \u00b7 SMAReX";
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-serif text-2xl sm:text-3xl">Administration</h1>
        <p className="text-muted-foreground">
          Manage users, moderate resources and review security scan history.
        </p>
      </header>

      <StatsRow />
      <Tabs defaultValue="resources">
        <TabsList>
          <TabsTrigger value="resources">Resources</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="security">Security logs</TabsTrigger>
        </TabsList>

        <TabsContent value="resources" className="mt-4">
          <ResourcesTab />
        </TabsContent>
        <TabsContent value="users" className="mt-4">
          <UsersTab />
        </TabsContent>
        <TabsContent value="security" className="mt-4">
          <SecurityTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function StatsRow() {
  const { data, isLoading } = useAdminStats();

  const stats = [
    { label: "Users", value: data?.total_users },
    { label: "Resources", value: data?.total_resources },
    { label: "Safely stored", value: data?.safe_resources },
    { label: "Rejected uploads", value: data?.rejected_uploads },
    { label: "Downloads", value: data?.total_downloads },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {stats.map((stat) => (
        <Card key={stat.label}>
          <CardContent className="p-5">
            <p className="text-xs text-muted-foreground">{stat.label}</p>
            <p className="mt-1 text-2xl font-semibold">
              {isLoading ? "\u2026" : (stat.value ?? 0)}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ResourcesTab() {
  const [status, setStatus] = useState<string | undefined>(undefined);
  const { data, isLoading } = useAdminResources(status);
  const { deleteResource } = useAdminActions();
  const [pending, setPending] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {[undefined, "safe", "malicious", "suspicious", "error"].map((value) => (
          <Button
            key={value ?? "all"}
            size="sm"
            variant={status === value ? "default" : "outline"}
            onClick={() => setStatus(value)}
          >
            {value ?? "All"}
          </Button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading resources...</p>
      ) : !data || data.length === 0 ? (
        <EmptyState icon={FileWarning} title="No resources" description="Nothing matches this filter." />
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    <th scope="col" className="p-3 text-left font-medium">Title</th>
                    <th scope="col" className="p-3 text-left font-medium">Uploader</th>
                    <th scope="col" className="p-3 text-left font-medium">Security</th>
                    <th scope="col" className="p-3 text-left font-medium">Downloads</th>
                    <th scope="col" className="p-3 text-right font-medium">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((resource) => (
                    <tr key={resource.id} className="border-b last:border-0">
                      <td className="p-3">
                        <div className="max-w-xs truncate font-medium">{resource.title}</div>
                        <div className="text-xs text-muted-foreground">
                          {formatDate(resource.created_at)}
                        </div>
                      </td>
                      <td className="p-3 text-muted-foreground">
                        {resource.owner_name ?? "\u2014"}
                      </td>
                      <td className="p-3">
                        <Badge
                          variant={
                            resource.security_status === "safe" ? "success" : "destructive"
                          }
                        >
                          {resource.security_status}
                        </Badge>
                      </td>
                      <td className="p-3 text-muted-foreground">{resource.download_count}</td>
                      <td className="p-3 text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="Delete resource"
                          onClick={() => setPending(resource.id)}
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      <AlertDialog open={Boolean(pending)} onOpenChange={(open) => !open && setPending(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove this resource?</AlertDialogTitle>
            <AlertDialogDescription>
              The stored PDF and its metadata will be deleted permanently.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (!pending) return;
                deleteResource
                  .mutateAsync(pending)
                  .then(() => toast.success("Resource removed"))
                  .catch((err) => toast.error(errorMessage(err)))
                  .finally(() => setPending(null));
              }}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function UsersTab() {
  const [search, setSearch] = useState("");
  const debounced = useDebounced(search, 350);
  const { data, isLoading } = useAdminUsers(debounced || undefined);
  const { setUserRole } = useAdminActions();

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by name or email..."
          className="pl-9"
          aria-label="Search users"
        />
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading users...</p>
      ) : !data || data.length === 0 ? (
        <EmptyState icon={Users} title="No users" description="Nobody matches that search." />
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    <th scope="col" className="p-3 text-left font-medium">User</th>
                    <th scope="col" className="p-3 text-left font-medium">Role</th>
                    <th scope="col" className="p-3 text-left font-medium">Status</th>
                    <th scope="col" className="p-3 text-right font-medium">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((user) => (
                    <tr key={user.id} className="border-b last:border-0">
                      <td className="p-3">
                        <div className="font-medium">{user.full_name}</div>
                        <div className="text-xs text-muted-foreground">{user.email}</div>
                      </td>
                      <td className="p-3">
                        <Badge variant={user.role === "admin" ? "default" : "secondary"}>
                          {user.role}
                        </Badge>
                      </td>
                      <td className="p-3">
                        <Badge variant={user.is_active ? "success" : "destructive"}>
                          {user.is_active ? "Active" : "Suspended"}
                        </Badge>
                      </td>
                      <td className="p-3 text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              setUserRole
                                .mutateAsync({
                                  id: user.id,
                                  role: user.role === "admin" ? "student" : "admin",
                                })
                                .then(() => toast.success("Role updated"))
                                .catch((err) => toast.error(errorMessage(err)))
                            }
                          >
                            {user.role === "admin" ? "Demote" : "Promote"}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              setUserRole
                                .mutateAsync({
                                  id: user.id,
                                  role: user.role,
                                  active: !user.is_active,
                                })
                                .then(() => toast.success("Account updated"))
                                .catch((err) => toast.error(errorMessage(err)))
                            }
                          >
                            {user.is_active ? "Suspend" : "Restore"}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function SecurityTab() {
  const [status, setStatus] = useState<string | undefined>(undefined);
  const { data, isLoading } = useAdminSecurityLogs(status);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {[undefined, "safe", "malicious", "suspicious", "error"].map((value) => (
          <Button
            key={value ?? "all"}
            size="sm"
            variant={status === value ? "default" : "outline"}
            onClick={() => setStatus(value)}
          >
            {value ?? "All"}
          </Button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading scan history...</p>
      ) : !data || data.length === 0 ? (
        <EmptyState
          icon={ShieldAlert}
          title="No scan records"
          description="VirusTotal verdicts will appear here."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    <th scope="col" className="p-3 text-left font-medium">File</th>
                    <th scope="col" className="p-3 text-left font-medium">Verdict</th>
                    <th scope="col" className="p-3 text-left font-medium">Details</th>
                    <th scope="col" className="p-3 text-left font-medium">Scanned</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((entry) => (
                    <tr key={entry.id} className="border-b last:border-0">
                      <td className="p-3">
                        <div className="max-w-[16rem] truncate font-medium">{entry.file_name}</div>
                        <div className="max-w-[16rem] truncate font-mono text-[11px] text-muted-foreground">
                          {entry.file_hash.slice(0, 24)}\u2026
                        </div>
                      </td>
                      <td className="p-3">
                        <Badge
                          variant={entry.scan_status === "safe" ? "success" : "destructive"}
                        >
                          {entry.scan_status}
                        </Badge>
                      </td>
                      <td className="max-w-sm p-3 text-xs text-muted-foreground">
                        {entry.details ?? "\u2014"}
                      </td>
                      <td className="p-3 text-xs text-muted-foreground">
                        {formatDate(entry.scan_date)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}