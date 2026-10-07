import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";

import { AdminRoute, ProtectedRoute } from "@/components/RouteGuards";
import { AuthProvider } from "@/contexts/AuthContext";
import { AppLayout } from "@/layouts/AppLayout";
import AdminPage from "@/pages/AdminPage";
import DashboardPage from "@/pages/DashboardPage";
import LibraryPage from "@/pages/LibraryPage";
import LoginPage from "@/pages/LoginPage";
import NotFoundPage from "@/pages/NotFoundPage";
import ProfilePage from "@/pages/ProfilePage";
import ResourceDetailsPage from "@/pages/ResourceDetailsPage";
import SavedPage from "@/pages/SavedPage";
import UploadPage from "@/pages/UploadPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // Never retry a deliberate rejection (401/403/404/422).
        const status = (error as { status?: number })?.status ?? 0;
        if ([401, 403, 404, 422].includes(status)) return false;
        return failureCount < 2;
      },
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<LoginPage initialMode="signup" />} />

            {/* Everything else requires a session */}
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/library" element={<LibraryPage />} />
              <Route path="/resources/:id" element={<ResourceDetailsPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/saved" element={<SavedPage />} />
              <Route path="/profile" element={<ProfilePage />} />

              <Route
                path="/admin"
                element={
                  <AdminRoute>
                    <AdminPage />
                  </AdminRoute>
                }
              />
            </Route>

            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>

          <Toaster position="bottom-right" richColors closeButton />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}