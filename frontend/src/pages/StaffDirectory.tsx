/**
 * UC-7 — Administrator browses and searches the staff directory.
 */
import { useEffect, useState } from "react";
import { api, extractApiError } from "../api/client";
import type {
  StaffDirectoryEntry,
  StaffProfileDetail,
  StaffSearchCategory,
} from "../types";
import { Banner, EmptyState, TagPill } from "./Profile";

const CATEGORY_OPTIONS: { value: StaffSearchCategory; label: string }[] = [
  { value: "name", label: "Name" },
  { value: "expertise", label: "Expertise" },
  { value: "publication", label: "Publication" },
  { value: "department", label: "Department" },
];

export function StaffDirectoryPage() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState<StaffSearchCategory>("name");
  const [department, setDepartment] = useState("");
  const [tagLabel, setTagLabel] = useState("");
  const [rows, setRows] = useState<StaffDirectoryEntry[]>([]);
  const [openProfile, setOpenProfile] = useState<StaffProfileDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function search() {
    setBusy(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (q.trim()) {
        params.q = q.trim();
        params.category = category;
      }
      if (department.trim()) params.department = department.trim();
      if (tagLabel.trim()) params.tag_label = tagLabel.trim();
      const { data } = await api.get<StaffDirectoryEntry[]>("/profile/staff", {
        params,
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

  async function openStaff(id: string) {
    setError(null);
    try {
      const { data } = await api.get<StaffProfileDetail>(`/profile/staff/${id}`);
      setOpenProfile(data);
    } catch (err) {
      setError(extractApiError(err, "Could not load staff profile."));
    }
  }

  async function triggerSync(id: string) {
    setError(null);
    try {
      await api.post(`/sync/users/${id}`);
      await openStaff(id);
    } catch (err) {
      setError(extractApiError(err, "Sync trigger failed."));
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-heading-1 font-announce text-text-primary">
          Staff Profiles
        </h1>
      </header>

      {error && <Banner kind="error">{error}</Banner>}

      <section className="card grid grid-cols-1 gap-3 md:grid-cols-4">
        <div className="md:col-span-2">
          <label className="label">Keyword</label>
          <input
            className="input"
            placeholder="Search…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void search();
            }}
          />
        </div>
        <div>
          <label className="label">Category</label>
          <select
            className="input"
            value={category}
            onChange={(e) =>
              setCategory(e.target.value as StaffSearchCategory)
            }
          >
            {CATEGORY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Department filter</label>
          <input
            className="input"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void search();
            }}
          />
        </div>
        <div className="md:col-span-3">
          <label className="label">Tag filter (canonical label)</label>
          <input
            className="input"
            value={tagLabel}
            onChange={(e) => setTagLabel(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void search();
            }}
          />
        </div>
        <div className="flex items-end justify-end">
          <button
            type="button"
            className="btn-primary"
            onClick={search}
            disabled={busy}
          >
            {busy ? "Searching…" : "Search"}
          </button>
        </div>
      </section>

      <section className="card overflow-hidden p-0">
        <table className="min-w-full divide-y divide-border-secondary text-small">
          <thead className="bg-bg-surface text-caption uppercase tracking-wide text-text-quaternary">
            <tr>
              <th className="px-4 py-3 text-left font-signature">Name</th>
              <th className="px-4 py-3 text-left font-signature">Department</th>
              <th className="px-4 py-3 text-left font-signature">Top tags</th>
              <th className="px-4 py-3 text-right font-signature">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-secondary">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-text-tertiary">
                  No matching staff.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.id}>
                  <td className="px-4 py-3 text-text-primary">
                    {r.full_name}
                    <div className="text-caption text-text-tertiary">
                      {r.email}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-text-secondary">
                    {r.department ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-text-tertiary">
                    <div className="flex flex-wrap gap-1">
                      {r.tag_labels.slice(0, 6).map((label) => (
                        <span key={label} className="pill">
                          {label}
                        </span>
                      ))}
                      {r.tag_labels.length > 6 && (
                        <span className="text-caption text-text-quaternary">
                          +{r.tag_labels.length - 6}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={() => openStaff(r.id)}
                    >
                      View profile
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      {openProfile && (
        <section className="card space-y-4">
          <header className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-heading-3 font-announce text-text-primary">
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
      )}
    </div>
  );
}
