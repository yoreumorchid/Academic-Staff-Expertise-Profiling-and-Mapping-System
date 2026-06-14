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
  description?: string;
}) {
  const [draftTitle, setDraftTitle] = useState("");
  const [draftText, setDraftText] = useState("");
  const [draftFile, setDraftFile] = useState<File | null>(null);
  const [specs, setSpecs] = useState<SpecIngestResponse[]>([]);
  const [report, setReport] = useState<MappingReport | null>(null);
  const [staffIndex, setStaffIndex] = useState<Record<string, StaffDirectoryEntry>>({});
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [textBusy, setTextBusy] = useState(false);
  const [fileBusy, setFileBusy] = useState(false);
  const [matchBusy, setMatchBusy] = useState(false);

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
    setTextBusy(true);
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
      setTextBusy(false);
    }
  }

  async function submitFile() {
    if (!draftFile || !draftTitle.trim()) {
      setError("Provide both a title and a file.");
      return;
    }
    setFileBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("spec_type", specType);
      fd.append("title", draftTitle);
      fd.append("file", draftFile);
      const { data } = await api.post<SpecIngestResponse>(
        "/mapping/specs/upload",
        fd,
      );
      setInfo(`Document "${data.title}" parsed and ingested.`);
      setDraftTitle("");
      setDraftFile(null);
      await loadSpecs();
    } catch (err) {
      setError(extractApiError(err, "Upload failed."));
    } finally {
      setFileBusy(false);
    }
  }

  async function runMatch(specId: string, reportId: string | null) {
    setMatchBusy(true);
    setError(null);
    setReport(null);
    try {
      if (reportId) {
        // View existing result — just fetch the saved report.
        // Also refresh the spec list so latest_report_ids are up-to-date.
        const { data } = await api.get<MappingReport>(`/mapping/reports/${reportId}`);
        setReport(data);
      } else {
        // Run fresh match.
        const { data } = await api.post<MappingReport>(
          `/mapping/specs/${specId}/match`,
          null,
          { params: { top_n: 25 } },
        );
        setReport(data);
        await loadSpecs(); // refresh to show "Matched" + latest_report_id
      }
    } catch (err) {
      setError(extractApiError(err, reportId ? "Could not load report." : "Matching failed."));
    } finally {
      setMatchBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-heading-1 font-announce text-text-primary">
          {title}
        </h1>
        {description && (
          <p className="mt-2 max-w-2xl text-body-lg text-text-tertiary">
            {description}
          </p>
        )}
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
          <button type="submit" className="btn-primary" disabled={textBusy}>
            {textBusy ? "Ingesting…" : "Ingest text"}
          </button>
        </div>

        <div className="border-t border-border-secondary pt-3">
          <p className="text-caption text-text-tertiary">
            Or upload a PDF / DOCX:
          </p>
          <div className="mt-2">
            <input
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => setDraftFile(e.target.files?.[0] ?? null)}
              className="text-small text-text-secondary"
            />
          </div>
          {draftFile && !draftTitle.trim() && (
            <p className="mt-2 text-caption text-status-amber">
              Please fill in the Title field above before uploading.
            </p>
          )}
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              className="btn-primary"
              onClick={submitFile}
              disabled={fileBusy || !draftFile || !draftTitle.trim()}
            >
              {fileBusy ? "Uploading…" : "Upload"}
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
          <ul className="divide-y divide-border-secondary">
            {specs.map((s) => {
              const hasReport = !!s.latest_report_id;
              return (
                <li
                  key={s.id}
                  className="flex items-center justify-between py-2"
                >
                  <div>
                    <div className="text-body text-text-primary">{s.title}</div>
                    <div className="text-caption text-text-tertiary">
                      {s.source_filename ?? "text input"}
                      {hasReport && (
                        <span className="ml-2 text-brand-green">· Matched</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {hasReport && (
                      <button
                        type="button"
                        className="btn-ghost"
                        onClick={async () => {
                          try {
                            const response = await api.get(
                              `/mapping/specs/${s.id}/export`,
                              { responseType: "blob" },
                            );
                            const blob = new Blob([response.data], { type: "application/pdf" });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.href = url;
                            a.download = `match_report_${s.title.slice(0, 20)}.pdf`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(url);
                          } catch (err) {
                            setError(extractApiError(err, "Export failed."));
                          }
                        }}
                      >
                        Export PDF
                      </button>
                    )}
                    <button
                      type="button"
                      className={`btn-ghost ${hasReport ? "text-brand-green" : ""}`}
                      onClick={() => runMatch(s.id, s.latest_report_id)}
                      disabled={matchBusy}
                    >
                      {hasReport ? "View Result" : "Run match"}
                    </button>
                    <button
                      type="button"
                      className="btn-ghost text-status-red"
                      onClick={async () => {
                        if (!window.confirm("Delete this specification and all its reports permanently?")) return;
                        try {
                          await api.delete(`/mapping/specs/${s.id}`);
                          await loadSpecs();
                          setInfo("Specification deleted.");
                        } catch (err) {
                          setError(extractApiError(err, "Delete failed."));
                        }
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {matchBusy && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30 backdrop-blur-sm">
          <div className="card text-center space-y-3">
            <p className="text-body font-signature text-text-primary">
              Running semantic match...
            </p>
            <p className="text-caption text-text-tertiary">
              Computing cosine similarity and spreading activation across all staff profiles. This may take a moment.
            </p>
          </div>
        </div>
      )}

      {report && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="match-results-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) setReport(null);
          }}
        >
          <section className="card w-full max-w-4xl max-h-[80vh] overflow-y-auto space-y-4 shadow-floating">
            <header className="flex items-start justify-between gap-4">
              <div>
                <h2
                  id="match-results-title"
                  className="text-heading-3 font-announce text-text-primary"
                >
                  Mapping Report
                </h2>
              </div>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setReport(null)}
                aria-label="Close"
              >
                Close
              </button>
            </header>
            {report.entries.length === 0 ? (
              <EmptyState text="No academic staff met the minimum semantic threshold." />
            ) : (
              <div className="space-y-6">
                {/* Section 1: Spec Title */}
                <div>
                  <div className="text-caption uppercase tracking-wide text-text-quaternary mb-1">
                    Specification Title
                  </div>
                  <h3 className="text-heading-3 font-announce text-text-primary">
                    {report.spec_title}
                  </h3>
                </div>

                {/* Section 2: Spec Content */}
                <div>
                  <div className="text-caption uppercase tracking-wide text-text-quaternary mb-1">
                    Specification Content
                  </div>
                  <p className="text-small text-text-secondary leading-relaxed whitespace-pre-line max-h-40 overflow-y-auto">
                    {report.spec_text}
                  </p>
                </div>

                {/* Section 3: Match Results */}
                <div>
                  <div className="text-caption uppercase tracking-wide text-text-quaternary mb-2">
                    Match Results
                  </div>
                  <table className="min-w-full divide-y divide-border-secondary text-small">
                    <thead className="text-caption uppercase tracking-wide text-text-quaternary">
                      <tr>
                        <th className="px-2 py-2 text-left font-signature">Rank</th>
                        <th className="px-2 py-2 text-left font-signature">Staff</th>
                        <th className="px-2 py-2 text-left font-signature">Department</th>
                        <th className="px-2 py-2 text-right font-signature">Cosine</th>
                        <th className="px-2 py-2 text-right font-signature">Spread</th>
                        <th className="px-2 py-2 text-right font-signature">Combined</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-secondary">
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
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Section 4: AI Analysis */}
                <div>
                  <div className="text-caption uppercase tracking-wide text-text-quaternary mb-2">
                    AI Analysis
                  </div>
                  {report.summary ? (
                    <p className="text-body leading-relaxed text-text-secondary whitespace-pre-line">
                      {report.summary}
                    </p>
                  ) : (
                    <p className="text-caption text-text-quaternary italic">
                      Explanation will appear here once generated.
                    </p>
                  )}
                </div>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

export const CourseMappingPage = () => (
  <MappingWorkspace
    specType="course"
    title="Course Mapping"
  />
);

export const GrantMappingPage = () => (
  <MappingWorkspace
    specType="grant"
    title="Research Grant Mapping"
  />
);
