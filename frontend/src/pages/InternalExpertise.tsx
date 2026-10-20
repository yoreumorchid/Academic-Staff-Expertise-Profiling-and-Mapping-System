import { useEffect, useState } from "react";
import { api, extractApiError } from "../api/client";
import type { InternalExpertiseOverview } from "../types";
import { Banner, EmptyState } from "./Profile";

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function shortLabel(label: string): string {
  return label.length > 34 ? `${label.slice(0, 31)}...` : label;
}

function OverviewMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-bg-panel px-4 py-3">
      <dt className="text-label uppercase tracking-wide text-text-quaternary">{label}</dt>
      <dd className="mt-1 text-heading-3 font-announce text-text-primary">{value}</dd>
    </div>
  );
}

function ExpertiseAreaChart({ overview }: { overview: InternalExpertiseOverview }) {
  const [hover, setHover] = useState<string | null>(null);
  const areas = overview.areas;
  const width = 900;
  const left = 250;
  const right = 150;
  const top = 28;
  const bottom = 46;
  const rowHeight = 42;
  const height = top + bottom + areas.length * rowHeight;
  const chartWidth = width - left - right;
  const maxCount = Math.max(...areas.map((area) => area.staff_count), 1);
  const tickStep = Math.max(1, Math.ceil(maxCount / 5));
  const axisMax = Math.ceil(maxCount / tickStep) * tickStep;
  const ticks = Array.from(
    { length: axisMax / tickStep + 1 },
    (_, index) => index * tickStep,
  );
  const xFor = (value: number) => left + (value / axisMax) * chartWidth;

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full rounded-comfy bg-bg-deepest"
        role="img"
        aria-label="Horizontal bar chart showing staff coverage by expertise area"
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((tick) => {
          const x = xFor(tick);
          return (
            <g key={tick}>
              <line x1={x} y1={top - 8} x2={x} y2={height - bottom} stroke="#e1e4ea" />
              <text x={x} y={height - 25} textAnchor="middle" fontSize="12" fill="#6b7079">
                {tick}
              </text>
            </g>
          );
        })}
        <text x={width - right} y={height - 6} textAnchor="end" fontSize="12" fill="#6b7079">
          Number of staff profiles
        </text>
        {areas.map((area, index) => {
          const y = top + index * rowHeight;
          const barWidth = (area.staff_count / axisMax) * chartWidth;
          const detail = `${area.label}: ${area.staff_count} staff across ${area.department_count} department${area.department_count === 1 ? "" : "s"}`;
          return (
            <g
              key={area.label}
              tabIndex={0}
              aria-label={detail}
              onMouseEnter={() => setHover(detail)}
              onFocus={() => setHover(detail)}
              onBlur={() => setHover(null)}
            >
              <title>{detail}</title>
              <text x={left - 14} y={y + 21} textAnchor="end" fontSize="13" fill="#3d4148">
                {shortLabel(area.label)}
              </text>
              <rect x={left} y={y + 7} width={barWidth} height={22} rx={5} fill="#3b784b" fillOpacity={0.9} />
              <text x={Math.min(left + barWidth + 10, width - right + 8)} y={y + 22} fontSize="12" fontWeight="600" fill="#3d4148">
                {area.staff_count} staff ({area.department_count} dept)
              </text>
            </g>
          );
        })}
      </svg>
      <p className="mt-2 min-h-5 text-caption text-text-secondary">
        {hover ?? "Hover or focus a bar for its full coverage summary."}
      </p>
    </div>
  );
}

export function InternalExpertisePanel({ embedded = false }: { embedded?: boolean }) {
  const [overview, setOverview] = useState<InternalExpertiseOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api.get<InternalExpertiseOverview>("/expertise/internal")
      .then(({ data }) => {
        if (active) setOverview(data);
      })
      .catch((err) => {
        if (active) setError(extractApiError(err, "Could not load the expertise overview."));
      });
    return () => { active = false; };
  }, []);

  if (error) return <Banner kind="error">{error}</Banner>;
  if (!overview) {
    return <div className="card text-small text-text-tertiary">Loading expertise overview…</div>;
  }

  const usableShare = overview.total_academic_staff
    ? overview.profiles_with_usable_expertise / overview.total_academic_staff
    : 0;
  const leadingArea = overview.areas[0] ?? null;
  const broadestArea = overview.areas.reduce(
    (best, area) => !best || area.department_count > best.department_count ? area : best,
    overview.areas[0] ?? null,
  );

  return (
    <section className="space-y-4">
      <h2 className={`${embedded ? "text-heading-3" : "text-heading-2"} font-announce text-text-primary`}>
        Faculty Expertise Overview
      </h2>

      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-card border border-border-secondary bg-border-secondary shadow-subtle lg:grid-cols-4">
        <OverviewMetric label="Academic staff" value={overview.total_academic_staff} />
        <OverviewMetric label="Departments" value={overview.total_departments} />
        <OverviewMetric label="Profile coverage" value={percent(usableShare)} />
        <OverviewMetric label="Expertise areas" value={overview.total_expertise_areas} />
      </dl>

      {overview.areas.length === 0 ? (
        <div className="card">
          <EmptyState text="No validated or sufficiently confident expertise areas are available yet." />
        </div>
      ) : (
        <>
          <div className="card space-y-3">
            <div>
              <h3 className="text-heading-3 font-announce text-text-primary">Most represented expertise areas</h3>
              <p className="text-caption text-text-tertiary">
                The chart can show up to the 12 most represented areas.
              </p>
            </div>
            <ExpertiseAreaChart overview={overview} />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="card">
              <div className="text-label uppercase tracking-wide text-text-quaternary">Widest staff coverage</div>
              <div className="mt-2 font-signature text-text-primary">{leadingArea?.label}</div>
              <p className="mt-1 text-caption text-text-tertiary">
                {leadingArea?.staff_count} staff ({leadingArea?.department_count} dept)
              </p>
            </div>
            <div className="card">
              <div className="text-label uppercase tracking-wide text-text-quaternary">Broadest department reach</div>
              <div className="mt-2 font-signature text-text-primary">{broadestArea?.label}</div>
              <p className="mt-1 text-caption text-text-tertiary">
                Present across {broadestArea?.department_count ?? 0} departments
              </p>
            </div>
            <div className="card">
              <div className="text-label uppercase tracking-wide text-text-quaternary">Profile data gap</div>
              <div className="mt-2 font-signature text-text-primary">{overview.profiles_without_usable_expertise} profiles</div>
              <p className="mt-1 text-caption text-text-tertiary">
                Active staff without usable expertise data for this overview
              </p>
            </div>
          </div>
        </>
      )}

    </section>
  );
}

