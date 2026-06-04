/**
 * Barrel module for the dashboard surfaces. Each Use Case implementation
 * lives in its own file so audits against the spec matrix remain
 * deterministic; App.tsx imports the entire dashboard surface from here.
 */
import { useEffect, useState } from "react";
import { api, extractApiError } from "../api/client";

export { ProfileOverviewPage } from "./Profile";
export { TagRefinementPage } from "./Tags";
export { AcademicBackgroundPage } from "./Background";
export { PublicationsPage } from "./Publications";
export { ExportSnapshotPage } from "./Export";
export { AdminHomePage } from "./AdminHome";
export { StaffDirectoryPage } from "./StaffDirectory";
export { CourseMappingPage, GrantMappingPage } from "./Mapping";
export { GapAnalyticsPage, GlobalBenchmarkingPage } from "./Gap";

// ---------------------------------------------------------------------------
// UC-2 — Pending Registrations (kept inline as the only admin-side surface
// that consumes the /admin/registrations endpoint directly).
// ---------------------------------------------------------------------------

interface PendingRegistration {
  id: string;
  full_name: string;
  email: string;
  role: string;
  department: string | null;
  orcid_id: string | null;
  portfolios: { portfolio_type: string }[];
  created_at: string;
}

const ROLE_LABELS: Record<string, string> = {
  academic_staff: "Academic Staff",
  faculty_administrator: "Faculty Administrator",
};

const PORTFOLIO_LABELS: Record<string, string> = {
  faculty_manager: "Faculty Manager",
  head_of_department: "Head of Department",
  deputy_dean_research: "Deputy Dean (Research)",
  deputy_dean_ugpg: "Deputy Dean (UG/PG)",
};

function prettyRole(role: string): string {
  return (
    ROLE_LABELS[role] ??
    role
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

function prettyPortfolio(p: string): string {
  return (
    PORTFOLIO_LABELS[p] ??
    p
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

export function PendingRegistrationsPage() {
  const [rows, setRows] = useState<PendingRegistration[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    try {
      const { data } = await api.get<PendingRegistration[]>(
        "/admin/registrations",
      );
      setRows(data);
    } catch (err) {
      setError(extractApiError(err, "Could not load pending registrations."));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function decide(userId: string, approve: boolean) {
    setBusy(userId);
    setError(null);
    try {
      await api.post(`/admin/registrations/${userId}`, { approve });
      await load();
    } catch (err) {
      setError(extractApiError(err, "Authorization request failed."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-heading-1 font-announce text-text-primary">
          Pending Registrations
        </h1>
      </div>

      {error && (
        <div className="rounded-comfy border border-border-primary bg-bg-surface p-3 text-caption text-text-secondary">
          {error}
        </div>
      )}

      <div className="card overflow-hidden p-0">
        <table className="min-w-full divide-y divide-border-secondary text-small">
          <thead className="bg-bg-surface text-caption uppercase tracking-wide text-text-quaternary">
            <tr>
              <th className="px-4 py-3 text-left font-signature">Name</th>
              <th className="px-4 py-3 text-left font-signature">Email</th>
              <th className="px-4 py-3 text-left font-signature">Role</th>
              <th className="px-4 py-3 text-left font-signature">Details</th>
              <th className="px-4 py-3 text-right font-signature">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-secondary">
            {rows === null ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-text-tertiary">
                  Loading…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-text-tertiary">
                  No pending requests.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.id}>
                  <td className="px-4 py-3 text-text-primary">{row.full_name}</td>
                  <td className="px-4 py-3 text-text-secondary">{row.email}</td>
                  <td className="px-4 py-3 text-text-secondary">{prettyRole(row.role)}</td>
                  <td className="px-4 py-3 text-text-tertiary">
                    {row.department && <span>{row.department}</span>}
                    {row.orcid_id && (
                      <span className="ml-2 pill">{row.orcid_id}</span>
                    )}
                    {row.portfolios.map((p) => (
                      <span key={p.portfolio_type} className="ml-2 pill">
                        {prettyPortfolio(p.portfolio_type)}
                      </span>
                    ))}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex gap-2">
                      <button
                        type="button"
                        className="btn-primary"
                        disabled={busy === row.id}
                        onClick={() => decide(row.id, true)}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="btn-ghost"
                        disabled={busy === row.id}
                        onClick={() => decide(row.id, false)}
                      >
                        Reject
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
