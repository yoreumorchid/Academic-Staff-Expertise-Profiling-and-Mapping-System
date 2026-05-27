import { NavLink, useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/auth";
import { canToggleView, sidebarForActiveView } from "../navigation/sidebar";

/**
 * Persistent application shell shared by both portals.
 *
 * Implements the global header (UC-6 step 3) with the dual-role
 * "Switch View" toggle (FR-012 / UC-6 alternative flows) and the
 * portfolio-derived sidebar.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, activeView, setActiveView, logout } = useAuthStore();
  const navigate = useNavigate();

  if (!user) return null;
  const links = sidebarForActiveView(user, activeView);
  const showToggle = canToggleView(user);

  return (
    <div className="flex min-h-screen bg-bg-marketing text-text-primary">
      <aside className="w-64 shrink-0 border-r border-white/[0.05] bg-bg-panel">
        <div className="px-5 py-6">
          <div className="text-heading-3 font-announce text-text-primary">
            ExpertiseInsight
          </div>
          <div className="mt-1 text-caption text-text-tertiary">
            {activeView === "staff" ? "Expertise Portal" : "Strategic Dashboard"}
          </div>
        </div>
        <nav className="mt-2 flex flex-col gap-0.5 px-2">
          {links.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                [
                  "flex items-center justify-between rounded-comfy px-3 py-2 text-small font-signature transition-colors",
                  isActive
                    ? "bg-white/[0.05] text-text-primary"
                    : "text-text-secondary hover:bg-white/[0.03] hover:text-text-primary",
                ].join(" ")
              }
            >
              <span>{item.label}</span>
              <span className="text-label text-text-quaternary">{item.uc}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-white/[0.05] bg-bg-panel px-6 py-3">
          <div className="text-caption text-text-tertiary">
            Logged in as{" "}
            <span className="text-text-secondary">{user.full_name}</span>
            <span className="mx-2 text-text-quaternary">·</span>
            <span className="text-text-tertiary">{user.email}</span>
          </div>
          <div className="flex items-center gap-2">
            {showToggle && (
              <div className="flex items-center rounded-full border border-border-primary p-0.5">
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
              Sign out
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto px-8 py-8">{children}</main>
      </div>
    </div>
  );
}
