/**
 * UC-15 / UC-16 / UC-17 — Benchmarking & gap analytics.
 *
 * GapAnalyticsPage runs the combined report (which internally references
 * the most recent global + peer runs).
 * GlobalBenchmarkingPage focuses on UC-15 alone and exposes a peer
 * upload area for UC-16.
 */
import { useEffect, useRef, useState } from "react";
import { api, extractApiError } from "../api/client";
import type {
  BenchmarkRun,
  GapAnalysisReport,
  VisualizationPayload,
} from "../types";
import { Banner, EmptyState } from "./Profile";

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

      {report ? (
        <>
          <section className="card">
            <h2 className="mb-3 text-heading-3 font-announce text-text-primary">
              Narrative
            </h2>
            <p className="whitespace-pre-line text-small text-text-secondary">
              {report.narrative}
            </p>
          </section>
          <section className="card">
            <h2 className="mb-3 text-heading-3 font-announce text-text-primary">
              White spaces
            </h2>
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
          </section>
        </>
      ) : (
        <section className="card">
          <EmptyState text="Click 'Generate combined report' to consolidate the latest benchmark runs." />
        </section>
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

  async function runPeer() {
    if (peerFiles.length === 0) {
      setError("Upload at least one peer curriculum document.");
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const fd = new FormData();
      peerFiles.forEach((f) => fd.append("files", f));
      const { data } = await api.post<BenchmarkRun>(
        "/benchmarking/peer",
        fd,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
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
          Upload one or more PDF/DOCX curriculum documents from peer
          institutions.
        </p>
        <div className="mt-3">
          <input
            type="file"
            accept=".pdf,.docx"
            multiple
            onChange={(e) => setPeerFiles(Array.from(e.target.files ?? []))}
            className="text-small text-text-secondary"
          />
        </div>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            className="btn-primary"
            onClick={runPeer}
            disabled={busy || peerFiles.length === 0}
          >
            {busy ? "Running…" : "Run peer benchmark"}
          </button>
        </div>
      </section>

      {run && (
        <>
          <section className="card">
            <h2 className="mb-3 text-heading-3 font-announce text-text-primary">
              Narrative — {run.benchmark_type} run
            </h2>
            <p className="whitespace-pre-line text-small text-text-secondary">
              {run.narrative ?? "No narrative produced."}
            </p>
          </section>

          {run.visualization_payload && (
            <section className="card">
              <h2 className="mb-3 text-heading-3 font-announce text-text-primary">
                UMAP projection
              </h2>
              <UmapScatter payload={run.visualization_payload} />
            </section>
          )}

          <section className="card">
            <h2 className="mb-3 text-heading-3 font-announce text-text-primary">
              White spaces
            </h2>
            {run.white_spaces.length === 0 ? (
              <EmptyState text="No white spaces flagged." />
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
          </section>
        </>
      )}
    </div>
  );
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
