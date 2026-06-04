/**
 * UC-10 — Manually curate the academic background timeline.
 */
import { FormEvent, useEffect, useState } from "react";
import { api, extractApiError } from "../api/client";
import type {
  AcademicBackground,
  AcademicBackgroundCategory,
  AcademicBackgroundInput,
} from "../types";
import { Banner, EmptyState } from "./Profile";

const CATEGORY_OPTIONS: { value: AcademicBackgroundCategory; label: string }[] =
  [
    { value: "education", label: "Education" },
    { value: "appointment", label: "Appointment" },
    { value: "award", label: "Award" },
    { value: "service", label: "Service" },
  ];

const EMPTY_FORM: AcademicBackgroundInput = {
  category: "education",
  title: "",
  organization: "",
  description: "",
  start_date: "",
  end_date: null,
};

export function AcademicBackgroundPage() {
  const [records, setRecords] = useState<AcademicBackground[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<AcademicBackgroundInput>(EMPTY_FORM);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const { data } = await api.get<AcademicBackground[]>("/profile/background");
      setRecords(data);
    } catch (err) {
      setError(extractApiError(err, "Could not load background."));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function startEdit(record: AcademicBackground) {
    setEditingId(record.id);
    setForm({
      category: record.category,
      title: record.title,
      organization: record.organization ?? "",
      description: record.description ?? "",
      start_date: record.start_date,
      end_date: record.end_date,
    });
    setError(null);
  }

  function resetForm() {
    setEditingId(null);
    setForm(EMPTY_FORM);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (form.end_date && form.end_date < form.start_date) {
      setError("end_date must be on or after start_date.");
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    const payload: AcademicBackgroundInput = {
      ...form,
      organization: form.organization || null,
      description: form.description || null,
      end_date: form.end_date || null,
    };
    try {
      if (editingId) {
        await api.put(`/profile/background/${editingId}`, payload);
        setInfo("Record updated.");
      } else {
        await api.post("/profile/background", payload);
        setInfo("Record added.");
      }
      resetForm();
      await load();
    } catch (err) {
      setError(extractApiError(err, "Submission failed."));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm("Delete this record permanently?")) return;
    setError(null);
    try {
      await api.delete(`/profile/background/${id}`);
      await load();
    } catch (err) {
      setError(extractApiError(err, "Deletion failed."));
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-heading-1 font-announce text-text-primary">
          Academic Background
        </h1>
      </header>

      {error && <Banner kind="error">{error}</Banner>}
      {info && <Banner kind="success">{info}</Banner>}

      <form onSubmit={submit} className="card grid grid-cols-1 gap-3 md:grid-cols-2">
        <div>
          <label className="label">Category</label>
          <select
            className="input"
            value={form.category}
            onChange={(e) =>
              setForm({
                ...form,
                category: e.target.value as AcademicBackgroundCategory,
              })
            }
          >
            {CATEGORY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Title</label>
          <input
            className="input"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            required
          />
        </div>
        <div>
          <label className="label">Organization</label>
          <input
            className="input"
            value={form.organization ?? ""}
            onChange={(e) => setForm({ ...form, organization: e.target.value })}
          />
        </div>
        <div>
          <label className="label">Start date</label>
          <input
            type="date"
            className="input"
            value={form.start_date}
            onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            required
          />
        </div>
        <div>
          <label className="label">End date (optional)</label>
          <input
            type="date"
            className="input"
            value={form.end_date ?? ""}
            onChange={(e) => setForm({ ...form, end_date: e.target.value || null })}
          />
        </div>
        <div className="md:col-span-2">
          <label className="label">Description</label>
          <textarea
            className="input min-h-[80px]"
            value={form.description ?? ""}
            onChange={(e) =>
              setForm({ ...form, description: e.target.value })
            }
          />
        </div>
        <div className="md:col-span-2 flex items-center justify-end gap-2">
          {editingId && (
            <button type="button" className="btn-ghost" onClick={resetForm}>
              Cancel
            </button>
          )}
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Saving…" : editingId ? "Update record" : "Add record"}
          </button>
        </div>
      </form>

      <section className="card">
        <h2 className="mb-4 text-heading-3 font-announce text-text-primary">
          Existing records
        </h2>
        {records.length === 0 ? (
          <EmptyState text="No background records yet." />
        ) : (
          <ul className="divide-y divide-border-secondary">
            {records.map((r) => (
              <li
                key={r.id}
                className="flex items-start justify-between gap-4 py-3"
              >
                <div>
                  <div className="text-body text-text-primary">{r.title}</div>
                  <div className="mt-1 text-caption text-text-tertiary">
                    {r.category} · {r.organization ?? "—"} · {r.start_date}
                    {r.end_date ? ` → ${r.end_date}` : " → present"}
                  </div>
                  {r.description && (
                    <p className="mt-2 text-small text-text-secondary">
                      {r.description}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => startEdit(r)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => remove(r.id)}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
