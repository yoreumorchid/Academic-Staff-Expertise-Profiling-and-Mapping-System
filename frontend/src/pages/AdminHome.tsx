/**
 * Administrator landing page — surfaces the strategic-dashboard summary
 * (UC-6) with quick links into the modules permitted by the actor's
 * portfolio.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, extractApiError } from "../api/client";
import { sidebarForActiveView } from "../navigation/sidebar";
import { useAuthStore } from "../store/auth";
import type { StaffDirectoryEntry } from "../types";
import { Banner, EmptyState, Stat } from "./Profile";

export function AdminHomePage() {
  const { user } = useAuthStore();
  const [staff, setStaff] = useState<StaffDirectoryEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get<StaffDirectoryEntry[]>("/profile/staff");
        setStaff(data);
      } catch (err) {
        setError(extractApiError(err, "Could not load staff directory."));
      }
    })();
  }, []);

  const departments = useMemo(() => {
    const set = new Set<string>();
    staff.forEach((s) => {
      if (s.department) set.add(s.department);
    });
    return set.size;
  }, [staff]);

  const taggedCount = useMemo(
    () => staff.filter((s) => s.tag_labels.length > 0).length,
    [staff],
  );

  const links = user ? sidebarForActiveView(user, "admin") : [];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-heading-1 font-announce text-text-primary">
          Strategic Dashboard
        </h1>
      </header>

      {error && <Banner kind="error">{error}</Banner>}

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Stat label="Academic staff" value={staff.length} />
        <Stat label="Departments" value={departments} />
        <Stat label="Profiles with tags" value={taggedCount} />
      </section>

      <section className="card">
        <h2 className="mb-3 text-heading-3 font-announce text-text-primary">
          Module shortcuts
        </h2>
        {links.length === 0 ? (
          <EmptyState text="No portfolio modules attached to your account." />
        ) : (
          <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {links.map((l) => (
              <li key={l.path}>
                <Link
                  to={l.path}
                  className="flex items-center justify-between rounded-comfy border border-border-secondary bg-bg-surface px-4 py-3 text-small text-text-secondary transition-colors hover:bg-bg-secondary hover:text-text-primary"
                >
                  <span>{l.label}</span>

                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
