import type { PortfolioType, UserRole, ActiveView, CurrentUser } from "../types";

/**
 * Sidebar specification derived from instructions.md §2.2.
 * Each entry maps to a specific Use Case ID per §4 rule 1 — no
 * decorative links are permitted.
 */
export interface NavItem {
  label: string;
  path: string;
  /** Use Case identifier this link satisfies. */
  uc: string;
}

const STAFF_LINKS: NavItem[] = [
  { label: "Profile Overview", path: "/staff/profile", uc: "UC-7/UC-11" },
  { label: "Expertise Tag Refinement", path: "/staff/tags", uc: "UC-11" },
  { label: "Academic Background", path: "/staff/background", uc: "UC-10" },
  { label: "Publications & Abstracts", path: "/staff/publications", uc: "UC-9" },
  { label: "Export Portfolio Snapshot", path: "/staff/export", uc: "UC-18" },
];

const PORTFOLIO_LINKS: Record<PortfolioType, NavItem[]> = {
  faculty_manager: [
    { label: "Pending Registrations", path: "/admin/registrations", uc: "UC-2" },
    { label: "Gap Analytics Overview", path: "/admin/gap", uc: "UC-15/17" },
    { label: "Global Benchmarking", path: "/admin/benchmarking/global", uc: "UC-15" },
    { label: "Staff Profiles", path: "/admin/staff", uc: "UC-7" },
  ],
  head_of_department: [
    { label: "Gap Analytics Overview", path: "/admin/gap", uc: "UC-17" },
    { label: "Semantic Course Mapping", path: "/admin/mapping/course", uc: "UC-13/14" },
    { label: "Research Grant Mapping", path: "/admin/mapping/grant", uc: "UC-13/14" },
    { label: "Staff Profiles", path: "/admin/staff", uc: "UC-7" },
  ],
  deputy_dean_research: [
    { label: "Research Grant Mapping", path: "/admin/mapping/grant", uc: "UC-13/14" },
    { label: "Staff Profiles", path: "/admin/staff", uc: "UC-7" },
  ],
  deputy_dean_ugpg: [
    { label: "Gap Analytics Overview", path: "/admin/gap", uc: "UC-17" },
    { label: "Semantic Course Mapping", path: "/admin/mapping/course", uc: "UC-13/14" },
    { label: "Staff Profiles", path: "/admin/staff", uc: "UC-7" },
  ],
};

export function sidebarForActiveView(
  user: CurrentUser,
  activeView: ActiveView
): NavItem[] {
  if (activeView === "staff") return STAFF_LINKS;

  // Merge portfolio-specific links, preserving order and de-duplicating
  // by path so multi-portfolio admins see a clean union.
  const merged: NavItem[] = [];
  const seen = new Set<string>();
  for (const p of user.portfolios) {
    for (const item of PORTFOLIO_LINKS[p.portfolio_type] ?? []) {
      if (!seen.has(item.path)) {
        merged.push(item);
        seen.add(item.path);
      }
    }
  }
  return merged;
}

export function canToggleView(user: CurrentUser): boolean {
  // FR-012: the toggle is visible only when the user truly holds both
  // an academic-staff identity and an administrative portfolio.
  if (user.role === "academic_staff") {
    return user.portfolios.length > 0;
  }
  return user.is_dual_role;
}

export function defaultViewFor(role: UserRole): ActiveView {
  return role === "faculty_administrator" ? "admin" : "staff";
}
