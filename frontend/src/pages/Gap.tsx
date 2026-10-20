/**
 * UC-15 / UC-16 / UC-17 — Benchmarking & gap analytics.
 *
 * GapAnalyticsPage runs the combined report (which internally references
 * the most recent global + peer runs).
 * GlobalBenchmarkingPage focuses on UC-15 alone and exposes a peer
 * upload area for UC-16.
 */
import { useRef, useState } from "react";
import { api, extractApiError } from "../api/client";
import type {
  BenchmarkRun,
  BenchmarkWhiteSpace,
  DocumentPreview,
  GapAnalysisReport,
  VisualizationPayload,
} from "../types";
import { Banner, EmptyState } from "./Profile";
import { DocumentSectionPreview, getDocumentSelectionUsage } from "./DocumentSectionPreview";

// ---------------------------------------------------------------------------
// UC-17 — combined narrative + white-space list
// ---------------------------------------------------------------------------

export function GapAnalyticsPage() {
  const [report, setReport] = useState<GapAnalysisReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const { data } = await api.post<GapAnalysisReport>("/benchmarking/combined");
      setReport(data);
    } catch (err) {
      setError(extractApiError(err, "Combined report failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-heading-1 font-announce text-text-primary">
            Gap Analytics Overview
          </h1>
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={run}
          disabled={busy}
        >
          {busy ? "Generating…" : "Generate combined report"}
        </button>
      </header>

      {error && <Banner kind="error">{error}</Banner>}

      <section className="card">
        <EmptyState text="Click 'Generate combined report' to consolidate the latest benchmark runs." />
      </section>

      {report && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="gap-report-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) setReport(null);
          }}
        >
          <section className="card w-full max-w-3xl max-h-[80vh] overflow-y-auto space-y-4 shadow-floating">
            <header className="flex items-start justify-between gap-4">
              <h2
                id="gap-report-title"
                className="text-heading-3 font-announce text-text-primary"
              >
                Gap Analytics Report
              </h2>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setReport(null)}
                aria-label="Close"
              >
                Close
              </button>
            </header>
            <div>
              <h3 className="mb-2 text-heading-3 font-announce text-text-primary">
                Summary
              </h3>
              <p className="whitespace-pre-line text-small text-text-secondary">
                {report.narrative}
              </p>
            </div>
            {report.warnings.map((warning) => (
              <Banner key={warning} kind="info">{warning}</Banner>
            ))}
            <details className="rounded-comfy border border-border-secondary bg-bg-deepest p-3">
              <summary className="cursor-pointer text-body font-signature text-text-primary">
                Method details
              </summary>
              <p className="mt-1 text-caption text-text-secondary">
                Global {(report.weighting.global_weight * 100).toFixed(0)}% · Peer{" "}
                {(report.weighting.peer_weight * 100).toFixed(0)}%. Evidence is ranked
                within its own source before the source weight is applied.
              </p>
              <p className="mt-1 text-caption text-status-amber">
                Pending faculty UAT · {report.weighting.interpretation}
              </p>
            </details>
            <div>
              <h3 className="mb-2 text-heading-3 font-announce text-text-primary">
                Aggregated review priority
              </h3>
              {report.white_spaces.length === 0 ? (
                <EmptyState text="No coverage evidence is available." />
              ) : (
                <ol className="divide-y divide-border-secondary">
                  {report.white_spaces.map((item, idx) => (
                    <li key={`${item.source}-${item.domain_label}-${idx}`} className="py-4 first:pt-0">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="text-caption uppercase tracking-wide text-text-quaternary">
                            #{idx + 1} · {item.source} evidence
                          </p>
                          <p className="font-signature text-text-primary">{item.domain_label}</p>
                        </div>
                        <p className="text-caption text-status-amber">
                          Pending administrator review
                        </p>
                      </div>
                      {item.nearest_staff_name && (
                        <p className="mt-2 text-caption text-text-tertiary">
                          Closest staff expertise: <span className="text-text-secondary">{item.nearest_staff_name}</span>
                        </p>
                      )}
                      <details className="mt-2 text-caption text-text-tertiary">
                        <summary className="cursor-pointer">Method and source details</summary>
                        <dl className="mt-1 grid gap-1 sm:grid-cols-2">
                          <div><dt className="inline">Weighted priority: </dt><dd className="inline text-text-secondary">{item.weighted_priority_score.toFixed(3)}</dd></div>
                          <div><dt className="inline">Relative priority × source weight: </dt><dd className="inline text-text-secondary">{item.source_relative_priority.toFixed(3)} × {item.source_weight.toFixed(2)}</dd></div>
                          <div><dt className="inline">Raw coverage distance: </dt><dd className="inline text-text-secondary">{item.displacement_score.toFixed(3)}</dd></div>
                          <div><dt className="inline">Nearest internal cluster: </dt><dd className="inline text-text-secondary">{item.nearest_cluster_label ?? "Unavailable"}</dd></div>
                          {item.external_source_id && <div><dt className="inline">OpenAlex source: </dt><dd className="inline text-text-secondary">{item.external_source_id}{item.external_subfield ? ` · ${item.external_subfield}` : ""}</dd></div>}
                          {item.peer_filename && <div><dt className="inline">Peer source: </dt><dd className="inline text-text-secondary">{item.peer_filename}{item.detected_section ? ` · ${item.detected_section}` : ""}</dd></div>}
                        </dl>
                      </details>
                      {item.source_excerpt && (
                        <p className="mt-2 whitespace-pre-line rounded-comfy bg-bg-deepest p-2 text-caption text-text-secondary">
                          {item.source_excerpt}
                        </p>
                      )}
                      {item.recommendation && <p className="mt-2 text-caption text-text-tertiary">{item.recommendation}</p>}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// UC-15 + UC-16 — individual run + UMAP scatter
// ---------------------------------------------------------------------------

export function GlobalBenchmarkingPage() {
  const [run, setRun] = useState<BenchmarkRun | null>(null);
  const [peerFiles, setPeerFiles] = useState<File[]>([]);
  const [peerPreview, setPeerPreview] = useState<DocumentPreview | null>(null);
  const [selectedSections, setSelectedSections] = useState<Set<string>>(new Set());
  const [coverageConfirmed, setCoverageConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function runGlobal() {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const { data } = await api.post<BenchmarkRun>("/benchmarking/global");
      setRun(data);
      setInfo("Global benchmark completed.");
    } catch (err) {
      setError(extractApiError(err, "Global benchmark failed."));
    } finally {
      setBusy(false);
    }
  }

  async function previewPeer() {
    if (peerFiles.length === 0) {
      setError("Upload at least one peer curriculum document.");
      return;
    }
    if (peerFiles.length > 8) {
      setError("Upload at most 8 peer curriculum files per analysis.");
      return;
    }
    if (peerFiles.some((file) => file.size > 10 * 1024 * 1024)) {
      setError("Each peer curriculum file must not exceed 10 MiB.");
      return;
    }
    if (peerFiles.reduce((total, file) => total + file.size, 0) > 25 * 1024 * 1024) {
      setError("The combined peer upload must not exceed 25 MiB.");
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const fd = new FormData();
      peerFiles.forEach((f) => fd.append("files", f));
      const { data } = await api.post<DocumentPreview>("/benchmarking/peer/preview", fd);
      setPeerPreview(data);
      setSelectedSections(new Set(data.sections.filter((s) => s.included_by_default).map((s) => s.id)));
      setInfo("Review the extracted programme sections before analysis.");
    } catch (err) {
      setError(extractApiError(err, "Peer document preview failed."));
    } finally { setBusy(false); }
  }

  async function runPeer() {
    if (!peerPreview || selectedSections.size === 0 || getDocumentSelectionUsage(peerPreview, selectedSections).exceeds) return;
    setBusy(true); setError(null); setInfo(null);
    try {
      const fd = new FormData();
      peerFiles.forEach((f) => fd.append("files", f));
      selectedSections.forEach((id) => fd.append("included_section_ids", id));
      fd.append("confirm_programme_coverage", String(coverageConfirmed));
      const { data } = await api.post<BenchmarkRun>("/benchmarking/peer", fd);
      setRun(data);
      setInfo("Peer comparison completed.");
    } catch (err) {
      setError(extractApiError(err, "Peer benchmark failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-heading-1 font-announce text-text-primary">
          Global &amp; Peer Benchmarking
        </h1>
      </header>

      {error && <Banner kind="error">{error}</Banner>}
      {info && <Banner kind="success">{info}</Banner>}

      <section className="card">
        <h2 className="text-heading-3 font-announce text-text-primary">
          Global Topic <C></C>overage
        </h2>
        <p className="mt-1 text-caption text-text-tertiary">
          Reviews current prominent OpenAlex Computer Science topics across
          every official subfield against internal staff capability clusters.
          This is a coverage review, not a short-term trend forecast.
        </p>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            className="btn-primary"
            onClick={runGlobal}
            disabled={busy}
          >
            {busy ? "Running…" : "Run global benchmark"}
          </button>
        </div>
      </section>

      <section className="card">
        <h2 className="text-heading-3 font-announce text-text-primary">
          Peer-institution upload
        </h2>
        <p className="mt-1 text-caption text-text-tertiary">
          Upload a complete programme curriculum, or a multi-document collection
          that covers the programme. A single course cannot support an
          institution-level gap claim. Maximum 8 files, 10 MiB each and 25 MiB
          combined. Review detected sections before analysis.
        </p>
        <div className="mt-3">
          <input
            type="file"
            accept=".pdf,.docx"
            multiple
            onChange={(e) => { setPeerFiles(Array.from(e.target.files ?? [])); setPeerPreview(null); setCoverageConfirmed(false); }}
            className="text-small text-text-secondary"
          />
        </div>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            className="btn-primary"
            onClick={peerPreview ? runPeer : previewPeer}
            disabled={busy || peerFiles.length === 0 || !!(peerPreview && (selectedSections.size === 0 || getDocumentSelectionUsage(peerPreview, selectedSections).exceeds)) || !!(peerPreview?.appears_single_course && !coverageConfirmed)}
          >
            {busy ? "Processing…" : peerPreview ? "Run with selected sections" : "Preview programme sections"}
          </button>
        </div>
        {peerPreview && <>
          <DocumentSectionPreview preview={peerPreview} selected={selectedSections} onChange={setSelectedSections} />
          {peerPreview.appears_single_course && <label className="mt-3 flex gap-2 text-small text-text-secondary">
            <input type="checkbox" checked={coverageConfirmed} onChange={(e) => setCoverageConfirmed(e.target.checked)} />
            I confirm these files adequately cover the programme. Results will remain potential gaps, not an institution-level conclusion from one course.
          </label>}
        </>}
      </section>

      {run && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="benchmark-run-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) setRun(null);
          }}
        >
          <section className="card w-full max-w-3xl max-h-[80vh] overflow-y-auto space-y-4 shadow-floating">
            <header className="flex items-start justify-between gap-4">
              <h2
                id="benchmark-run-title"
                className="text-heading-3 font-announce text-text-primary"
              >
                {run.benchmark_type === "global"
                  ? "Global benchmark results"
                  : "Peer comparison results"}
              </h2>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setRun(null)}
                aria-label="Close"
              >
                Close
              </button>
            </header>
            <div>
              <h3 className="mb-2 text-heading-3 font-announce text-text-primary">
                Summary
              </h3>
              <p className="whitespace-pre-line text-small text-text-secondary">
                {run.narrative ?? "No summary is available."}
              </p>
            </div>
            {run.benchmark_type === "global" && run.source_payload && (
              <details className="rounded-comfy bg-bg-deepest p-3 text-caption text-text-tertiary">
                <summary className="cursor-pointer font-signature text-text-secondary">
                  Method and source details
                </summary>
                <p>
                  {run.source_payload.provider ?? "OpenAlex"} · {run.source_payload.scope?.display_name ?? "Computer Science"}
                  {run.source_payload.retrieved_at ? ` · retrieved ${new Date(run.source_payload.retrieved_at).toLocaleString()}` : ""}
                </p>
                <p className="mt-1">
                  Two highest-output research topics per official subfield; article, review, book, and book-chapter records only. No time-series trend score.
                </p>
                {run.source_payload.embedding_model && <p className="mt-1">Embedding model: {run.source_payload.embedding_model}</p>}
              </details>
            )}
            {run.visualization_payload && (
              <div>
                <h3 className="mb-2 text-heading-3 font-announce text-text-primary">
                  Research Area Overview
                </h3>
                <p className="mb-2 text-caption text-text-tertiary">
                  A two-dimensional view of similarity between research areas.
                </p>
                <UmapScatter payload={run.visualization_payload} />
              </div>
            )}
            <div>
              <h3 className="mb-2 text-heading-3 font-announce text-text-primary">
                {run.benchmark_type === "peer"
                  ? "Potential Coverage Gaps"
                  : "Global Topic Coverage"}
              </h3>
              {run.white_spaces.length === 0 ? (
                <EmptyState
                  text={
                    run.benchmark_type === "peer"
                      ? "No potential coverage gaps were identified."
                      : "No global topic coverage results were produced."
                  }
                />
              ) : run.benchmark_type === "peer" ? (
                <PeerEvidenceList items={run.white_spaces} />
              ) : (
                <GlobalEvidenceList items={run.white_spaces} />
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function GlobalEvidenceList({ items }: { items: BenchmarkWhiteSpace[] }) {
  const [sort, setSort] = useState<"weaker_first" | "stronger_first" | "subfield">("weaker_first");
  const ordered = [...items].sort((a, b) => {
    if (sort === "subfield") {
      return `${a.external_subfield ?? ""}\0${a.domain_label}`.localeCompare(
        `${b.external_subfield ?? ""}\0${b.domain_label}`,
      );
    }
    return sort === "weaker_first"
      ? b.displacement_score - a.displacement_score
      : a.displacement_score - b.displacement_score;
  });

  return <div className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-caption text-text-tertiary">
        Higher distance means weaker semantic alignment, not an automatic staffing or curriculum gap. All results require administrator review.
      </p>
      <label className="text-caption text-text-secondary">
        Sort{" "}
        <select className="rounded border border-border-secondary bg-bg-deepest p-1" value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}>
          <option value="weaker_first">Weaker coverage first</option>
          <option value="stronger_first">Stronger coverage first</option>
          <option value="subfield">Computer Science subfield</option>
        </select>
      </label>
    </div>
    <ul className="divide-y divide-border-secondary">
      {ordered.map((item, index) => <li key={`${item.external_source_id}-${index}`} className="py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-body font-signature text-text-primary">{item.domain_label}</span>
          <span className="text-caption text-status-amber">Pending administrator review</span>
        </div>
        <p className="mt-1 text-caption text-text-tertiary">
          {item.external_subfield ?? "Computer Science"}
          {item.external_works_count == null ? "" : ` · ${item.external_works_count.toLocaleString()} research outputs`}
        </p>
        {item.source_excerpt && <p className="mt-2 text-small text-text-secondary">{item.source_excerpt}</p>}
        <details className="mt-2 text-caption text-text-tertiary">
          <summary className="cursor-pointer">Method and source details</summary>
          <dl className="mt-1 grid gap-1 sm:grid-cols-2">
            <div><dt className="inline">Raw coverage distance: </dt><dd className="inline text-text-secondary">{item.displacement_score.toFixed(3)}</dd></div>
            <div><dt className="inline">Nearest internal cluster: </dt><dd className="inline text-text-secondary">{item.nearest_cluster_label ?? "Unavailable"}</dd></div>
            <div><dt className="inline">OpenAlex source: </dt><dd className="inline text-text-secondary">{item.external_source_id ?? "Unavailable"}</dd></div>
            <div><dt className="inline">OpenAlex topic updated: </dt><dd className="inline text-text-secondary">{item.external_updated_date ?? "Unavailable"}</dd></div>
          </dl>
        </details>
      </li>)}
    </ul>
  </div>;
}

function PeerEvidenceList({ items }: { items: BenchmarkWhiteSpace[] }) {
  const [sort, setSort] = useState<"gap_first" | "covered_first" | "file">("gap_first");
  const ordered = [...items].sort((a, b) => {
    if (sort === "file") {
      return `${a.peer_filename ?? ""}\0${a.detected_section ?? ""}`.localeCompare(
        `${b.peer_filename ?? ""}\0${b.detected_section ?? ""}`,
      );
    }
    return sort === "gap_first"
      ? b.displacement_score - a.displacement_score
      : a.displacement_score - b.displacement_score;
  });
  const label = (value: BenchmarkWhiteSpace["coverage_classification"]) =>
    value === "candidate_gap" ? "Potential gap"
      : value === "partially_covered" ? "Partially covered"
      : value === "covered" ? "Covered" : "Unclassified";

  return <div className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-caption text-text-tertiary">
        All {items.length} selected sections are shown with equal weight. Results
        are indicative and require administrator review.
      </p>
      <label className="text-caption text-text-secondary">
        Sort{" "}
        <select className="rounded border border-border-secondary bg-bg-deepest p-1" value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}>
          <option value="gap_first">Potential gaps first</option>
          <option value="covered_first">Covered first</option>
          <option value="file">Filename and section</option>
        </select>
      </label>
    </div>
    <ul className="divide-y divide-border-secondary">
      {ordered.map((item, index) => <li key={`${item.peer_filename}-${item.detected_section}-${index}`} className="py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-body font-signature text-text-primary">{label(item.coverage_classification)}</span>
          <span className="text-caption text-status-amber">Pending administrator review</span>
        </div>
        <p className="mt-1 text-small text-text-secondary">
          {item.peer_filename} · {item.detected_section}
        </p>
        <p className="mt-2 whitespace-pre-line rounded-comfy bg-bg-deepest p-2 text-caption text-text-secondary">
          {item.source_excerpt}
        </p>
        <p className="mt-2 text-caption text-text-tertiary">
          Closest staff expertise:{" "}
          <span className="text-text-secondary">
            {item.nearest_staff_name ?? "Unavailable"}
          </span>
        </p>
        <details className="mt-2 text-caption text-text-tertiary">
          <summary className="cursor-pointer">Method details</summary>
          <dl className="mt-1 grid gap-1 sm:grid-cols-2">
            <div><dt className="inline">Raw coverage distance: </dt><dd className="inline text-text-secondary">{item.displacement_score.toFixed(3)}</dd></div>
            <div><dt className="inline">Nearest cluster: </dt><dd className="inline text-text-secondary">{item.nearest_cluster_label ?? "Unavailable"}{item.nearest_cluster_distance == null ? "" : ` (${item.nearest_cluster_distance.toFixed(3)})`}</dd></div>
            <div><dt className="inline">Calibration: </dt><dd className="inline text-text-secondary">Synthetic development dataset</dd></div>
          </dl>
        </details>
      </li>)}
    </ul>
  </div>;
}

// ---------------------------------------------------------------------------
// Lightweight SVG scatter — no third-party charting dependency required.
// ---------------------------------------------------------------------------

function UmapScatter({ payload }: { payload: VisualizationPayload }) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const points = payload.points ?? [];

  if (points.length === 0) {
    return <EmptyState text="No visualization points." />;
  }

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const width = 720;
  const height = 360;
  const pad = 24;

  const scaleX = (x: number) =>
    pad + ((x - minX) / Math.max(maxX - minX, 1e-9)) * (width - 2 * pad);
  const scaleY = (y: number) =>
    height - pad - ((y - minY) / Math.max(maxY - minY, 1e-9)) * (height - 2 * pad);

  const colorFor = (kind: string) =>
    kind === "internal"
      ? "#7170ff"
      : kind === "global"
      ? "#27a644"
      : "#828fff";

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        className="w-full rounded-comfy border border-border-secondary bg-bg-deepest"
        onMouseLeave={() => setHover(null)}
      >
        {points.map((p, idx) => (
          <circle
            key={idx}
            cx={scaleX(p.x)}
            cy={scaleY(p.y)}
            r={4}
            fill={colorFor(p.kind)}
            opacity={0.85}
            onMouseEnter={() => setHover(`${p.kind}: ${p.label}`)}
          />
        ))}
      </svg>
      <div className="mt-2 flex items-center gap-4 text-caption text-text-tertiary">
        <Legend color="#7170ff" label="Internal" />
        <Legend color="#27a644" label="OpenAlex topic" />
        <Legend color="#828fff" label="Peer" />
        {hover && <span className="ml-auto text-text-secondary">{hover}</span>}
      </div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}
