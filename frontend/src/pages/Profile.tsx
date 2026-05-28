/**
 * UC-7 + UC-12 — Consolidated academic profile for the signed-in user.
 *
 * Renders the harvested expertise tags, publications and recent sync
 * jobs, and exposes the manual sync trigger required by UC-12.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, extractApiError } from "../api/client";
import { useAuthStore } from "../store/auth";
import type {
  Publication,
  StaffProfileDetail,
  SyncJob,
  UserExpertiseTag,
} from "../types";

export function ProfileOverviewPage() {
  const { user } = useAuthStore();
  const [profile, setProfile] = useState<StaffProfileDetail | null>(null);
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);

  async function loadAll() {
    if (!user) return;
    try {
      const [pRes, jRes] = await Promise.all([
        api.get<StaffProfileDetail>(`/profile/staff/${user.id}`),
        api.get<SyncJob[]>(`/sync/jobs`),
      ]);
      setProfile(pRes.data);
      setJobs(jRes.data);
    } catch (err) {
      setError(extractApiError(err, "Could not load profile."));
    }
  }

  useEffect(() => {
    void loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  async function triggerSync() {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const { data } = await api.post<SyncJob>("/sync/me");
      setInfo(
        `Sync ${data.status}. ${data.publications_added} new publication(s), ${data.tags_added} new tag(s).`,
      );
      await loadAll();
    } catch (err) {
      setError(extractApiError(err, "Manual sync failed."));
    } finally {
      setBusy(false);
    }
  }

  const validatedCount = useMemo(
    () => profile?.expertise.filter((e) => e.validated).length ?? 0,
    [profile],
  );

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-caption font-signature uppercase tracking-wide text-text-quaternary">
            UC-7 / UC-12
          </p>
          <h1 className="mt-1 text-heading-1 font-announce text-text-primary">
            Profile Overview
          </h1>
          <p className="mt-2 max-w-2xl text-body-lg text-text-tertiary">
            Consolidated view of your AI-generated expertise tags, harvested
            publications and recent synchronization activity.
          </p>
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={triggerSync}
          disabled={busy || !user?.orcid_id}
          title={
            user?.orcid_id
              ? "Run a manual ORCID + OpenAlex harvest now."
              : "Link an ORCID ID in your profile to enable harvesting."
          }
        >
          {busy ? "Syncing…" : "Run manual sync"}
        </button>
      </header>

      {error && <Banner kind="error">{error}</Banner>}
      {info && <Banner kind="info">{info}</Banner>}

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Stat label="Expertise tags" value={profile?.expertise.length ?? 0} />
        <Stat label="Validated" value={validatedCount} />
        <Stat label="Publications" value={profile?.publications.length ?? 0} />
      </section>

      <section className="card">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-heading-3 font-announce text-text-primary">
            Expertise Tags
          </h2>
          <Link to="/staff/tags" className="text-caption text-brand-violet hover:text-brand-hover">
            Refine tags →
          </Link>
        </div>
        {profile && profile.expertise.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {profile.expertise.slice(0, 30).map((t) => (
              <TagPill key={t.id} tag={t} />
            ))}
          </div>
        ) : (
          <EmptyState text="No expertise tags yet. Run a sync to populate them." />
        )}
      </section>

      <section className="card">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-heading-3 font-announce text-text-primary">
            Recent Publications
          </h2>
          <Link
            to="/staff/publications"
            className="text-caption text-brand-violet hover:text-brand-hover"
          >
            Manage abstracts →
          </Link>
        </div>
        {profile && profile.publications.length > 0 ? (
          <ul className="divide-y divide-white/[0.05]">
            {profile.publications.slice(0, 8).map((p) => (
              <PublicationRow key={p.id} publication={p} />
            ))}
          </ul>
        ) : (
          <EmptyState text="No publications harvested yet." />
        )}
      </section>

      <section className="card">
        <h2 className="mb-4 text-heading-3 font-announce text-text-primary">
          Recent Sync Jobs
        </h2>
        {jobs.length === 0 ? (
          <EmptyState text="No sync jobs recorded yet." />
        ) : (
          <table className="min-w-full divide-y divide-white/[0.05] text-small">
            <thead className="text-caption uppercase tracking-wide text-text-quaternary">
              <tr>
                <th className="px-2 py-2 text-left font-signature">Trigger</th>
                <th className="px-2 py-2 text-left font-signature">Status</th>
                <th className="px-2 py-2 text-right font-signature">Pubs</th>
                <th className="px-2 py-2 text-right font-signature">Tags</th>
                <th className="px-2 py-2 text-left font-signature">Finished</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05]">
              {jobs.slice(0, 10).map((j) => (
                <tr key={j.id}>
                  <td className="px-2 py-2 text-text-secondary">{j.trigger}</td>
                  <td className="px-2 py-2">
                    <span className="pill">{j.status}</span>
                  </td>
                  <td className="px-2 py-2 text-right text-text-secondary">{j.publications_added}</td>
                  <td className="px-2 py-2 text-right text-text-secondary">{j.tags_added}</td>
                  <td className="px-2 py-2 text-text-tertiary">
                    {j.finished_at ? new Date(j.finished_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared subcomponents (reused across staff pages).
// ---------------------------------------------------------------------------

export function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="card">
      <div className="text-caption uppercase tracking-wide text-text-quaternary">
        {label}
      </div>
      <div className="mt-2 text-heading-1 font-announce text-text-primary">
        {value}
      </div>
    </div>
  );
}

export function EmptyState({ text }: { text: string }) {
  return <p className="text-small text-text-tertiary">{text}</p>;
}

export function Banner({
  kind,
  children,
}: {
  kind: "error" | "info" | "success";
  children: React.ReactNode;
}) {
  const tone =
    kind === "error"
      ? "border-white/[0.08] text-text-secondary"
      : kind === "success"
      ? "border-status-green/40 text-status-emerald"
      : "border-brand-violet/40 text-brand-violet";
  return (
    <div
      className={`rounded-comfy border bg-white/[0.02] p-3 text-caption ${tone}`}
    >
      {children}
    </div>
  );
}

export function TagPill({ tag }: { tag: UserExpertiseTag }) {
  const validated = tag.validated;
  return (
    <span
      className={`pill ${
        validated
          ? "border-brand-violet/50 text-text-primary"
          : "text-text-secondary"
      }`}
      title={`Confidence: ${(tag.confidence * 100).toFixed(0)}% · Source: ${tag.source}`}
    >
      {tag.tag.canonical_label}
      {validated && <span className="ml-1 text-status-emerald">✓</span>}
    </span>
  );
}

function PublicationRow({ publication }: { publication: Publication }) {
  return (
    <li className="py-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-body text-text-primary">
            {publication.title ?? publication.doi}
          </div>
          <div className="mt-1 text-caption text-text-tertiary">
            {publication.venue ?? "Venue n/a"}
            {publication.publication_year && (
              <span className="ml-2">· {publication.publication_year}</span>
            )}
            <span className="ml-2">· DOI {publication.doi}</span>
          </div>
        </div>
        {publication.abstract_missing && (
          <span className="pill border-brand-violet/50 text-brand-violet">
            Abstract missing
          </span>
        )}
      </div>
    </li>
  );
}
