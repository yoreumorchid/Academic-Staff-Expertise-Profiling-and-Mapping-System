/**
 * UC-7 + UC-12 — Consolidated profile page used by ALL signed-in users.
 *
 * For dual-role accounts the page is intentionally identical in both
 * Staff View and Admin View: the profile reflects the person, not the
 * portal. It always includes:
 *   * Personal information (read-only).
 *   * Academic features (sync, tags, publications, sync jobs) — these
 *     sections render only when the user is an academic staff member or
 *     a dual-role admin who has harvested data.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, extractApiError } from "../api/client";
import { submitSync } from "../api/sync";
import { useAuthStore } from "../store/auth";
import type {
  Publication,
  StaffProfileDetail,
  SyncJob,
  UserExpertiseTag,
} from "../types";

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

const SYNC_TRIGGER_LABELS: Record<SyncJob["trigger"], string> = {
  first_login: "First sign-in",
  manual: "Requested by user",
  quarterly: "Scheduled update",
};

const SYNC_STATUS_LABELS: Record<SyncJob["status"], string> = {
  queued: "Waiting to start",
  running: "In progress",
  succeeded: "Completed",
  no_new_data: "Already up to date",
  failed: "Could not complete",
};

export function ProfileOverviewPage() {
  const { user, activeSyncJobId } = useAuthStore();
  const [profile, setProfile] = useState<StaffProfileDetail | null>(null);
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);

  // A user is considered "academic" if they hold the academic-staff role
  // or are flagged as dual-role (FA who also publishes). Pure FAs see
  // personal information here and use the separate Account Settings page
  // for sign-in security.
  const isAcademic =
    user?.role === "academic_staff" || user?.is_dual_role === true;

  // Active sync state is persisted globally by job id, so navigation and
  // refreshes do not interrupt the worker.


  async function loadAll() {
    if (!user) return;
    try {
      const requests: Promise<unknown>[] = [
        api.get<StaffProfileDetail>(`/profile/staff/${user.id}`).then((r) => {
          setProfile(r.data);
        }),
      ];
      if (isAcademic) {
        requests.push(
          api.get<SyncJob[]>(`/sync/jobs`).then((r) => setJobs(r.data)),
        );
      }
      await Promise.all(requests);
    } catch (err) {
      setError(extractApiError(err, "Could not load profile."));
    }
  }

  useEffect(() => {
    void loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  useEffect(() => {
    const reload = (event: Event) => {
      const job = (event as CustomEvent<SyncJob>).detail;
      if (job?.status === "no_new_data") {
        setInfo("Profile update completed. Your expertise profile is already up to date.");
      } else if (job?.status === "succeeded") {
        setInfo(
          `Profile update completed: ${job.publications_added} publication(s) and ${job.tags_added} expertise area(s) added.`,
        );
      }
      void loadAll();
    };
    window.addEventListener("expertise-sync-completed", reload);
    return () => window.removeEventListener("expertise-sync-completed", reload);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  async function triggerSync() {
    if (activeSyncJobId) return;
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const submission = await submitSync();
      setInfo(
        submission.alreadyActive
          ? "This profile is already being updated. Current progress is now shown."
          : "Profile update started. Progress will be shown here.",
      );
    } catch (err) {
      setError(extractApiError(err, "Could not start the profile update."));
    } finally {
      setBusy(false);
    }
  }

  const validatedCount = useMemo(
    () => profile?.expertise.filter((e) => e.validated).length ?? 0,
    [profile],
  );

  if (!user) return null;

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-heading-1 font-announce text-text-primary">
            My Profile
          </h1>
        </div>
        {isAcademic && (
          <button
            type="button"
            className="btn-primary"
            onClick={triggerSync}
            disabled={busy || Boolean(activeSyncJobId) || !user.orcid_id}
            title={
              user.orcid_id
                ? "Check ORCID and OpenAlex for the latest publications."
                : "Link an ORCID ID to enable profile updates."
            }
          >
            {activeSyncJobId
              ? "Update in progress…"
              : busy
                ? "Starting update…"
                : "Update My Profile"}
          </button>
        )}
      </header>

      {error && <Banner kind="error">{error}</Banner>}
      {info && <Banner kind="info">{info}</Banner>}

      {/* -------------------------------------------------------------- */}
      {/* Personal information — shown to everyone.                       */}
      {/* -------------------------------------------------------------- */}
      <section className="card space-y-3">
        <h2 className="text-heading-3 font-announce text-text-primary">
          Personal information
        </h2>
        <dl className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <InfoField label="Full name" value={user.full_name} />
          <InfoField label="Email" value={user.email} />
          <InfoField
            label="Phone number"
            value={user.phone_number ?? "Not provided"}
          />
          <InfoField label="Department" value={user.department ?? "—"} />
          <InfoField label="Role" value={ROLE_LABELS[user.role] ?? user.role} />
          <InfoField
            label="Portfolio"
            value={
              user.portfolios.length === 0
                ? "—"
                : user.portfolios
                    .map( 
                      (p) =>
                        PORTFOLIO_LABELS[p.portfolio_type] ?? p.portfolio_type,
                    )
                    .join(", ")
            }
          />
          <InfoField
            label="ORCID"
            value={user.orcid_id ?? "—"}
          />
        </dl>
      </section>

      {/* -------------------------------------------------------------- */}
      {/* Academic surfaces — UC-7 + UC-12. Only relevant for academic    */}
      {/* staff and dual-role administrators.                             */}
      {/* -------------------------------------------------------------- */}
      {isAcademic && (
        <>
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
              <Link
                to="/staff/tags"
                className="text-small font-signature text-brand-green hover:text-brand-green-hover"
              >
                Refine tags →
              </Link>
            </div>
            {profile && profile.expertise.length > 0 ? (
              <>
                <ul className="grid grid-cols-1 gap-x-8 md:grid-cols-2">
                  {profile.expertise.slice(0, 8).map((t) => (
                    <TagSummaryRow key={t.id} tag={t} />
                  ))}
                </ul>
                {profile.expertise.length > 8 && (
                  <p className="mt-4 text-small text-text-tertiary">
                    Showing 8 of {profile.expertise.length} expertise areas.
                  </p>
                )}
              </>
            ) : (
              <EmptyState text="No expertise tags yet. Update your profile to add them." />
            )}
          </section>

          <section className="card">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-heading-3 font-announce text-text-primary">
                Recent Publications
              </h2>
              <Link
                to="/staff/publications"
                className="text-small font-signature text-brand-green hover:text-brand-green-hover"
              >
                Manage abstracts →
              </Link>
            </div>
            {profile && profile.publications.length > 0 ? (
              <ul className="divide-y divide-border-secondary">
                {profile.publications.slice(0, 5).map((p) => (
                  <PublicationRow key={p.id} publication={p} />
                ))}
              </ul>
            ) : (
              <EmptyState text="No publications are available yet. Update your profile first." />
            )}
          </section>

          <section className="card">
            <h2 className="mb-4 text-heading-3 font-announce text-text-primary">
              Recent Profile Updates
            </h2>
            {jobs.length === 0 ? (
              <EmptyState text="No profile updates have been recorded yet." />
            ) : (
              <table className="min-w-full divide-y divide-border-secondary text-small">
                <thead className="text-caption uppercase tracking-wide text-text-quaternary">
                  <tr>
                    <th className="px-2 py-2 text-left font-signature">Started by</th>
                    <th className="px-2 py-2 text-left font-signature">Status</th>
                    <th className="px-2 py-2 text-right font-signature">Pubs</th>
                    <th className="px-2 py-2 text-right font-signature">Tags</th>
                    <th className="px-2 py-2 text-left font-signature">Finished</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-secondary">
                  {jobs.slice(0, 10).map((j) => (
                    <tr key={j.id}>
                      <td className="px-2 py-2 text-text-secondary">
                        {SYNC_TRIGGER_LABELS[j.trigger]}
                      </td>
                      <td className="px-2 py-2">
                        <span className="pill">{SYNC_STATUS_LABELS[j.status]}</span>
                      </td>
                      <td className="px-2 py-2 text-right text-text-secondary">
                        {j.publications_added}
                      </td>
                      <td className="px-2 py-2 text-right text-text-secondary">
                        {j.tags_added}
                      </td>
                      <td className="px-2 py-2 text-text-tertiary">
                        {j.finished_at
                          ? new Date(j.finished_at).toLocaleString()
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}

    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared subcomponents (reused across staff pages).
// ---------------------------------------------------------------------------

function InfoField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-caption uppercase tracking-wide text-text-quaternary">
        {label}
      </dt>
      <dd className="mt-1 text-body text-text-primary">{value}</dd>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared subcomponents (reused across staff pages).
// ---------------------------------------------------------------------------

export function Stat({ label, value }: { label: string; value: number | string }) {
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
      ? "border-border-primary text-text-secondary"
      : kind === "success"
      ? "border-status-green/40 text-status-emerald"
      : "border-brand-green/40 text-brand-green";
  return (
    <div
      className={`rounded-comfy border bg-bg-surface p-3 text-caption ${tone}`}
    >
      {children}
    </div>
  );
}

function TagSummaryRow({ tag }: { tag: UserExpertiseTag }) {
  return (
    <li className="border-b border-border-secondary py-3">
      <div className="text-body font-signature text-text-primary">
        {tag.tag.canonical_label}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-small">
        <span className="text-text-secondary">
          {tag.tag.domain ?? "Unclassified"}
        </span>
        <span className="text-text-tertiary">
          Confidence {(tag.confidence * 100).toFixed(0)}%
        </span>
        {tag.validated && (
          <span className="font-signature text-status-green">Validated</span>
        )}
      </div>
    </li>
  );
}

function PublicationRow({ publication }: { publication: Publication }) {
  return (
    <li className="py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-body font-signature leading-relaxed text-text-primary">
            {publication.title ?? publication.doi}
          </div>
          <dl className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-small text-text-tertiary">
            <div className="inline-flex gap-1.5">
              <dt>Venue</dt>
              <dd className="text-text-secondary">
                {publication.venue ?? "Not available"}
              </dd>
            </div>
            {publication.publication_year && (
              <div className="inline-flex gap-1.5">
                <dt>Year</dt>
                <dd className="text-text-secondary">
                  {publication.publication_year}
                </dd>
              </div>
            )}
          </dl>
        </div>
        {publication.abstract_missing && (
          <span className="shrink-0 text-small font-signature text-status-amber">
            Abstract missing
          </span>
        )}
      </div>
    </li>
  );
}
