import { useState, FormEvent } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/auth";
import { canToggleView, sidebarForActiveView } from "../navigation/sidebar";

/**
 * Persistent application shell shared by both portals.
 *
 * Brand renders as "Expertise Insight". A global header search bar
 * routes any query into the staff directory (UC-7 header search).
 * Sidebar items use the floating-card hover effect from index.css.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, activeView, setActiveView, logout } = useAuthStore();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  if (!user) return null;
  const links = sidebarForActiveView(user, activeView);
  const showToggle = canToggleView(user);

  function onSearch(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    if (!q) return;
    navigate(`/admin/staff?q=${encodeURIComponent(q)}`);
  }

  // Show the global search bar only when an admin surface is reachable —
  // i.e. the user is currently in admin view, or holds the dual-role
  // toggle. Pure academic-staff sessions get a leaner header.
  const showGlobalSearch = activeView === "admin" || showToggle;

  return (
    <div className="flex min-h-screen bg-bg-marketing text-text-primary">
      <aside className="w-64 shrink-0 border-r border-border-secondary bg-bg-panel">
        <div className="px-5 py-6">
          <div className="text-heading-3 font-announce text-text-primary">
            Expertise Insight
          </div>
        </div>
        <nav className="mt-2 flex flex-col gap-2 px-3 pb-6">
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
            <form onSubmit={onSearch} className="flex-1 max-w-xl">
              <label htmlFor="global-search" className="sr-only">
                Global search
              </label>
              <div className="relative">
                <input
                  id="global-search"
                  type="search"
                  className="input pl-10"
                  placeholder="Search staff, expertise, publications, departments…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <svg
                  aria-hidden="true"
                  viewBox="0 0 20 20"
                  className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-quaternary"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <circle cx="9" cy="9" r="6" />
                  <path d="m17 17-3.5-3.5" strokeLinecap="round" />
                </svg>
              </div>
            </form>
          ) : (
            <div className="flex-1" />
          )}
          <div className="text-caption text-text-tertiary whitespace-nowrap">
            <span className="text-text-primary">{user.full_name}</span>
            <span className="mx-2 text-text-quaternary">·</span>
            <span className="text-text-tertiary">{user.email}</span>
          </div>
          <div className="flex items-center gap-2">
            {showToggle && (
              <div className="flex items-center rounded-full border border-border-primary bg-white p-0.5">
                <button
                  type="button"
                  onClick={() => setActiveView("staff")}
                  className={[
                    "rounded-full px-3 py-1 text-label font-signature transition-colors",
                    activeView === "staff"
                      ? "bg-brand-indigo text-white"
                      : "text-text-tertiary hover:text-text-primary",
                  ].join(" ")}
                >
                  Staff View
                </button>
                <button
                  type="button"
                  onClick={() => setActiveView("admin")}
                  className={[
                    "rounded-full px-3 py-1 text-label font-signature transition-colors",
                    activeView === "admin"
                      ? "bg-brand-indigo text-white"
                      : "text-text-tertiary hover:text-text-primary",
                  ].join(" ")}
                >
                  Admin View
                </button>
              </div>
            )}
            <button
              type="button"
              className="btn-ghost"
              onClick={() => {
                logout();
                navigate("/login", { replace: true });
              }}
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
