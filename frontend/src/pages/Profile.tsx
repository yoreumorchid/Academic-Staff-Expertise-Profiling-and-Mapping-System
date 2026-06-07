/**
 * UC-7 + UC-12 — Consolidated profile page used by ALL signed-in users.
 *
 * For dual-role accounts the page is intentionally identical in both
 * Staff View and Admin View: the profile reflects the person, not the
 * portal. It always includes:
 *   * Personal information (read-only).
 *   * Account operations: change password, log out.
 *   * Academic features (sync, tags, publications, sync jobs) — these
 *     sections render only when the user is an academic staff member or
 *     a dual-role admin who has harvested data.
 */
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, extractApiError } from "../api/client";
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

export function ProfileOverviewPage() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<StaffProfileDetail | null>(null);
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);

  // ---- Account management state ----
  const [pwCurrent, setPwCurrent] = useState("");
  const [pwNext1, setPwNext1] = useState("");
  const [pwNext2, setPwNext2] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwInfo, setPwInfo] = useState<string | null>(null);

  // A user is considered "academic" if they hold the academic-staff role
  // or are flagged as dual-role (FA who also publishes). Pure FAs see
  // only the account-management surfaces.
  const isAcademic =
    user?.role === "academic_staff" || user?.is_dual_role === true;

  // Long-running sync state.  Once a sync is dispatched we set
  // ``syncing=true`` so a blocking modal appears and beforeunload guards
  // any close/refresh attempts.  The button click POSTs and AWAITS the
  // backend, which is synchronous (returns only when the harvest finishes
  // or fails) — there is no separate polling channel.
  const [syncing, setSyncing] = useState(false);

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

  async function triggerSync() {
    if (syncing) return;  // double-click guard
    setSyncing(true);
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const { data } = await api.post<SyncJob>("/sync/me", null, {
        timeout: 600000,  // 10 min — large harvests can take a while
      });
      setInfo(
        `Sync ${data.status}. ${data.publications_added} new publication(s), ${data.tags_added} new tag(s).`,
      );
      await loadAll();
    } catch (err) {
      setError(extractApiError(err, "Manual sync failed."));
    } finally {
      setBusy(false);
      setSyncing(false);
    }
  }

  // Block tab close / refresh while a sync is running.
  useEffect(() => {
    if (!syncing) return;
    function onBeforeUnload(e: BeforeUnloadEvent) {
      e.preventDefault();
      e.returnValue = "";  // browsers ignore custom text but require this assignment
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [syncing]);

  async function changePassword(event: FormEvent) {
    event.preventDefault();
    setPwError(null);
    setPwInfo(null);
    if (pwNext1 !== pwNext2) {
      setPwError("New password confirmation does not match.");
      return;
    }
    setPwBusy(true);
    try {
      await api.post("/auth/change-password", {
        current_password: pwCurrent,
        new_password: pwNext1,
      });
      setPwInfo("Password updated.");
      setPwCurrent("");
      setPwNext1("");
      setPwNext2("");
    } catch (err) {
      setPwError(extractApiError(err, "Could not change password."));
    } finally {
      setPwBusy(false);
    }
  }

  function doLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  const validatedCount = useMemo(
    () => profile?.expertise.filter((e) => e.validated).length ?? 0,
    [profile],
  );

  if (!user) return null;

  return (
    <div className="space-y-6">
      {/* Blocking modal while a sync is in flight. */}
      {syncing && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="sync-status-title"
        >
          <section className="card w-full max-w-md space-y-4 shadow-floating text-center">
            <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-brand-green border-t-transparent" />
            <h2
              id="sync-status-title"
              className="text-heading-3 font-announce text-text-primary"
            >
              Sync in progress…
            </h2>
            <p className="text-small text-text-secondary">
              We are fetching your publications from ORCID + OpenAlex and
              re-running the NLP pipeline. This can take a few minutes for
              prolific researchers.
            </p>
            <p className="text-caption text-status-amber font-signature">
              ⚠ Please do not refresh, close, or navigate away from this
              page until the sync completes.
            </p>
          </section>
        </div>
      )}

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
            disabled={busy || syncing || !user.orcid_id}
            title={
              user.orcid_id
                ? "Run a manual ORCID + OpenAlex harvest now."
                : "Link an ORCID ID in your profile to enable harvesting."
            }
          >
            {syncing ? "Syncing…" : busy ? "Working…" : "Run manual sync"}
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
                className="text-caption text-brand-indigo hover:text-brand-hover"
              >
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
                className="text-caption text-brand-indigo hover:text-brand-hover"
              >
                Manage abstracts →
              </Link>
            </div>
            {profile && profile.publications.length > 0 ? (
              <ul className="divide-y divide-border-secondary">
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
              <table className="min-w-full divide-y divide-border-secondary text-small">
                <thead className="text-caption uppercase tracking-wide text-text-quaternary">
                  <tr>
                    <th className="px-2 py-2 text-left font-signature">Trigger</th>
                    <th className="px-2 py-2 text-left font-signature">Status</th>
                    <th className="px-2 py-2 text-right font-signature">Pubs</th>
                    <th className="px-2 py-2 text-right font-signature">Tags</th>
                    <th className="px-2 py-2 text-left font-signature">Finished</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-secondary">
                  {jobs.slice(0, 10).map((j) => (
                    <tr key={j.id}>
                      <td className="px-2 py-2 text-text-secondary">{j.trigger}</td>
                      <td className="px-2 py-2">
                        <span className="pill">{j.status}</span>
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

      {/* -------------------------------------------------------------- */}
      {/* Account management — shown to everyone.                         */}
      {/* -------------------------------------------------------------- */}
      {pwError && <Banner kind="error">{pwError}</Banner>}
      {pwInfo && <Banner kind="success">{pwInfo}</Banner>}
      <section className="card space-y-3">
        <h2 className="text-heading-3 font-announce text-text-primary">
          Change password
        </h2>
        <form onSubmit={changePassword} className="space-y-3">
          <div>
            <label className="label">Current password</label>
            <input
              className="input"
              type="password"
              value={pwCurrent}
              onChange={(e) => setPwCurrent(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label">New password</label>
            <input
              className="input"
              type="password"
              value={pwNext1}
              onChange={(e) => setPwNext1(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label">Confirm new password</label>
            <input
              className="input"
              type="password"
              value={pwNext2}
              onChange={(e) => setPwNext2(e.target.value)}
              required
            />
          </div>
          <div className="flex justify-end">
            <button type="submit" className="btn-primary" disabled={pwBusy}>
              {pwBusy ? "Updating…" : "Update password"}
            </button>
          </div>
        </form>
      </section>

      <section className="card space-y-3">
        <h2 className="text-heading-3 font-announce text-text-primary">
          Account
        </h2>
        <p className="text-caption text-text-tertiary">
          End the current session and return to the login screen.
        </p>
        <div className="flex justify-end">
          <button type="button" className="btn-ghost" onClick={doLogout}>
            Log out
          </button>
        </div>
      </section>
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
      ? "border-border-primary text-text-secondary"
      : kind === "success"
      ? "border-status-green/40 text-status-emerald"
      : "border-brand-indigo/40 text-brand-indigo";
  return (
    <div
      className={`rounded-comfy border bg-bg-surface p-3 text-caption ${tone}`}
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
          ? "border-brand-indigo/50 text-text-primary"
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
          <span className="pill border-brand-indigo/50 text-brand-indigo">
            Abstract missing
          </span>
        )}
      </div>
    </li>
  );
}
