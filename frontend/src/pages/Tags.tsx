/**
 * UC-11 — Refine the AI-generated expertise tags.
 *
 * The user may validate or remove harvested tags and add custom labels.
 * Validated tags are confirmed by the user as accurate representations
 * of their expertise — they appear prominently on the profile and are
 * prioritised in CV/portfolio snapshot exports.
 *
 * The backend enforces the "non-empty profile" exception; here we
 * additionally guard the submit button when the staged change would
 * clearly leave the profile empty.
 */
import { useEffect, useMemo, useState } from "react";
import { api, extractApiError } from "../api/client";
import type { RefineTagsRequest, UserExpertiseTag } from "../types";
import { Banner, EmptyState } from "./Profile";

export function TagRefinementPage() {
  const [tags, setTags] = useState<UserExpertiseTag[]>([]);
  const [removeIds, setRemoveIds] = useState<Set<string>>(new Set());
  // Only tag-ids the user has *just* requested to validate (not yet
  // persisted).  Tags that were already validated in the DB are tracked
  // separately via ``t.validated``.
  const [validateIds, setValidateIds] = useState<Set<string>>(new Set());
  const [draftLabel, setDraftLabel] = useState("");
  const [addLabels, setAddLabels] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const { data } = await api.get<UserExpertiseTag[]>("/profile/expertise");
      setTags(data);
      setRemoveIds(new Set());
      // Auto-select tags that were ALREADY validated in the DB so the
      // user sees them as "currently validated".
      setValidateIds(new Set());
      setAddLabels([]);
    } catch (err) {
      setError(extractApiError(err, "Could not load expertise tags."));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  // Count tags that will remain after pending removals.
  const remainingCount = useMemo(() => {
    return tags.filter((t) => !removeIds.has(t.tag.id)).length + addLabels.length;
  }, [tags, removeIds, addLabels]);

  function toggleRemove(tagId: string) {
    setRemoveIds((prev) => {
      const next = new Set(prev);
      if (next.has(tagId)) next.delete(tagId);
      else next.add(tagId);
      return next;
    });
  }

  function toggleValidate(tagId: string) {
    if (removeIds.has(tagId)) return;
    setValidateIds((prev) => {
      const next = new Set(prev);
      if (next.has(tagId)) next.delete(tagId);
      else next.add(tagId);
      return next;
    });
  }

  function addCustomLabel() {
    const trimmed = draftLabel.trim();
    if (!trimmed) return;
    if (addLabels.includes(trimmed)) return;
    setAddLabels((prev) => [...prev, trimmed]);
    setDraftLabel("");
  }

  function removeCustomLabel(label: string) {
    setAddLabels((prev) => prev.filter((l) => l !== label));
  }

  async function submit() {
    if (remainingCount === 0) {
      setError("A profile must retain at least one expertise tag.");
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const payload: RefineTagsRequest = {
        remove_tag_ids: Array.from(removeIds),
        validate_tag_ids: Array.from(validateIds).filter(
          (id) => !removeIds.has(id),
        ),
        add_labels: addLabels,
      };

      const addedCount = addLabels.length;
      const removedCount = removeIds.size;
      const validatedCount = validateIds.size;

      await api.post("/profile/expertise/refine", payload);

      const parts: string[] = [];
      if (validatedCount > 0) parts.push(`${validatedCount} tag(s) validated`);
      if (removedCount > 0) parts.push(`${removedCount} tag(s) removed`);
      if (addedCount > 0) parts.push(`${addedCount} label(s) added`);
      setInfo(parts.join(" · "));

      await load();
    } catch (err) {
      setError(extractApiError(err, "Refinement failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-heading-1 font-announce text-text-primary">
          Expertise Tag Refinement
        </h1>
        <p className="mt-2 max-w-2xl text-body-lg text-text-tertiary">
          Confirm which AI-generated tags correctly represent your expertise
          and remove those that don't. Validated tags are prioritised in your
          CV and portfolio snapshot.
        </p>
      </header>

      {error && <Banner kind="error">{error}</Banner>}
      {info && <Banner kind="success">{info}</Banner>}

      <section className="card">
        <h2 className="mb-4 text-heading-3 font-announce text-text-primary">
          AI-generated tags
        </h2>
        {tags.length === 0 ? (
          <EmptyState text="No tags yet. Run a sync from Profile Overview." />
        ) : (
          <ul className="divide-y divide-border-secondary">
            {tags.map((t) => {
              const removing = removeIds.has(t.tag.id);
              const alreadyValidated = t.validated;
              const newlyValidated = validateIds.has(t.tag.id);

              return (
                <li
                  key={t.id}
                  className={`flex items-center justify-between gap-4 py-3 ${
                    removing ? "opacity-50" : ""
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-body text-text-primary">
                          {t.tag.canonical_label}
                        </span>
                        {alreadyValidated && (
                          <span className="pill border-brand-green/50 text-brand-green">
                            Validated
                          </span>
                        )}
                        {newlyValidated && !alreadyValidated && (
                          <span className="pill border-status-amber/50 text-status-amber">
                            Pending
                          </span>
                        )}
                      </div>
                      <div className="mt-1 text-caption text-text-tertiary">
                        {t.tag.domain ?? "Unclassified"} · confidence{" "}
                        {(t.confidence * 100).toFixed(0)}% · source {t.source}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {removing ? (
                      <button
                        type="button"
                        className="btn-ghost text-caption"
                        onClick={() => toggleRemove(t.tag.id)}
                      >
                        Undo
                      </button>
                    ) : (
                      <>
                        {alreadyValidated ? (
                          <span className="text-caption text-brand-green">
                            Validated
                          </span>
                        ) : (
                          <button
                            type="button"
                            className={`text-caption ${
                              newlyValidated
                                ? "btn-ghost"
                                : "btn-primary px-3 py-1"
                            }`}
                            onClick={() => toggleValidate(t.tag.id)}
                          >
                            {newlyValidated ? "Cancel" : "Validate"}
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn-ghost text-caption"
                          onClick={() => toggleRemove(t.tag.id)}
                        >
                          Remove
                        </button>
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="card">
        <h2 className="mb-4 text-heading-3 font-announce text-text-primary">
          Add custom labels
        </h2>
        <p className="mb-3 text-caption text-text-tertiary">
          Add expertise labels that weren't surfaced by the AI pipeline.
        </p>
        {addLabels.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {addLabels.map((label) => (
              <span
                key={label}
                className="pill border-brand-green/50 text-text-primary"
              >
                {label}
                <button
                  type="button"
                  className="ml-2 text-text-tertiary hover:text-text-primary"
                  onClick={() => removeCustomLabel(label)}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          <input
            className="input"
            placeholder="e.g. Graph Neural Networks"
            value={draftLabel}
            onChange={(e) => setDraftLabel(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addCustomLabel();
              }
            }}
          />
          <button type="button" className="btn-ghost" onClick={addCustomLabel}>
            Add
          </button>
        </div>
      </section>

      <div className="flex items-center justify-between">
        <span className="text-caption text-text-tertiary">
          {removeIds.size + validateIds.size + addLabels.length > 0 ? (
            <>
              Pending changes:{" "}
              {validateIds.size > 0 && (
                <span className="text-brand-green">
                  {validateIds.size} validation(s)
                </span>
              )}
              {validateIds.size > 0 && removeIds.size > 0 && " · "}
              {removeIds.size > 0 && (
                <span className="text-status-red">
                  {removeIds.size} removal(s)
                </span>
              )}
              {removeIds.size + validateIds.size > 0 && addLabels.length > 0 && " · "}
              {addLabels.length > 0 && (
                <span className="text-brand-violet">
                  {addLabels.length} label(s)
                </span>
              )}
              {" → "}
              <span className="text-text-secondary">{remainingCount} tag(s) after save</span>
            </>
          ) : (
            <>No pending changes</>
          )}
        </span>
        <button
          type="button"
          className="btn-primary"
          onClick={submit}
          disabled={busy || remainingCount === 0 || (removeIds.size + validateIds.size + addLabels.length === 0)}
        >
          {busy ? "Saving…" : "Save changes"}
        </button>
      </div>
    </div>
  );
}