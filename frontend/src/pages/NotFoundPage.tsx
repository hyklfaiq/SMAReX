import { Compass, Home } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

export default function NotFoundPage() {
  useEffect(() => {
    document.title = "Not found \u00b7 SMAReX";
  }, []);

  return (
    <div className="grid min-h-[60vh] place-items-center px-6 text-center">
      <div className="space-y-4">
        <Compass className="mx-auto h-12 w-12 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-serif text-3xl">Page not found</h1>
        <p className="mx-auto max-w-md text-muted-foreground">
          The page you are looking for does not exist, or it may have been removed.
        </p>
        <div className="flex justify-center gap-2">
          <Button asChild>
            <Link to="/dashboard">
              <Home className="h-4 w-4" aria-hidden="true" />
              Back to dashboard
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/library">Browse the library</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}