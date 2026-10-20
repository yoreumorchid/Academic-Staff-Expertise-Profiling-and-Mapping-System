import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./layouts/AppShell";
import { RequireAuth } from "./layouts/RequireAuth";
import { SessionExpiredModal } from "./layouts/SessionExpiredModal";
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

const PAGE_TITLES: Record<string, string> = {
  "/login": "Log In",
  "/register": "Create Account",
  "/forgot-password": "Reset Password",
  "/reset-password": "Choose New Password",
  "/staff/profile": "Profile Overview",
  "/staff/tags": "Expertise Tag Refinement",
  "/staff/background": "Academic Background",
  "/staff/publications": "Publications & Abstracts",
  "/staff/export": "Export Portfolio Snapshot",
  "/admin": "Dashboard",
  "/admin/registrations": "Pending Registrations",
  "/admin/staff": "Staff Profiles",
  "/admin/mapping/course": "Course Mapping",
  "/admin/mapping/grant": "Research Grant Mapping",
  "/admin/gap": "Gap Analytics Overview",
  "/admin/benchmarking/global": "Global Benchmarking",
};

function DocumentTitle() {
  const { pathname } = useLocation();

  useEffect(() => {
    const pageTitle = PAGE_TITLES[pathname];
    document.title = pageTitle
      ? `${pageTitle} | Expertise Insight`
      : "Expertise Insight";
  }, [pathname]);

  return null;
}

export function App() {
  const hydrate = useAuthStore((s) => s.hydrate);
  useEffect(() => hydrate(), [hydrate]);

  return (
    <>
      <DocumentTitle />
      <SessionExpiredModal />
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
          path="/admin/profile"
          element={<Navigate to="/staff/profile" replace />}
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
    </>
  );
}
