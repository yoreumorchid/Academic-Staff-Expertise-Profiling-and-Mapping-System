/**
 * Phase-1 placeholder views for the dashboard surfaces.
 *
 * Per instructions.md §4 rule 1, no decorative or dead links are
 * permitted: each placeholder explicitly states which Use Case it will
 * implement in the next build phase and renders the spec-mandated
 * "No records found" empty-state styling instead of fabricated data.
 */

interface PlaceholderProps {
  title: string;
  uc: string;
  description: string;
}

function ModulePlaceholder({ title, uc, description }: PlaceholderProps) {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-caption font-signature uppercase tracking-wide text-text-quaternary">
          {uc}
        </p>
        <h1 className="mt-1 text-heading-1 font-announce text-text-primary">
          {title}
        </h1>
        <p className="mt-2 max-w-2xl text-body-lg text-text-tertiary">
          {description}
        </p>
      </div>
      <div className="card">
        <p className="text-small text-text-tertiary">
          No records found. This module's data pipeline is provisioned in a
          subsequent build phase per the spec matrix; the empty state shown
          here is the explicit fallback mandated by UC-7's exception flow and
          §4 rule 1 of instructions.md.
        </p>
      </div>
    </div>
  );
}

// --- Staff portal -----------------------------------------------------------

export const ProfileOverviewPage = () => (
  <ModulePlaceholder
    uc="UC-7 / UC-11"
    title="Profile Overview"
    description="Consolidated view of your AI-generated expertise tags, publications, and validated metadata."
  />
);

export const TagRefinementPage = () => (
  <ModulePlaceholder
    uc="UC-11"
    title="Expertise Tag Refinement"
    description="Review, validate, remove, or supplement the normalized expertise tags produced by the SciBERT + LLM pipeline."
  />
);

export const AcademicBackgroundPage = () => (
  <ModulePlaceholder
    uc="UC-10"
    title="Academic Background"
    description="Manage administrative roles, awards, and education with chronological-integrity validation."
  />
);

export const PublicationsPage = () => (
  <ModulePlaceholder
    uc="UC-9"
    title="Publications & Abstracts"
    description="Inspect harvested publications and supplement abstracts that OpenAlex could not return."
  />
);

export const ExportSnapshotPage = () => (
  <ModulePlaceholder
    uc="UC-18"
    title="Export Portfolio Snapshot"
    description="Compose and download a one-page PDF or DOCX of your prioritized expertise tags and selected publications."
  />
);

// --- Admin portal -----------------------------------------------------------

export const AdminHomePage = () => (
  <ModulePlaceholder
    uc="UC-6"
    title="Strategic Dashboard"
    description="High-level analytical summaries scoped to your portfolio. Use the sidebar to enter individual modules."
  />
);

export const StaffDirectoryPage = () => (
  <ModulePlaceholder
    uc="UC-7"
    title="Staff Profiles"
    description="Filterable directory of academic staff with normalized expertise tags and department affiliation."
  />
);

export const CourseMappingPage = () => (
  <ModulePlaceholder
    uc="UC-13 / UC-14"
    title="Semantic Course Mapping"
    description="Ingest a syllabus (text or document) and produce a ranked list of best-matched academic staff via cosine similarity and spreading activation."
  />
);

export const GrantMappingPage = () => (
  <ModulePlaceholder
    uc="UC-13 / UC-14"
    title="Research Grant Mapping"
    description="Ingest a grant call (text or document) and produce a ranked list of academic staff, including cross-department latent experts."
  />
);

export const GapAnalyticsPage = () => (
  <ModulePlaceholder
    uc="UC-15 / UC-17"
    title="Gap Analytics Overview"
    description="K-Means + UMAP visualization of internal expertise centroids compared against global and peer benchmarks, with LLM-synthesized narrative."
  />
);

export const GlobalBenchmarkingPage = () => (
  <ModulePlaceholder
    uc="UC-15"
    title="Global Benchmarking"
    description="Compare internal faculty clusters against IEEE Xplore-sourced global research frontiers and identify institutional white spaces."
  />
);

// --- Admin: pending registrations (UC-2) -----------------------------------

import { useEffect, useState } from "react";
import { api, extractApiError } from "../api/client";

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

export function PendingRegistrationsPage() {
  const [rows, setRows] = useState<PendingRegistration[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    try {
      const { data } = await api.get<PendingRegistration[]>(
        "/admin/registrations"
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
        <p className="text-caption font-signature uppercase tracking-wide text-text-quaternary">
          UC-2
        </p>
        <h1 className="mt-1 text-heading-1 font-announce text-text-primary">
          Pending Registrations
        </h1>
        <p className="mt-2 max-w-2xl text-body-lg text-text-tertiary">
          Review and approve or reject newly submitted accounts. Approval
          activates the account and dispatches a notification (UC-5).
        </p>
      </div>

      {error && (
        <div className="rounded-comfy border border-white/[0.08] bg-white/[0.02] p-3 text-caption text-text-secondary">
          {error}
        </div>
      )}

      <div className="card overflow-hidden p-0">
        <table className="min-w-full divide-y divide-white/[0.05] text-small">
          <thead className="bg-white/[0.02] text-caption uppercase tracking-wide text-text-quaternary">
            <tr>
              <th className="px-4 py-3 text-left font-signature">Name</th>
              <th className="px-4 py-3 text-left font-signature">Email</th>
              <th className="px-4 py-3 text-left font-signature">Role</th>
              <th className="px-4 py-3 text-left font-signature">Details</th>
              <th className="px-4 py-3 text-right font-signature">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.05]">
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
                  <td className="px-4 py-3 text-text-secondary">{row.role}</td>
                  <td className="px-4 py-3 text-text-tertiary">
                    {row.department && <span>{row.department}</span>}
                    {row.orcid_id && (
                      <span className="ml-2 pill">{row.orcid_id}</span>
                    )}
                    {row.portfolios.map((p) => (
                      <span key={p.portfolio_type} className="ml-2 pill">
                        {p.portfolio_type}
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
