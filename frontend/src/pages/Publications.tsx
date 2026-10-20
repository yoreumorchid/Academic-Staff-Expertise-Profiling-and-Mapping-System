/**
 * UC-9 — Review harvested publications and supplement missing abstracts
 * either by pasting text or by uploading a PDF / DOCX file.
 */
import { FormEvent, useEffect, useState } from "react";
import { api, extractApiError } from "../api/client";
import type { Publication } from "../types";
import { Banner } from "./Profile";

export function PublicationsPage() {
  const [pubs, setPubs] = useState<Publication[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [textBusy, setTextBusy] = useState(false);
  const [fileBusy, setFileBusy] = useState(false);

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
    setTextBusy(true);
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
      setTextBusy(false);
    }
  }

  async function submitFile() {
    if (!openId || !file) {
      setError("Select a PDF or DOCX file first.");
      return;
    }
    setFileBusy(true);
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
      setFileBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-heading-1 font-announce text-text-primary">
          Publications &amp; Abstracts
        </h1>
        <p className="mt-2 max-w-3xl text-body leading-relaxed text-text-tertiary">
          When OpenAlex cannot return an abstract for a paper we found via
          your ORCID, the ABSTRACT row is flagged <em>Missing</em>. Click
          <span className="mx-1 font-signature">Supplement</span>
          to paste the text yourself or upload a PDF/DOCX so the system
          can re-run tag extraction on that paper.
        </p>
      </header>

      {error && <Banner kind="error">{error}</Banner>}
      {info && <Banner kind="success">{info}</Banner>}

      <section className="card overflow-hidden p-0">
        {pubs.length === 0 ? (
          <p className="px-6 py-8 text-center text-body text-text-tertiary">
            No publications harvested yet.
          </p>
        ) : (
          <ul className="divide-y divide-border-secondary">
            {pubs.map((p) => (
              <li key={p.id} className="p-5 sm:p-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <h2 className="text-body-lg font-signature leading-relaxed text-text-primary">
                      {p.title ?? p.doi}
                    </h2>
                    <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-2 text-small text-text-tertiary">
                      <div className="inline-flex gap-2">
                        <dt>Venue</dt>
                        <dd className="text-text-secondary">
                          {p.venue ?? "Not available"}
                        </dd>
                      </div>
                      <div className="inline-flex gap-2">
                        <dt>Year</dt>
                        <dd className="text-text-secondary">
                          {p.publication_year ?? "Not available"}
                        </dd>
                      </div>
                      <div className="inline-flex items-center gap-2">
                        <dt>Abstract</dt>
                        <dd
                          className={`font-signature ${
                            p.abstract_missing
                              ? "text-status-amber"
                              : "text-status-green"
                          }`}
                        >
                          {p.abstract_missing ? "Missing" : "Available"}
                        </dd>
                      </div>
                    </dl>
                  </div>
                  {p.abstract_missing && (
                    <button
                      type="button"
                      className="btn-primary shrink-0 self-start sm:self-center"
                      onClick={() => openDrawer(p.id)}
                    >
                      Supplement abstract
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {openId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="supplement-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpenId(null);
          }}
        >
          <section className="card w-full max-w-2xl space-y-4 shadow-floating">
            <header className="flex items-start justify-between gap-4">
              <div>
                <h2
                  id="supplement-title"
                  className="text-heading-3 font-announce text-text-primary"
                >
                  Supplement abstract
                </h2>
                <p className="mt-1 text-small leading-relaxed text-text-tertiary">
                  Paste the abstract from the publisher's page, or upload
                  the PDF/DOCX. The text is parsed locally and sent through
                  the same NLP pipeline that runs on quarterly sync.
                </p>
              </div>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setOpenId(null)}
                aria-label="Close"
              >
                Close
              </button>
            </header>

            <form onSubmit={submitText} className="space-y-3">
              <label
                className="mb-2 block text-small font-signature text-text-secondary"
                htmlFor="abstract"
              >
                Paste abstract text (≥ 200 characters)
              </label>
              <textarea
                id="abstract"
                className="input min-h-[200px]"
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
              <div className="flex justify-end">
                <button type="submit" className="btn-primary" disabled={textBusy}>
                  {textBusy ? "Submitting\u2026" : "Submit text"}
                </button>
              </div>
            </form>

            <div className="border-t border-border-secondary pt-4">
              <p className="text-small text-text-tertiary">
                Or upload a PDF / DOCX document:
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
                  disabled={fileBusy || !file}
                >
                  {fileBusy ? "Uploading\u2026" : "Upload"}
                </button>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
