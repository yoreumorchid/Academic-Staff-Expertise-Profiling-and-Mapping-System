/**
 * UC-15 / UC-16 / UC-17 — Benchmarking & gap analytics.
 *
 * GapAnalyticsPage runs the combined report (which internally references
 * the most recent global + peer runs).
 * GlobalBenchmarkingPage focuses on UC-15 alone and exposes a peer
 * upload area for UC-16.
 */
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, extractApiError } from "../api/client";
import type {
  BenchmarkRun,
  BenchmarkHistory,
  BenchmarkRunSummary,
  BenchmarkWhiteSpace,
  DocumentPreview,
  GapAnalysisReport,
  VisualizationPayload,
} from "../types";
import { Banner, EmptyState } from "./Profile";
import { DocumentSectionPreview, getDocumentSelectionUsage } from "./DocumentSectionPreview";
import { MarkdownSummary } from "../components/MarkdownSummary";

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
          <p className="mt-2 max-w-3xl text-small text-text-secondary">
            Uses the newest saved Global coverage report. Peer curriculum overviews remain descriptive and are not scored as gaps.
          </p>
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

      <section className="card p-6">
        <h2 className="text-heading-3 font-announce text-text-primary">How the combined report works</h2>
        <div className="mt-4 grid gap-5 text-small text-text-secondary md:grid-cols-3">
          <div>
            <p className="font-signature text-text-primary">1. Selects evidence</p>
            <p className="mt-1">Uses the latest retained Global report available when you click Generate.</p>
          </div>
          <div>
            <p className="font-signature text-text-primary">2. Ranks Global coverage</p>
            <p className="mt-1">Orders OpenAlex topics by weaker internal capability alignment. This is review priority, not proven gap severity.</p>
          </div>
          <div>
            <p className="font-signature text-text-primary">3. Keeps Peer separate</p>
            <p className="mt-1">Peer uploads provide a curriculum overview only. They will enter Gap Analytics only after a faculty-validated alignment method exists.</p>
          </div>
        </div>
        <p className="mt-5 text-caption text-text-tertiary">
          Generate again after a new benchmark run to use the newer report. An already-open combined report does not update itself.
        </p>
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
              <MarkdownSummary>{report.narrative}</MarkdownSummary>
            </div>
            {report.warnings.map((warning) => (
              <Banner key={warning} kind="info">{warning}</Banner>
            ))}
            <details className="rounded-comfy border border-border-secondary bg-bg-deepest p-4">
              <summary className="cursor-pointer text-body font-signature text-text-primary">
                Method details
              </summary>
              <p className="mt-1 text-caption text-text-secondary">
                Global coverage evidence only. Peer curriculum overview is excluded from scoring.
              </p>
              <p className="mt-1 text-caption text-status-amber">
                Pending faculty UAT · {report.weighting.interpretation}
              </p>
              <dl className="mt-3 grid gap-2 text-caption sm:grid-cols-2">
                <div>
                  <dt className="text-text-tertiary">Global report used</dt>
                  <dd className="text-text-secondary">
                    {report.global_run_created_at ? new Date(report.global_run_created_at).toLocaleString() : "Not available"}
                  </dd>
                </div>
                <div>
                  <dt className="text-text-tertiary">Peer curriculum overview</dt>
                  <dd className="text-text-secondary">Not used in Gap Analytics scoring</dd>
                </div>
              </dl>
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
  const navigate = useNavigate();
  const [peerFiles, setPeerFiles] = useState<File[]>([]);
  const [peerPreview, setPeerPreview] = useState<DocumentPreview | null>(null);
  const [selectedSections, setSelectedSections] = useState<Set<string>>(new Set());
  const [history, setHistory] = useState<BenchmarkHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [activeOperation, setActiveOperation] = useState<"global" | "peer_preview" | "peer" | null>(null);

  const busy = activeOperation !== null;
  const globalLimitReached = history !== null
    && history.global_runs_today >= history.global_daily_limit;

  async function loadHistory() {
    try {
      const { data } = await api.get<BenchmarkHistory>("/benchmarking/history");
      setHistory(data);
    } catch (err) {
      setError(extractApiError(err, "Benchmark report history could not be loaded."));
    }
  }

  useEffect(() => {
    void loadHistory();
  }, []);

  async function runGlobal() {
    setActiveOperation("global");
    setError(null);
    setInfo(null);
    try {
      const { data } = await api.post<BenchmarkRun>("/benchmarking/global");
      await loadHistory();
      navigate(`/admin/benchmarking/reports/${data.id}`);
    } catch (err) {
      setError(extractApiError(err, "Global benchmark failed."));
    } finally {
      setActiveOperation(null);
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
      setError("The total Peer upload must not exceed 25 MiB.");
      return;
    }
    setActiveOperation("peer_preview");
    setError(null);
    setInfo(null);
    try {
      const fd = new FormData();
      peerFiles.forEach((f) => fd.append("files", f));
      const { data } = await api.post<DocumentPreview>("/benchmarking/peer/preview", fd);
      setPeerPreview(data);
      setSelectedSections(new Set(data.sections.filter((s) => s.included_by_default).map((s) => s.id)));
      setInfo("Review the extracted academic sections before creating the overview.");
    } catch (err) {
      setError(extractApiError(err, "Peer document preview failed."));
    } finally { setActiveOperation(null); }
  }

  async function runPeer() {
    if (!peerPreview || selectedSections.size === 0 || getDocumentSelectionUsage(peerPreview, selectedSections).exceeds) return;
    setActiveOperation("peer"); setError(null); setInfo(null);
    try {
      const fd = new FormData();
      peerFiles.forEach((f) => fd.append("files", f));
      selectedSections.forEach((id) => fd.append("included_section_ids", id));
      const { data } = await api.post<BenchmarkRun>("/benchmarking/peer", fd);
      await loadHistory();
      navigate(`/admin/benchmarking/reports/${data.id}`);
    } catch (err) {
      setError(extractApiError(err, "Peer curriculum overview failed."));
    } finally {
      setActiveOperation(null);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-heading-1 font-announce text-text-primary">
          Global Benchmarking &amp; Peer Overview
        </h1>
      </header>

      {error && <Banner kind="error">{error}</Banner>}
      {info && <Banner kind="success">{info}</Banner>}
      {activeOperation && (
        <Banner kind="info">
          {activeOperation === "global"
            ? "Running Global Benchmark… Stay on this page; the report will open automatically when it is ready."
            : activeOperation === "peer_preview"
              ? "Processing the uploaded curriculum… Reviewable sections will appear here when ready."
              : "Creating Peer Curriculum Overview… Stay on this page; the overview will open automatically when it is ready."}
        </Banner>
      )}

      <div className="grid items-stretch gap-6 xl:grid-cols-2">
      <section className="card flex h-full flex-col p-6">
        <h2 className="text-heading-3 font-announce text-text-primary">
          Global Topic Coverage
        </h2>
        <p className="mt-2 text-small text-text-secondary">
          Compare prominent OpenAlex Computer Science topics with current internal capability clusters.
        </p>
        <p className="mt-2 text-caption text-text-tertiary">
          Coverage evidence only
        </p>
        <div className="mt-auto flex justify-end pt-6">
          <button
            type="button"
            className="btn-primary"
            onClick={runGlobal}
            disabled={busy || globalLimitReached}
          >
            {activeOperation === "global" ? "Running global benchmark…" : "Run global benchmark"}
          </button>
        </div>
        {history && (
          <p className="mt-3 text-right text-caption text-text-tertiary">
            {history.global_runs_today} of {history.global_daily_limit} runs used today
            {globalLimitReached ? ". The limit resets tomorrow." : "."}
          </p>
        )}
      </section>

      <section className="card flex h-full flex-col p-6">
        <h2 className="text-heading-3 font-announce text-text-primary">
          Peer Curriculum Overview
        </h2>
        <p className="mt-2 text-small text-text-secondary">
          Extract reviewable academic content from peer curriculum documents without scoring staff or claiming gaps.
        </p>
        <p className="mt-2 text-caption text-text-tertiary">
          Up to 8 PDF or DOCX files.  Max 10 MB for each file and 25 MB total
        </p>
        <div className="mt-4">
          <input
            type="file"
            accept=".pdf,.docx"
            multiple
            onChange={(e) => { setPeerFiles(Array.from(e.target.files ?? [])); setPeerPreview(null); }}
            className="text-small text-text-secondary"
          />
        </div>
        <div className="mt-auto flex justify-end pt-6">
          <button
            type="button"
            className="btn-primary"
            onClick={peerPreview ? runPeer : previewPeer}
            disabled={busy || peerFiles.length === 0 || !!(peerPreview && (selectedSections.size === 0 || getDocumentSelectionUsage(peerPreview, selectedSections).exceeds))}
          >
            {activeOperation === "peer_preview"
              ? "Processing curriculum…"
              : activeOperation === "peer"
                ? "Creating curriculum overview…"
                : peerPreview ? "Create overview from selected sections" : "Preview curriculum sections"}
          </button>
        </div>
        {peerPreview && <>
          <DocumentSectionPreview preview={peerPreview} selected={selectedSections} onChange={setSelectedSections} />
        </>}
      </section>
      </div>

      <section className="card p-6">
        <div className="mb-5">
          <h2 className="text-heading-3 font-announce text-text-primary">Recent reports</h2>
          <p className="mt-1 text-caption text-text-tertiary">
            The latest five reports of each type are retained. Reports open in a new tab.
          </p>
        </div>
        {history === null ? (
          <p className="text-small text-text-tertiary">Loading report history…</p>
        ) : (
          <div className="grid gap-8 lg:grid-cols-2">
            <ReportHistory title="Global benchmarks" runs={history.global_runs} />
            <ReportHistory title="Peer curriculum overviews" runs={history.peer_runs} />
          </div>
        )}
      </section>
    </div>
  );
}

function ReportHistory({ title, runs }: { title: string; runs: BenchmarkRunSummary[] }) {
  return (
    <div>
      <h3 className="font-signature text-text-primary">{title}</h3>
      {runs.length === 0 ? (
        <p className="mt-3 text-caption text-text-tertiary">No saved reports yet.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {runs.map((run) => (
            <li key={run.id}>
              <a
                href={`/admin/benchmarking/reports/${run.id}`}
                target="_blank"
                rel="noreferrer noopener"
                className="flex items-center justify-between gap-4 rounded-comfy border border-border-secondary p-3 hover:bg-bg-surface"
              >
                <span className="text-small text-text-secondary">
                  {new Date(run.created_at).toLocaleString()}
                </span>
                <span className="text-caption text-text-tertiary">{run.item_count} items</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function BenchmarkReportPage() {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<BenchmarkRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    api.get<BenchmarkRun>(`/benchmarking/runs/${runId}`)
      .then(({ data }) => setRun(data))
      .catch((err) => setError(extractApiError(err, "Benchmark report could not be loaded.")));
  }, [runId]);

  if (error) return <Banner kind="error">{error}</Banner>;
  if (!run) return <p className="text-small text-text-tertiary">Loading benchmark report…</p>;

  const isGlobal = run.benchmark_type === "global";
  return (
    <article className="mx-auto max-w-6xl space-y-8 pb-12">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-caption uppercase tracking-wide text-text-quaternary">
            {isGlobal ? "Global benchmark" : "Peer curriculum overview"}
          </p>
          <h1 className="mt-1 text-heading-1 font-announce text-text-primary">
            {isGlobal ? "Global Topic Coverage" : "Peer Curriculum Overview"}
          </h1>
          <p className="mt-2 text-caption text-text-tertiary">
            Generated {new Date(run.created_at).toLocaleString()}
          </p>
        </div>
        <Link to="/admin/benchmarking/global" className="btn-ghost">Back to benchmarking</Link>
      </header>

      {isGlobal && run.source_payload && <GlobalMethodSummary run={run} />}
      {!isGlobal && run.source_payload && (
        <section className="card p-6">
          <h2 className="text-heading-3 font-announce text-text-primary">Interpretation boundary</h2>
          <p className="mt-2 text-small text-text-secondary">
            {run.source_payload.interpretation ?? "Descriptive curriculum overview only. No staff comparison or gap classification is used."}
          </p>
        </section>
      )}

      {run.visualization_payload && (
        <section className="card p-6">
          <h2 className="text-heading-3 font-announce text-text-primary">Research Area Overview</h2>
          <p className="mb-4 mt-1 text-caption text-text-tertiary">
            A two-dimensional exploratory view of similarity between research areas.
          </p>
          <UmapScatter payload={run.visualization_payload} />
        </section>
      )}

      <section className="card p-6">
        <h2 className="mb-5 text-heading-3 font-announce text-text-primary">
          {isGlobal ? "Global Topic Coverage" : "Selected Curriculum Content"}
        </h2>
        {run.white_spaces.length === 0 ? (
          <EmptyState text={isGlobal ? "No global topic coverage results were produced." : "No academic curriculum sections were retained."} />
        ) : isGlobal ? (
          <GlobalEvidenceList items={run.white_spaces} />
        ) : (
          <PeerEvidenceList items={run.white_spaces} />
        )}
      </section>
    </article>
  );
}

function GlobalMethodSummary({ run }: { run: BenchmarkRun }) {
  const source = run.source_payload;
  if (!source) return null;
  const selection = source.selection;
  return (
    <section className="card p-6">
      <h2 className="text-heading-3 font-announce text-text-primary">Source and method</h2>
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-small text-text-secondary">
        <span>{source.provider ?? "OpenAlex"}</span>
        <span>{source.scope?.display_name ?? "Computer Science"}</span>
        {source.retrieved_at && <span>Retrieved {new Date(source.retrieved_at).toLocaleString()}</span>}
      </div>
      <dl className="mt-5 grid gap-x-8 gap-y-4 text-caption sm:grid-cols-2 lg:grid-cols-3">
        <div><dt className="text-text-tertiary">Topic selection</dt><dd className="mt-1 text-text-secondary">Top {selection?.topics_per_subfield ?? 2} research-output topics per official subfield</dd></div>
        <div><dt className="text-text-tertiary">Included work types</dt><dd className="mt-1 text-text-secondary">{selection?.work_types?.join(", ") ?? "Article, review, book, book chapter"}</dd></div>
        <div><dt className="text-text-tertiary">Embedding model</dt><dd className="mt-1 break-words text-text-secondary">{source.embedding_model ?? "Unavailable"}</dd></div>
        <div><dt className="text-text-tertiary">Comparison</dt><dd className="mt-1 text-text-secondary">{source.distance_formula ?? "Cosine distance to nearest internal cluster"}</dd></div>
        <div><dt className="text-text-tertiary">Trend analysis</dt><dd className="mt-1 text-text-secondary">Not used</dd></div>
        <div><dt className="text-text-tertiary">Interpretation</dt><dd className="mt-1 text-text-secondary">{source.interpretation ?? "Administrator review required"}</dd></div>
      </dl>
    </section>
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
      ? (b.displacement_score ?? 0) - (a.displacement_score ?? 0)
      : (a.displacement_score ?? 0) - (b.displacement_score ?? 0);
  });

  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-4">
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
    <ul className="space-y-4">
      {ordered.map((item, index) => <li key={`${item.external_source_id}-${index}`} className="rounded-card border border-border-secondary bg-bg-deepest p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-body font-signature text-text-primary">{item.domain_label}</span>
          <span className="text-caption text-status-amber">Pending administrator review</span>
        </div>
        <p className="mt-1 text-caption text-text-tertiary">
          {item.external_subfield ?? "Computer Science"}
          {item.external_works_count == null ? "" : ` · ${item.external_works_count.toLocaleString()} research outputs`}
        </p>
        {item.source_excerpt && <p className="mt-3 leading-relaxed text-small text-text-secondary">{item.source_excerpt}</p>}
        <div className="mt-4 border-t border-border-secondary pt-4 text-caption text-text-tertiary">
          <h4 className="font-signature text-text-secondary">Method and source details</h4>
          <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2">
            <div><dt className="inline">Raw coverage distance: </dt><dd className="inline text-text-secondary">{item.displacement_score?.toFixed(3) ?? "Unavailable"}</dd></div>
            <div><dt className="inline">Nearest internal cluster: </dt><dd className="inline text-text-secondary">{item.nearest_cluster_label ?? "Unavailable"}</dd></div>
            <div><dt className="inline">OpenAlex source: </dt><dd className="inline text-text-secondary">{item.external_source_id ?? "Unavailable"}</dd></div>
            <div><dt className="inline">OpenAlex topic updated: </dt><dd className="inline text-text-secondary">{item.external_updated_date ?? "Unavailable"}</dd></div>
          </dl>
        </div>
      </li>)}
    </ul>
  </div>;
}

function PeerEvidenceList({ items }: { items: BenchmarkWhiteSpace[] }) {
  const ordered = [...items].sort((a, b) =>
    `${a.peer_filename ?? ""}\0${a.detected_section ?? ""}`.localeCompare(
      `${b.peer_filename ?? ""}\0${b.detected_section ?? ""}`,
    )
  );

  return <div className="space-y-4">
    <p className="text-small text-text-secondary">
      {items.length} academic sections retained from the uploaded material. Administrative sections were automatically excluded. No staff matching or gap classification was performed.
    </p>
    <ul className="space-y-4">
      {ordered.map((item, index) => <li key={`${item.peer_filename}-${item.detected_section}-${index}`} className="rounded-card border border-border-secondary bg-bg-deepest p-5">
        <p className="text-caption text-text-tertiary">{item.peer_filename}</p>
        <h3 className="mt-1 text-body font-signature text-text-primary">
          {item.detected_section ?? "Curriculum section"}
        </h3>
        <p className="mt-3 whitespace-pre-line leading-relaxed text-small text-text-secondary">
          {item.source_excerpt}
        </p>
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
