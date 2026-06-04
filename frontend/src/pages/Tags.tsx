/**
 * UC-11 — Refine the AI-generated expertise tags.
 *
 * The user may validate or remove harvested tags and add custom labels.
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
      setValidateIds(
        new Set(data.filter((t) => t.validated).map((t) => t.tag.id)),
      );
      setAddLabels([]);
    } catch (err) {
      setError(extractApiError(err, "Could not load expertise tags."));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const remainingPreview = useMemo(() => {
    const kept = tags.filter((t) => !removeIds.has(t.tag.id)).length;
    return kept + addLabels.length;
  }, [tags, removeIds, addLabels]);

  function toggleRemove(tagId: string) {
    setRemoveIds((prev) => {
      const next = new Set(prev);
      if (next.has(tagId)) next.delete(tagId);
      else {
        next.add(tagId);
        // Removed tags cannot also be validated.
        setValidateIds((v) => {
          const nv = new Set(v);
          nv.delete(tagId);
          return nv;
        });
      }
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
    if (remainingPreview === 0) {
      setError(
        "A profile must retain at least one expertise tag.",
      );
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
      await api.post("/profile/expertise/refine", payload);
      setInfo("Expertise tags updated.");
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
              const validating = validateIds.has(t.tag.id);
              return (
                <li
                  key={t.id}
                  className={`flex items-center justify-between gap-4 py-3 ${
                    removing ? "opacity-50" : ""
                  }`}
                >
                  <div>
                    <div className="text-body text-text-primary">
                      {t.tag.canonical_label}
                    </div>
                    <div className="mt-1 text-caption text-text-tertiary">
                      {t.tag.domain ?? "Unclassified"} · confidence{" "}
                      {(t.confidence * 100).toFixed(0)}% · source {t.source}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="inline-flex items-center gap-1 text-caption text-text-secondary">
                      <input
                        type="checkbox"
                        checked={validating}
                        onChange={() => toggleValidate(t.tag.id)}
                        disabled={removing}
                      />
                      Validate
                    </label>
                    <label className="inline-flex items-center gap-1 text-caption text-text-secondary">
                      <input
                        type="checkbox"
                        checked={removing}
                        onChange={() => toggleRemove(t.tag.id)}
                      />
                      Remove
                    </label>
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
        <div className="flex flex-wrap gap-2">
          {addLabels.map((label) => (
            <span
              key={label}
              className="pill border-brand-indigo/50 text-text-primary"
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
        <div className="mt-3 flex gap-2">
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
          Preview after save:{" "}
          <span className="text-text-secondary">{remainingPreview} tag(s)</span>
        </span>
        <button
          type="button"
          className="btn-primary"
          onClick={submit}
          disabled={busy}
        >
          {busy ? "Saving…" : "Save changes"}
        </button>
      </div>
    </div>
  );
}
