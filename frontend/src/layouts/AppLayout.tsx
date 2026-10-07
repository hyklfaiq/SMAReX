/**
 * App shell: sticky navbar, optional sidebar, and the routed page area.
 *
 * Responsive: the sidebar collapses into a drawer on small screens and the
 * primary navigation is mirrored in a bottom bar on mobile.
 */
import { BookMarked, LayoutDashboard, Library, LogOut, Menu, Shield, Upload, User, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/contexts/AuthContext";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";


import { cn, initials } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: typeof Library;
}

const STUDENT_NAV: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/library", label: "Library", icon: Library },
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/saved", label: "Saved", icon: BookMarked },
  { to: "/profile", label: "Profile", icon: User },
];

export function AppLayout() {
  const { profile, isAdmin, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  const nav = isAdmin ? [...STUDENT_NAV, { to: "/admin", label: "Admin", icon: Shield }] : STUDENT_NAV;

  const closeMenu = () => setMenuOpen(false);

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75">
        <div className="container flex h-16 items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setMenuOpen((open) => !open)}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
          >
            {menuOpen ? <X /> : <Menu />}
          </Button>

          <Link to="/dashboard" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
              S
            </span>
            <span className="hidden sm:inline">SMAReX</span>
          </Link>

          <nav aria-label="Primary" className="ml-6 hidden items-center gap-1 lg:flex">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-secondary text-secondary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )
                }
              >
                <item.icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            {profile && (
              <>
                <span className="hidden text-sm text-muted-foreground sm:inline">
                  {profile.full_name}
                </span>
                <Avatar>
                  <AvatarFallback>{initials(profile.full_name)}</AvatarFallback>
                </Avatar>
              </>
            )}
            <Button variant="ghost" size="sm" onClick={() => void signOut()}>
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Sign out</span>
            </Button>
          </div>
        </div>

        {menuOpen && (
          <div className="border-t lg:hidden">
            <nav aria-label="Mobile" className="container flex flex-col py-2">
              {nav.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={closeMenu}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-2 rounded-md px-3 py-2.5 text-sm font-medium",
                      isActive ? "bg-secondary" : "text-muted-foreground",
                    )
                  }
                >
                  <item.icon className="h-4 w-4" aria-hidden="true" />
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
        )}
      </header>

      <main className="container flex-1 py-6 sm:py-8">
        <Outlet />
      </main>

      <footer className="border-t py-6">
        <div className="container flex flex-col items-center justify-between gap-2 text-xs text-muted-foreground sm:flex-row">
          <p>SMAReX — Smart Academic Resource Exchange, IIUM.</p>
          <p>Every upload is scanned with VirusTotal before it is shared.</p>
        </div>
      </footer>

      {/* Mobile bottom bar for the most-used destinations. */}
      <nav
        aria-label="Quick navigation"
        className="sticky bottom-0 z-30 border-t bg-background/95 backdrop-blur lg:hidden"
      >
        <div className="container grid grid-cols-4 py-1.5">
          {STUDENT_NAV.slice(0, 4).map((item) => {
            const active = location.pathname.startsWith(item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "flex flex-col items-center gap-0.5 rounded-md py-1.5 text-[11px] font-medium",
                  active ? "text-primary" : "text-muted-foreground",
                )}
              >
                <item.icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}