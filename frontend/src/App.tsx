import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layouts/AppShell";
import { RequireAuth } from "./layouts/RequireAuth";
import {
  ForgotPasswordPage,
  LoginPage,
  RegisterPage,
  ResetPasswordPage,
} from "./pages/Auth";
import {
  AcademicBackgroundPage,
  AdminHomePage,
  CourseMappingPage,
  ExportSnapshotPage,
  GapAnalyticsPage,
  GlobalBenchmarkingPage,
  GrantMappingPage,
  PendingRegistrationsPage,
  ProfileOverviewPage,
  PublicationsPage,
  StaffDirectoryPage,
  TagRefinementPage,
} from "./pages/Dashboard";
import { useAuthStore } from "./store/auth";

function Protected({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  );
}

export function App() {
  const hydrate = useAuthStore((s) => s.hydrate);
  useEffect(() => hydrate(), [hydrate]);

  return (
    <Routes>
      {/* Public auth flows (UC-1, UC-3, UC-4) */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/* Staff portal — UC-9, UC-10, UC-11, UC-18 */}
      <Route
        path="/staff/profile"
        element={<Protected><ProfileOverviewPage /></Protected>}
      />
      <Route
        path="/staff/tags"
        element={<Protected><TagRefinementPage /></Protected>}
      />
      <Route
        path="/staff/background"
        element={<Protected><AcademicBackgroundPage /></Protected>}
      />
      <Route
        path="/staff/publications"
        element={<Protected><PublicationsPage /></Protected>}
      />
      <Route
        path="/staff/export"
        element={<Protected><ExportSnapshotPage /></Protected>}
      />

      {/* Admin portal — UC-2, UC-7, UC-13, UC-14, UC-15, UC-17 */}
      <Route
        path="/admin"
        element={<Protected><AdminHomePage /></Protected>}
      />
      <Route
        path="/admin/registrations"
        element={<Protected><PendingRegistrationsPage /></Protected>}
      />
      <Route
        path="/admin/staff"
        element={<Protected><StaffDirectoryPage /></Protected>}
      />
      <Route
        path="/admin/mapping/course"
        element={<Protected><CourseMappingPage /></Protected>}
      />
      <Route
        path="/admin/mapping/grant"
        element={<Protected><GrantMappingPage /></Protected>}
      />
      <Route
        path="/admin/gap"
        element={<Protected><GapAnalyticsPage /></Protected>}
      />
      <Route
        path="/admin/benchmarking/global"
        element={<Protected><GlobalBenchmarkingPage /></Protected>}
      />

      {/* Default landing */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
