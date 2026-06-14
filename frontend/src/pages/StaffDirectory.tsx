/**
 * UC-7 — Administrator browses and searches the staff directory.
 *
 * Search semantics (per UC-7 alt flows):
 *   * The Filter dropdown is single-select. "All fields" performs a
 *     full-text deep scan across name, department, expertise tags and
 *     publication metadata (backend ``category=all``).
 *   * Choosing a specific category (Name / Department / Expertise /
 *     Publications) restricts the search to that single field — staff
 *     whose match is only in another field are excluded.
 *
 * "View By" toolbar (Individual / Department / Expertise Clusters) is a
 * pure client-side regrouping of the current result set; it never
 * triggers a backend round-trip.
 */
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, extractApiError } from "../api/client";
import type {
  StaffDirectoryEntry,
  StaffProfileDetail,
  StaffSearchCategory,
} from "../types";
import { Banner, EmptyState, TagPill } from "./Profile";

const FILTER_OPTIONS: { value: StaffSearchCategory; label: string }[] = [
  { value: "all", label: "All fields" },
  { value: "name", label: "Name" },
  { value: "department", label: "Department" },
  { value: "expertise", label: "Expertise" },
  { value: "publication", label: "Publications" },
];

type ViewMode = "individual" | "department" | "expertise";

const VIEW_MODES: { value: ViewMode; label: string }[] = [
  { value: "individual", label: "Individual Cards" },
  { value: "department", label: "Department" },
  { value: "expertise", label: "Expertise Clusters" },
];

export function StaffDirectoryPage() {
  const [params] = useSearchParams();
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<StaffSearchCategory>("all");
  const [rows, setRows] = useState<StaffDirectoryEntry[]>([]);
  const [openProfile, setOpenProfile] = useState<StaffProfileDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("individual");

  async function search() {
    setBusy(true);
    setError(null);
    try {
      const keyword = q.trim();
      const { data } = await api.get<StaffDirectoryEntry[]>("/profile/staff", {
        params: keyword
          ? { q: keyword, category: filter }
          : {},
      });
      setRows(data);
    } catch (err) {
      setError(extractApiError(err, "Search failed."));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void search();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-run search when the filter changes and a keyword exists, so the
  // search scope updates immediately.
  useEffect(() => {
    if (q.trim()) void search();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  async function openStaff(id: string) {
    setError(null);
    try {
      const { data } = await api.get<StaffProfileDetail>(`/profile/staff/${id}`);
      setOpenProfile(data);
    } catch (err) {
      setError(extractApiError(err, "Could not load staff profile."));
    }
  }

  // Auto-open a profile when arriving from the global header dropdown
  // (?open=<uuid>). This fulfils the UC-7 "click any card → jump to full
  // expertise page" contract.
  useEffect(() => {
    const id = params.get("open");
    if (id) void openStaff(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  async function triggerSync(id: string) {
    setError(null);
    try {
      await api.post(`/sync/users/${id}`);
      await openStaff(id);
    } catch (err) {
      setError(extractApiError(err, "Sync trigger failed."));
    }
  }

  // ---------------------------------------------------------------------
  // View-By regrouping (client-side only — no backend round-trip).
  // ---------------------------------------------------------------------
  const groupedByDepartment = useMemo(() => {
    const groups = new Map<string, StaffDirectoryEntry[]>();
    for (const r of rows) {
      const key = r.department ?? "Unassigned";
      const arr = groups.get(key) ?? [];
      arr.push(r);
      groups.set(key, arr);
    }
    return Array.from(groups.entries()).sort((a, b) =>
      a[0].localeCompare(b[0]),
    );
  }, [rows]);

  const groupedByExpertise = useMemo(() => {
    const groups = new Map<string, StaffDirectoryEntry[]>();
    for (const r of rows) {
      const tags = r.tag_labels.length > 0 ? r.tag_labels.slice(0, 3) : ["Untagged"];
      for (const t of tags) {
        const arr = groups.get(t) ?? [];
        arr.push(r);
        groups.set(t, arr);
      }
    }
    return Array.from(groups.entries()).sort(
      (a, b) => b[1].length - a[1].length,
    );
  }, [rows]);

  const scopeLabel =
    filter === "all"
      ? "Full-text search across name, department, tags and publications."
      : `Search scoped to: ${
          FILTER_OPTIONS.find((o) => o.value === filter)?.label ?? filter
        }.`;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-heading-1 font-announce text-text-primary">
          Staff Profiles
        </h1>
      </header>

      {error && <Banner kind="error">{error}</Banner>}

      <section className="card space-y-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          <div className="flex-1">
            <label className="label">Main search</label>
            <input
              className="input"
              placeholder="Search staff…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void search();
              }}
            />
          </div>
          <div className="md:w-56">
            <label className="label">Filter</label>
            <select
              className="input"
              value={filter}
              onChange={(e) =>
                setFilter(e.target.value as StaffSearchCategory)
              }
            >
              {FILTER_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            className="btn-primary"
            onClick={search}
            disabled={busy}
          >
            {busy ? "Searching…" : "Search"}
          </button>
        </div>
        <p className="text-caption text-text-tertiary">{scopeLabel}</p>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-caption text-text-tertiary">
            {rows.length} result{rows.length === 1 ? "" : "s"}
          </div>
          <div
            role="tablist"
            aria-label="View by"
            className="inline-flex items-center rounded-full border border-border-primary bg-white p-0.5"
          >
            {VIEW_MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                role="tab"
                aria-selected={viewMode === m.value}
                onClick={() => setViewMode(m.value)}
                className={[
                  "rounded-full px-3 py-1 text-label font-signature transition-colors",
                  viewMode === m.value
                    ? "bg-brand-green text-white"
                    : "text-text-tertiary hover:text-text-primary",
                ].join(" ")}
              >
                View By: {m.label}
              </button>
            ))}
          </div>
        </div>

        {rows.length === 0 ? (
          <div className="card">
            <EmptyState text="No matching staff." />
          </div>
        ) : viewMode === "individual" ? (
          <IndividualGrid rows={rows} onOpen={openStaff} />
        ) : viewMode === "department" ? (
          <GroupList
            groups={groupedByDepartment}
            onOpen={openStaff}
            groupLabel="Department"
          />
        ) : (
          <GroupList
            groups={groupedByExpertise}
            onOpen={openStaff}
            groupLabel="Cluster"
          />
        )}
      </section>

      {openProfile && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="staff-profile-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpenProfile(null);
          }}
        >
          <section className="card w-full max-w-2xl max-h-[80vh] overflow-y-auto space-y-4 shadow-floating">
            <header className="flex items-start justify-between gap-4">
              <div>
                <h2
                  id="staff-profile-title"
                  className="text-heading-3 font-announce text-text-primary"
                >
                  {openProfile.full_name}
                </h2>
                <p className="text-caption text-text-tertiary">
                  {openProfile.department ?? "Department n/a"} · {openProfile.email}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => triggerSync(openProfile.id)}
                >
                  Trigger sync
                </button>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => setOpenProfile(null)}
                  aria-label="Close"
                >
                  Close
                </button>
              </div>
            </header>

            <div>
              <div className="mb-2 text-caption uppercase tracking-wide text-text-quaternary">
                Expertise
              </div>
              {openProfile.expertise.length === 0 ? (
                <EmptyState text="No tags." />
              ) : (
                <div className="flex flex-wrap gap-2">
                  {openProfile.expertise.map((t) => (
                    <TagPill key={t.id} tag={t} />
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="mb-2 text-caption uppercase tracking-wide text-text-quaternary">
                Publications
              </div>
              {openProfile.publications.length === 0 ? (
                <EmptyState text="No publications." />
              ) : (
                <ul className="divide-y divide-border-secondary">
                  {openProfile.publications.slice(0, 10).map((p) => (
                    <li key={p.id} className="py-2">
                      <div className="text-body text-text-primary">
                        {p.title ?? p.doi}
                      </div>
                      <div className="text-caption text-text-tertiary">
                        {p.venue ?? "Venue n/a"}
                        {p.publication_year && ` · ${p.publication_year}`}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// View-By renderers
// ---------------------------------------------------------------------------

function StaffCard({
  row,
  onOpen,
}: {
  row: StaffDirectoryEntry;
  onOpen: (id: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onOpen(row.id)}
      className="card flex w-full flex-col items-start gap-2 text-left transition-shadow hover:shadow-floating"
    >
      <div>
        <div className="text-body text-text-primary">{row.full_name}</div>
        <div className="text-caption text-text-tertiary">
          {row.department ?? "Department n/a"} · {row.email}
        </div>
      </div>
      {row.tag_labels.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {row.tag_labels.slice(0, 6).map((t) => (
            <span key={t} className="pill">
              {t}
            </span>
          ))}
          {row.tag_labels.length > 6 && (
            <span className="text-caption text-text-quaternary">
              +{row.tag_labels.length - 6}
            </span>
          )}
        </div>
      )}
    </button>
  );
}

function IndividualGrid({
  rows,
  onOpen,
}: {
  rows: StaffDirectoryEntry[];
  onOpen: (id: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      {rows.map((r) => (
        <StaffCard key={r.id} row={r} onOpen={onOpen} />
      ))}
    </div>
  );
}

function GroupList({
  groups,
  onOpen,
  groupLabel,
}: {
  groups: [string, StaffDirectoryEntry[]][];
  onOpen: (id: string) => void;
  groupLabel: string;
}) {
  return (
    <div className="space-y-4">
      {groups.map(([key, members]) => (
        <section key={key} className="card">
          <header className="mb-3 flex items-center justify-between">
            <div>
              <div className="text-caption uppercase tracking-wide text-text-quaternary">
                {groupLabel}
              </div>
              <h3 className="text-heading-3 font-announce text-text-primary">
                {key}
              </h3>
            </div>
            <span className="pill">{members.length} staff</span>
          </header>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {members.map((m) => (
              <StaffCard key={m.id + key} row={m} onOpen={onOpen} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
