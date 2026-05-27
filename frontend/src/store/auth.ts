import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ActiveView, CurrentUser } from "../types";
import { api, setAuthToken } from "../api/client";

interface AuthState {
  token: string | null;
  user: CurrentUser | null;
  activeView: ActiveView;
  hydrate: () => void;
  login: (token: string, user: CurrentUser) => void;
  logout: () => void;
  refreshMe: () => Promise<void>;
  setActiveView: (view: ActiveView) => void;
}

/**
 * Global auth + view-toggle store (UC-3, UC-6, FR-012).
 *
 * ``activeView`` drives the dual-role switcher described in
 * instructions.md §2.3: toggling does not destroy the session, it merely
 * swaps the sidebar navigation array between the two portals.
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      activeView: "staff",

      hydrate: () => {
        const { token } = get();
        if (token) setAuthToken(token);
      },

      login: (token, user) => {
        setAuthToken(token);
        const defaultView: ActiveView =
          user.role === "faculty_administrator" ? "admin" : "staff";
        set({ token, user, activeView: defaultView });
      },

      logout: () => {
        setAuthToken(null);
        set({ token: null, user: null, activeView: "staff" });
      },

      refreshMe: async () => {
        const response = await api.get<CurrentUser>("/auth/me");
        set({ user: response.data });
      },

      setActiveView: (view) => {
        const { user } = get();
        if (!user) return;
        // Guard: only dual-role users may flip into the opposite portal.
        if (view === "admin" && user.portfolios.length === 0) return;
        if (view === "staff" && user.role !== "academic_staff" && !user.is_dual_role) return;
        set({ activeView: view });
      },
    }),
    {
      name: "expertise-insight-auth",
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        activeView: state.activeView,
      }),
    }
  )
);
