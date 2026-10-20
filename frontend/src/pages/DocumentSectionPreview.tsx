import type { DocumentPreview } from "../types";

export function getDocumentSelectionUsage(preview: DocumentPreview, selected: Set<string>) {
  const sections = preview.sections.filter((section) => selected.has(section.id));
  const sourceTokens = sections.reduce((total, section) => total + section.token_count, 0);
  const payload = Math.max(1, preview.chunk_max_tokens - preview.overlap_tokens);
  const estimatedChunks = sections.reduce((total, section) => {
    if (!section.token_count) return total;
    return total + 1 + Math.ceil(Math.max(0, section.token_count - preview.chunk_max_tokens) / payload);
  }, 0);
  return {
    sourceTokens,
    estimatedChunks,
    warning: sourceTokens >= preview.warning_source_tokens || estimatedChunks >= Math.ceil(preview.max_chunks * 0.8),
    exceeds: sourceTokens > preview.max_source_tokens || estimatedChunks > preview.max_chunks,
  };
}

export function DocumentSectionPreview({
  preview,
  selected,
  onChange,
}: {
  preview: DocumentPreview;
  selected: Set<string>;
  onChange: (selected: Set<string>) => void;
}) {
  const usage = getDocumentSelectionUsage(preview, selected);
  const filenames = [...new Set(preview.sections.map((section) => section.filename))];
  const toggleFile = (filename: string, include: boolean) => {
    const next = new Set(selected);
    preview.sections.filter((s) => s.filename === filename).forEach((s) => {
      if (include) next.add(s.id); else next.delete(s.id);
    });
    onChange(next);
  };
  return (
    <div className="mt-4 max-h-[28rem] space-y-3 overflow-y-auto rounded-comfy border border-border-secondary p-3">
      <div className={`text-caption ${usage.exceeds ? "text-status-red" : usage.warning ? "text-status-amber" : "text-text-tertiary"}`}>
        {selected.size} of {preview.sections.length} sections selected ·{" "}
        {usage.exceeds
          ? "Over the analysis limit"
          : usage.warning
            ? "Close to the analysis limit"
            : "Within the analysis limit"}
      </div>
      <details className="text-caption text-text-tertiary">
        <summary className="cursor-pointer">Technical details</summary>
        <p className="mt-1">
          {usage.sourceTokens.toLocaleString()} /{" "}
          {preview.max_source_tokens.toLocaleString()} source tokens · about{" "}
          {usage.estimatedChunks} / {preview.max_chunks} analysis segments
        </p>
      </details>
      {usage.warning && !usage.exceeds && <p className="text-small text-status-amber">This selection is close to the analysis limit. Exclude administrative or less relevant sections to reduce noise.</p>}
      {usage.exceeds && <p className="text-small text-status-red">This selection exceeds the analysis limit and cannot be submitted. Exclude less relevant sections; content will never be silently truncated.</p>}
      {preview.warnings.map((warning) => <p key={warning} className="text-small text-status-amber">{warning}</p>)}
      {filenames.map((filename) => (
        <section key={filename}>
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-small font-signature text-text-primary">{filename}</h3>
            <div className="flex gap-2">
              <button type="button" className="btn-ghost" onClick={() => toggleFile(filename, true)}>Select all</button>
              <button type="button" className="btn-ghost" onClick={() => toggleFile(filename, false)}>Clear</button>
            </div>
          </div>
          <div className="space-y-2">
            {preview.sections.filter((s) => s.filename === filename).map((section) => (
              <details key={section.id} className="rounded-comfy bg-bg-deepest p-2">
                <summary className="cursor-pointer text-small text-text-primary">
                  <input className="mr-2" type="checkbox" checked={selected.has(section.id)} onClick={(e) => e.stopPropagation()} onChange={(e) => {
                    const next = new Set(selected);
                    if (e.target.checked) next.add(section.id); else next.delete(section.id);
                    onChange(next);
                  }} />
                  {section.section}{!section.included_by_default && <span className="ml-2 text-caption text-text-tertiary">default excluded</span>}
                </summary>
                <p className="mt-2 whitespace-pre-line text-caption text-text-secondary">{section.excerpt}</p>
              </details>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
