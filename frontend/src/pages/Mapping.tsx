/**
 * UC-13 + UC-14 — Ingest a course or grant specification and produce a
 * ranked list of matching academic staff (cosine + spreading activation).
 *
 * The same component renders both portals: the parent variant fixes
 * ``spec_type`` so the routes /admin/mapping/course and
 * /admin/mapping/grant remain semantically distinct in the sidebar.
 */
import { FormEvent, useEffect, useState } from "react";
import { api, extractApiError } from "../api/client";
import type {
  MappingReport,
  SpecIngestResponse,
  SpecificationType,
  StaffDirectoryEntry,
} from "../types";
import { Banner, EmptyState } from "./Profile";

function MappingWorkspace({
  specType,
  title,
  description,
}: {
  specType: SpecificationType;
  title: string;
  description: string;
}) {
  const [draftTitle, setDraftTitle] = useState("");
  const [draftText, setDraftText] = useState("");
  const [draftFile, setDraftFile] = useState<File | null>(null);
  const [specs, setSpecs] = useState<SpecIngestResponse[]>([]);
  const [report, setReport] = useState<MappingReport | null>(null);
  const [staffIndex, setStaffIndex] = useState<Record<string, StaffDirectoryEntry>>({});
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadSpecs() {
    try {
      const { data } = await api.get<SpecIngestResponse[]>("/mapping/specs", {
        params: { spec_type: specType },
      });
      setSpecs(data);
    } catch (err) {
      setError(extractApiError(err, "Could not load specifications."));
    }
  }

  async function loadStaffIndex() {
    try {
      const { data } = await api.get<StaffDirectoryEntry[]>("/profile/staff");
      const idx: Record<string, StaffDirectoryEntry> = {};
      data.forEach((row) => {
        idx[row.id] = row;
      });
      setStaffIndex(idx);
    } catch {
      // Non-fatal: rendering will fall back to UUIDs.
    }
  }

  useEffect(() => {
    void loadSpecs();
    void loadStaffIndex();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [specType]);

  async function submitText(event: FormEvent) {
    event.preventDefault();
    if (!draftTitle.trim() || draftText.trim().length < 80) {
      setError("Provide a title and at least 80 characters of specification text.");
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const { data } = await api.post<SpecIngestResponse>("/mapping/specs", {
        spec_type: specType,
        title: draftTitle,
        raw_text: draftText,
      });
      setInfo(`Specification "${data.title}" ingested.`);
      setDraftTitle("");
      setDraftText("");
      await loadSpecs();
    } catch (err) {
      setError(extractApiError(err, "Ingestion failed."));
    } finally {
      setBusy(false);
    }
  }

  async function submitFile() {
    if (!draftFile || !draftTitle.trim()) {
      setError("Provide both a title and a file.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("spec_type", specType);
      fd.append("title", draftTitle);
      fd.append("file", draftFile);
      const { data } = await api.post<SpecIngestResponse>(
        "/mapping/specs/upload",
        fd,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      setInfo(`Document "${data.title}" parsed and ingested.`);
      setDraftTitle("");
      setDraftFile(null);
      await loadSpecs();
    } catch (err) {
      setError(extractApiError(err, "Upload failed."));
    } finally {
      setBusy(false);
    }
  }

  async function runMatch(specId: string) {
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      const { data } = await api.post<MappingReport>(
        `/mapping/specs/${specId}/match`,
        null,
        { params: { top_n: 25 } },
      );
      setReport(data);
    } catch (err) {
      setError(extractApiError(err, "Matching failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-caption font-signature uppercase tracking-wide text-text-quaternary">
          UC-13 / UC-14
        </p>
        <h1 className="mt-1 text-heading-1 font-announce text-text-primary">
          {title}
        </h1>
        <p className="mt-2 max-w-2xl text-body-lg text-text-tertiary">
          {description}
        </p>
      </header>

      {error && <Banner kind="error">{error}</Banner>}
      {info && <Banner kind="success">{info}</Banner>}

      <form onSubmit={submitText} className="card space-y-3">
        <div>
          <label className="label">Title</label>
          <input
            className="input"
            value={draftTitle}
            onChange={(e) => setDraftTitle(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label">Specification text (≥ 80 characters)</label>
          <textarea
            className="input min-h-[140px]"
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
          />
        </div>
        <div className="flex justify-end">
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Ingesting…" : "Ingest text"}
          </button>
        </div>

        <div className="border-t border-white/[0.05] pt-3">
          <p className="text-caption text-text-tertiary">
            Or upload a PDF / DOCX (UC-13 alternative flow):
          </p>
          <div className="mt-2 flex items-center gap-2">
            <input
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => setDraftFile(e.target.files?.[0] ?? null)}
              className="text-small text-text-secondary"
            />
            <button
              type="button"
              className="btn-primary"
              onClick={submitFile}
              disabled={busy || !draftFile || !draftTitle.trim()}
            >
              {busy ? "Uploading…" : "Upload"}
            </button>
          </div>
        </div>
      </form>

      <section className="card">
        <h2 className="mb-3 text-heading-3 font-announce text-text-primary">
          Ingested specifications
        </h2>
        {specs.length === 0 ? (
          <EmptyState text="No specifications ingested yet." />
        ) : (
          <ul className="divide-y divide-white/[0.05]">
            {specs.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between py-2"
              >
                <div>
                  <div className="text-body text-text-primary">{s.title}</div>
                  <div className="text-caption text-text-tertiary">
                    {s.source_filename ?? "text input"}
                  </div>
                </div>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => runMatch(s.id)}
                  disabled={busy}
                >
                  Run match
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {report && (
        <section className="card">
          <h2 className="mb-3 text-heading-3 font-announce text-text-primary">
            Match results
          </h2>
          {report.summary && (
            <p className="mb-3 text-small text-text-secondary">{report.summary}</p>
          )}
          {report.entries.length === 0 ? (
            <EmptyState text="No academic staff met the minimum semantic threshold (UC-14 exception)." />
          ) : (
            <table className="min-w-full divide-y divide-white/[0.05] text-small">
              <thead className="text-caption uppercase tracking-wide text-text-quaternary">
                <tr>
                  <th className="px-2 py-2 text-left font-signature">Rank</th>
                  <th className="px-2 py-2 text-left font-signature">Staff</th>
                  <th className="px-2 py-2 text-left font-signature">Department</th>
                  <th className="px-2 py-2 text-right font-signature">Cosine</th>
                  <th className="px-2 py-2 text-right font-signature">Spread</th>
                  <th className="px-2 py-2 text-right font-signature">Combined</th>
                  <th className="px-2 py-2 text-left font-signature">Flag</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.05]">
                {report.entries.map((e) => {
                  const staff = staffIndex[e.user_id];
                  return (
                    <tr key={e.user_id}>
                      <td className="px-2 py-2 text-text-secondary">{e.rank}</td>
                      <td className="px-2 py-2 text-text-primary">
                        {staff?.full_name ?? e.user_id.slice(0, 8)}
                      </td>
                      <td className="px-2 py-2 text-text-tertiary">
                        {staff?.department ?? "—"}
                      </td>
                      <td className="px-2 py-2 text-right text-text-secondary">
                        {e.cosine_score.toFixed(3)}
                      </td>
                      <td className="px-2 py-2 text-right text-text-secondary">
                        {e.spreading_score.toFixed(3)}
                      </td>
                      <td className="px-2 py-2 text-right text-text-primary">
                        {e.combined_score.toFixed(3)}
                      </td>
                      <td className="px-2 py-2">
                        {e.is_cross_department && (
                          <span className="pill border-brand-violet/50 text-brand-violet">
                            Cross-dept
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  );
}

export const CourseMappingPage = () => (
  <MappingWorkspace
    specType="course"
    title="Semantic Course Mapping"
    description="Ingest a syllabus (text or document) and produce a ranked list of best-matched academic staff via cosine similarity and spreading activation."
  />
);

export const GrantMappingPage = () => (
  <MappingWorkspace
    specType="grant"
    title="Research Grant Mapping"
    description="Ingest a grant call (text or document) and produce a ranked list of academic staff, including cross-department latent experts."
  />
);
