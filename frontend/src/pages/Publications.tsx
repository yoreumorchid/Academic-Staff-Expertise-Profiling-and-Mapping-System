/**
 * UC-9 — Review harvested publications and supplement missing abstracts
 * either by pasting text or by uploading a PDF / DOCX file.
 */
import { FormEvent, useEffect, useState } from "react";
import { api, extractApiError } from "../api/client";
import type { Publication } from "../types";
import { Banner, EmptyState } from "./Profile";

export function PublicationsPage() {
  const [pubs, setPubs] = useState<Publication[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const { data } = await api.get<Publication[]>("/profile/publications");
      setPubs(data);
    } catch (err) {
      setError(extractApiError(err, "Could not load publications."));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function openDrawer(id: string) {
    setOpenId(id);
    setText("");
    setFile(null);
    setError(null);
    setInfo(null);
  }

  async function submitText(event: FormEvent) {
    event.preventDefault();
    if (!openId) return;
    if (text.trim().length < 200) {
      setError("Provide at least 200 characters of abstract text.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post(`/profile/publications/${openId}/abstract`, {
        abstract_text: text,
      });
      setInfo("Abstract supplemented. The NLP pipeline has been re-run.");
      setOpenId(null);
      await load();
    } catch (err) {
      setError(extractApiError(err, "Supplementation failed."));
    } finally {
      setBusy(false);
    }
  }

  async function submitFile() {
    if (!openId || !file) {
      setError("Select a PDF or DOCX file first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api.post(
        `/profile/publications/${openId}/abstract/upload`,
        fd,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      setInfo(
        "File parsed and abstract supplemented. NLP pipeline re-run completed.",
      );
      setOpenId(null);
      setFile(null);
      await load();
    } catch (err) {
      setError(extractApiError(err, "Upload failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-caption font-signature uppercase tracking-wide text-text-quaternary">
          UC-9
        </p>
        <h1 className="mt-1 text-heading-1 font-announce text-text-primary">
          Publications &amp; Abstracts
        </h1>
        <p className="mt-2 max-w-2xl text-body-lg text-text-tertiary">
          Publications missing an OpenAlex abstract are flagged below. Supply
          the abstract text or upload the corresponding document so the SciBERT
          + LLM pipeline can regenerate expertise tags.
        </p>
      </header>

      {error && <Banner kind="error">{error}</Banner>}
      {info && <Banner kind="success">{info}</Banner>}

      <section className="card overflow-hidden p-0">
        <table className="min-w-full divide-y divide-white/[0.05] text-small">
          <thead className="bg-white/[0.02] text-caption uppercase tracking-wide text-text-quaternary">
            <tr>
              <th className="px-4 py-3 text-left font-signature">Title</th>
              <th className="px-4 py-3 text-left font-signature">Venue</th>
              <th className="px-4 py-3 text-left font-signature">Year</th>
              <th className="px-4 py-3 text-left font-signature">Status</th>
              <th className="px-4 py-3 text-right font-signature">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.05]">
            {pubs.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-text-tertiary">
                  No publications harvested yet.
                </td>
              </tr>
            ) : (
              pubs.map((p) => (
                <tr key={p.id}>
                  <td className="px-4 py-3 text-text-primary">
                    {p.title ?? p.doi}
                  </td>
                  <td className="px-4 py-3 text-text-secondary">{p.venue ?? "—"}</td>
                  <td className="px-4 py-3 text-text-secondary">
                    {p.publication_year ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    {p.abstract_missing ? (
                      <span className="pill border-brand-violet/50 text-brand-violet">
                        Missing
                      </span>
                    ) : (
                      <span className="pill">OK</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {p.abstract_missing ? (
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={() => openDrawer(p.id)}
                      >
                        Supplement
                      </button>
                    ) : (
                      <span className="text-caption text-text-quaternary">—</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      {openId && (
        <section className="card space-y-4">
          <header className="flex items-center justify-between">
            <h2 className="text-heading-3 font-announce text-text-primary">
              Supplement abstract
            </h2>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => setOpenId(null)}
            >
              Close
            </button>
          </header>

          <form onSubmit={submitText} className="space-y-3">
            <label className="label" htmlFor="abstract">
              Paste abstract text (≥ 200 characters)
            </label>
            <textarea
              id="abstract"
              className="input min-h-[160px]"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <div className="flex justify-end">
              <button type="submit" className="btn-primary" disabled={busy}>
                {busy ? "Submitting…" : "Submit text"}
              </button>
            </div>
          </form>

          <div className="border-t border-white/[0.05] pt-4">
            <p className="text-caption text-text-tertiary">
              Or upload a PDF / DOCX document (UC-9 alternative flow):
            </p>
            <div className="mt-2 flex items-center gap-2">
              <input
                type="file"
                accept=".pdf,.docx"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="text-small text-text-secondary"
              />
              <button
                type="button"
                className="btn-primary"
                onClick={submitFile}
                disabled={busy || !file}
              >
                {busy ? "Uploading…" : "Upload"}
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
