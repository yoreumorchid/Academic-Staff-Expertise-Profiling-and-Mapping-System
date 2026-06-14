import { useEffect, useRef, useState, FormEvent } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { api, extractApiError } from "../api/client";
import { useAuthStore } from "../store/auth";
import { canToggleView, sidebarForActiveView } from "../navigation/sidebar";
import { SyncStatusGuard } from "./SyncStatusGuard";
import type { StaffDirectoryEntry } from "../types";

/**
 * Persistent application shell shared by both portals.
 *
 * Brand renders as "Expertise Insight". The global header search bar
 * (UC-7 alt flow) is a minimal single-line input — backend matching is
 * scoped to staff name + department only. Submitting the form opens an
 * inline dropdown of Overview Staff Profile cards; clicking any card
 * jumps directly to that staff member's full expertise page.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, activeView, setActiveView, logout } = useAuthStore();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StaffDirectoryEntry[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  if (!user) return null;
  const links = sidebarForActiveView(user, activeView);
  const showToggle = canToggleView(user);

  // Hide the global search bar for pure academic-staff sessions.
  const showGlobalSearch = activeView === "admin" || showToggle;

  // Close the dropdown on outside click.
  useEffect(() => {
    if (results === null) return;
    function onDocClick(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setResults(null);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [results]);

  async function onSearch(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    if (!q) return;
    setSearching(true);
    setSearchError(null);
    try {
      // UC-7 — global header search: backend filters on full_name and
      // department only. We issue both requests in parallel and union
      // the result set, preserving each staff member's first hit.
      const [byName, byDept] = await Promise.all([
        api.get<StaffDirectoryEntry[]>("/profile/staff", {
          params: { q, category: "name" },
        }),
        api.get<StaffDirectoryEntry[]>("/profile/staff", {
          params: { q, category: "department" },
        }),
      ]);
      const seen = new Set<string>();
      const merged: StaffDirectoryEntry[] = [];
      for (const row of [...byName.data, ...byDept.data]) {
        if (!seen.has(row.id)) {
          seen.add(row.id);
          merged.push(row);
        }
      }
      setResults(merged);
    } catch (err) {
      setSearchError(extractApiError(err, "Search failed."));
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  function openStaff(id: string) {
    setResults(null);
    setQuery("");
    navigate(`/admin/staff?open=${encodeURIComponent(id)}`);
  }

  return (
    <div className="flex min-h-screen bg-bg-marketing text-text-primary">
      <SyncStatusGuard />
      <aside className="w-64 shrink-0 border-r border-border-secondary bg-bg-panel">
        <div className="px-5 py-6">
          <div className="text-heading-3 font-announce text-text-primary">
            Expertise Insight
          </div>
        </div>
        <nav className="mt-2 flex flex-col gap-3 px-4 pb-6">
          {links.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end
              className={({ isActive }) =>
                ["sidebar-item", isActive ? "sidebar-item-active" : ""].join(" ")
              }
            >
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center gap-4 border-b border-border-secondary bg-bg-panel px-6 py-3">
          {showGlobalSearch ? (
            <div ref={dropdownRef} className="relative flex-1 max-w-xl">
              <form onSubmit={onSearch}>
                <label htmlFor="global-search" className="sr-only">
                  Global search
                </label>
                <div className="relative">
                  <input
                    id="global-search"
                    type="search"
                    className="input pl-10"
                    placeholder="Search staff by name or department…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                  <button
                    type="submit"
                    aria-label="Search"
                    className="absolute left-2 top-1/2 -translate-y-1/2 rounded p-1 text-text-quaternary hover:text-text-primary"
                  >
                    <svg
                      aria-hidden="true"
                      viewBox="0 0 20 20"
                      className="h-4 w-4"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <circle cx="9" cy="9" r="6" />
                      <path d="m17 17-3.5-3.5" strokeLinecap="round" />
                    </svg>
                  </button>
                </div>
              </form>
              {results !== null && (
                <div className="absolute left-0 right-0 top-full z-40 mt-2 max-h-[60vh] overflow-y-auto rounded-card border border-border-secondary bg-white shadow-floating">
                  {searching ? (
                    <div className="px-4 py-3 text-caption text-text-tertiary">
                      Searching…
                    </div>
                  ) : searchError ? (
                    <div className="px-4 py-3 text-caption text-text-secondary">
                      {searchError}
                    </div>
                  ) : results.length === 0 ? (
                    <div className="px-4 py-3 text-caption text-text-tertiary">
                      No staff matched “{query}”.
                    </div>
                  ) : (
                    <ul className="divide-y divide-border-secondary">
                      {results.map((r) => (
                        <li key={r.id}>
                          <button
                            type="button"
                            onClick={() => openStaff(r.id)}
                            className="w-full px-4 py-3 text-left transition-colors hover:bg-bg-surface"
                          >
                            <div className="text-body text-text-primary">
                              {r.full_name}
                            </div>
                            <div className="text-caption text-text-tertiary">
                              {r.department ?? "Department n/a"} · {r.email}
                            </div>
                            {r.tag_labels.length > 0 && (
                              <div className="mt-1 flex flex-wrap gap-1">
                                {r.tag_labels.slice(0, 4).map((t) => (
                                  <span key={t} className="pill">
                                    {t}
                                  </span>
                                ))}
                                {r.tag_labels.length > 4 && (
                                  <span className="text-caption text-text-quaternary">
                                    +{r.tag_labels.length - 4}
                                  </span>
                                )}
                              </div>
                            )}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1" />
          )}
          <div className="ml-auto flex items-center gap-3">
            {showToggle && (
              <div className="flex items-center rounded-full border border-border-primary bg-white p-0.5">
                <button
                  type="button"
                  onClick={() => {
                    setActiveView("staff");
                    navigate("/staff/profile");
                  }}
                  className={[
                    "rounded-full px-3 py-1 text-label font-signature transition-colors",
                    activeView === "staff"
                      ? "bg-brand-green text-white"
                      : "text-text-tertiary hover:text-text-primary",
                  ].join(" ")}
                >
                  Staff View
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setActiveView("admin");
                    navigate("/admin");
                  }}
                  className={[
                    "rounded-full px-3 py-1 text-label font-signature transition-colors",
                    activeView === "admin"
                      ? "bg-brand-green text-white"
                      : "text-text-tertiary hover:text-text-primary",
                  ].join(" ")}
                >
                  Admin View
                </button>
              </div>
            )}
            <button
              type="button"
              onClick={() => navigate("/staff/profile")}
              className="flex items-baseline gap-1 text-caption text-text-tertiary transition-colors hover:text-text-primary"
              title="View profile"
            >
              <span className="text-text-primary">{user.full_name}</span>{" "}
              <span className="hidden text-text-tertiary md:inline">
                {user.email}
              </span>
            </button>
            <button
              type="button"
              onClick={() => {
                logout();
                navigate("/login", { replace: true });
              }}
              className="text-small text-text-secondary underline underline-offset-2 hover:text-text-primary focus:outline-none focus:shadow-focus"
            >
              Log out
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto px-8 py-8">{children}</main>
      </div>
    </div>
  );
}
