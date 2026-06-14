/**
 * UC-18 — Compose and download a one-page portfolio snapshot.
 *
 * The user chooses any subset of expertise tags, publications and
 * background records; alternatively the `use_defaults` toggle delegates
 * the selection to the backend (top-confidence tags + most-recent items).
 */
import { useEffect, useMemo, useState } from "react";
import { api, extractApiError } from "../api/client";
import { useAuthStore } from "../store/auth";
import type {
  AcademicBackground,
  ExportSnapshotRequest,
  Publication,
  StaffProfileDetail,
} from "../types";
import { Banner, EmptyState } from "./Profile";

export function ExportSnapshotPage() {
  const { user } = useAuthStore();
  const [profile, setProfile] = useState<StaffProfileDetail | null>(null);
  const [background, setBackground] = useState<AcademicBackground[]>([]);
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());
  const [selectedPubs, setSelectedPubs] = useState<Set<string>>(new Set());
  const [selectedBg, setSelectedBg] = useState<Set<string>>(new Set());
  const [format, setFormat] = useState<"pdf" | "docx">("pdf");
  const [useDefaults, setUseDefaults] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        const [pRes, bRes] = await Promise.all([
          api.get<StaffProfileDetail>(`/profile/staff/${user.id}`),
          api.get<AcademicBackground[]>("/profile/background"),
        ]);
        setProfile(pRes.data);
        setBackground(bRes.data);
      } catch (err) {
        setError(extractApiError(err, "Could not load profile."));
      }
    })();
  }, [user]);

  function toggle(set: Set<string>, id: string, setter: (s: Set<string>) => void) {
    const next = new Set(set);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setter(next);
  }

  const isEmptySelection = useMemo(
    () =>
      !useDefaults &&
      selectedTags.size === 0 &&
      selectedPubs.size === 0 &&
      selectedBg.size === 0,
    [useDefaults, selectedTags, selectedPubs, selectedBg],
  );

  async function generate() {
    if (isEmptySelection) {
      setError(
        "Select at least one data point or enable 'use defaults'.",
      );
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const payload: ExportSnapshotRequest = {
        include_tag_ids: Array.from(selectedTags),
        include_publication_ids: Array.from(selectedPubs),
        include_background_ids: Array.from(selectedBg),
        format,
        use_defaults: useDefaults,
      };
      const response = await api.post("/export/snapshot", payload, {
        responseType: "blob",
      });
      const blob = new Blob([response.data], {
        type:
          format === "pdf"
            ? "application/pdf"
            : "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `expertise-snapshot.${format}`;
      link.click();
      URL.revokeObjectURL(url);
      setInfo("Snapshot generated and downloaded.");
    } catch (err) {
      setError(extractApiError(err, "Export failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-heading-1 font-announce text-text-primary">
          Export Portfolio Snapshot
        </h1>
      </header>

      {error && <Banner kind="error">{error}</Banner>}
      {info && <Banner kind="success">{info}</Banner>}

      <section className="card flex flex-wrap items-center gap-4">
        <label className="inline-flex items-center gap-2 text-small text-text-secondary">
          <input
            type="checkbox"
            checked={useDefaults}
            onChange={(e) => setUseDefaults(e.target.checked)}
          />
          Let the server choose the top tags &amp; recent publications
        </label>
        <div className="ml-auto inline-flex items-center gap-2">
          <span className="text-caption text-text-tertiary">Format</span>
          <select
            className="input w-28"
            value={format}
            onChange={(e) => setFormat(e.target.value as "pdf" | "docx")}
          >
            <option value="pdf">PDF</option>
            <option value="docx">DOCX</option>
          </select>
          <button
            type="button"
            className="btn-primary"
            onClick={generate}
            disabled={busy}
          >
            {busy ? "Generating…" : "Generate & Download"}
          </button>
        </div>
      </section>

      <section className="card">
        <h2 className="mb-3 text-heading-3 font-announce text-text-primary">
          Expertise tags
        </h2>
        {!profile || profile.expertise.length === 0 ? (
          <EmptyState text="No tags available to include." />
        ) : (
          <div className="flex flex-wrap gap-2">
            {profile.expertise.map((t) => {
              const active = selectedTags.has(t.tag.id);
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() =>
                    toggle(selectedTags, t.tag.id, setSelectedTags)
                  }
                  className={`pill ${
                    active
                      ? "border-brand-green bg-brand-green text-white"
                      : ""
                  }`}
                >
                  {t.tag.canonical_label}
                </button>
              );
            })}
          </div>
        )}
      </section>

      <section className="card">
        <h2 className="mb-3 text-heading-3 font-announce text-text-primary">
          Publications
        </h2>
        {!profile || profile.publications.length === 0 ? (
          <EmptyState text="No publications available to include." />
        ) : (
          <ul className="divide-y divide-border-secondary">
            {profile.publications.map((p: Publication) => {
              const active = selectedPubs.has(p.id);
              return (
                <li key={p.id} className="flex items-center gap-3 py-2">
                  <input
                    type="checkbox"
                    checked={active}
                    onChange={() =>
                      toggle(selectedPubs, p.id, setSelectedPubs)
                    }
                  />
                  <div>
                    <div className="text-body text-text-primary">
                      {p.title ?? p.doi}
                    </div>
                    <div className="text-caption text-text-tertiary">
                      {p.venue ?? "Venue n/a"}
                      {p.publication_year && ` · ${p.publication_year}`}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="card">
        <h2 className="mb-3 text-heading-3 font-announce text-text-primary">
          Academic background
        </h2>
        {background.length === 0 ? (
          <EmptyState text="No background records available." />
        ) : (
          <ul className="divide-y divide-border-secondary">
            {background.map((b) => {
              const active = selectedBg.has(b.id);
              return (
                <li key={b.id} className="flex items-center gap-3 py-2">
                  <input
                    type="checkbox"
                    checked={active}
                    onChange={() => toggle(selectedBg, b.id, setSelectedBg)}
                  />
                  <div>
                    <div className="text-body text-text-primary">{b.title}</div>
                    <div className="text-caption text-text-tertiary">
                      {b.category} · {b.organization ?? "—"} · {b.start_date}
                      {b.end_date ? ` → ${b.end_date}` : " → present"}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
