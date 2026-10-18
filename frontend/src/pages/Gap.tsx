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
                Narrative
              </h3>
              <p className="whitespace-pre-line text-small text-text-secondary">
                {report.narrative}
              </p>
            </div>
            <div>
              <h3 className="mb-2 text-heading-3 font-announce text-text-primary">
                White spaces
              </h3>
              {report.white_spaces.length === 0 ? (
                <EmptyState text="No white spaces flagged." />
              ) : (
                <table className="min-w-full divide-y divide-border-secondary text-small">
                  <thead className="text-caption uppercase tracking-wide text-text-quaternary">
                    <tr>
                      <th className="px-2 py-2 text-left font-signature">Source</th>
                      <th className="px-2 py-2 text-left font-signature">Domain</th>
                      <th className="px-2 py-2 text-right font-signature">
                        Displacement
                      </th>
                      <th className="px-2 py-2 text-left font-signature">Recommendation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-secondary">
                    {report.white_spaces.map((w, idx) => (
                      <tr key={`${w.source}-${idx}`}>
                        <td className="px-2 py-2 text-text-secondary">{w.source}</td>
                        <td className="px-2 py-2 text-text-primary">{w.domain_label}</td>
                        <td className="px-2 py-2 text-right text-text-secondary">
                          {w.displacement_score.toFixed(3)}
                        </td>
                        <td className="px-2 py-2 text-text-tertiary">
                          {w.recommendation ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
      setInfo(`Global run ${data.id.slice(0, 8)} completed.`);
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
      setInfo(`Peer run ${data.id.slice(0, 8)} completed.`);
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
          Global frontier
        </h2>
        <p className="mt-1 text-caption text-text-tertiary">
          Pulls eight benchmark queries from IEEE Xplore and clusters them
          against the internal corpus.
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
            I confirm these files adequately cover the programme. Results will remain candidate gaps, not an institution-level conclusion from one course.
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
                {run.benchmark_type} run results
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
                Narrative
              </h3>
              <p className="whitespace-pre-line text-small text-text-secondary">
                {run.narrative ?? "No narrative produced."}
              </p>
            </div>
            {run.visualization_payload && (
              <div>
                <h3 className="mb-2 text-heading-3 font-announce text-text-primary">
                  UMAP projection
                </h3>
                <UmapScatter payload={run.visualization_payload} />
              </div>
            )}
            <div>
              <h3 className="mb-2 text-heading-3 font-announce text-text-primary">
                {run.benchmark_type === "peer" ? "Candidate coverage evidence" : "White spaces"}
              </h3>
              {run.white_spaces.length === 0 ? (
                <EmptyState text={run.benchmark_type === "peer" ? "No candidate coverage evidence was produced." : "No white spaces flagged."} />
              ) : run.benchmark_type === "peer" ? (
                <PeerEvidenceList items={run.white_spaces} />
              ) : (
                <ul className="divide-y divide-border-secondary">
                  {run.white_spaces.map((w, idx) => (
                    <li key={idx} className="py-2">
                      <div className="flex items-center justify-between">
                        <span className="text-body text-text-primary">
                          {w.domain_label}
                        </span>
                        <span className="text-caption text-text-tertiary">
                          displacement {w.displacement_score.toFixed(3)}
                        </span>
                      </div>
                      {w.recommendation && (
                        <p className="mt-1 text-small text-text-secondary">
                          {w.recommendation}
                        </p>
                      )}
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
    value === "candidate_gap" ? "Candidate gap"
      : value === "partially_covered" ? "Partially covered"
      : value === "covered" ? "Covered" : "Unclassified";

  return <div className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-caption text-text-tertiary">
        All {items.length} retained segments are shown with equal weight. Classifications use a synthetic-development calibration and require administrator review.
      </p>
      <label className="text-caption text-text-secondary">
        Sort{" "}
        <select className="rounded border border-border-secondary bg-bg-deepest p-1" value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}>
          <option value="gap_first">Candidate gaps first</option>
          <option value="covered_first">Covered first</option>
          <option value="file">Filename and section</option>
        </select>
      </label>
    </div>
    <ul className="divide-y divide-border-secondary">
      {ordered.map((item, index) => <li key={`${item.peer_filename}-${item.detected_section}-${index}`} className="py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-body font-signature text-text-primary">{label(item.coverage_classification)}</span>
          <span className="text-caption text-text-tertiary">raw distance {item.displacement_score.toFixed(3)}</span>
        </div>
        <p className="mt-1 text-small text-text-secondary">
          {item.peer_filename} · {item.detected_section}
        </p>
        <p className="mt-2 whitespace-pre-line rounded-comfy bg-bg-deepest p-2 text-caption text-text-secondary">
          {item.source_excerpt}
        </p>
        <dl className="mt-2 grid gap-1 text-caption text-text-tertiary sm:grid-cols-2">
          <div><dt className="inline">Nearest staff: </dt><dd className="inline text-text-secondary">{item.nearest_staff_name ?? "Unavailable"}</dd></div>
          <div><dt className="inline">Nearest cluster: </dt><dd className="inline text-text-secondary">{item.nearest_cluster_label ?? "Unavailable"}{item.nearest_cluster_distance == null ? "" : ` (${item.nearest_cluster_distance.toFixed(3)})`}</dd></div>
        </dl>
        <p className="mt-2 text-caption text-status-amber">Pending administrator review</p>
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
        <Legend color="#27a644" label="Global frontier" />
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
