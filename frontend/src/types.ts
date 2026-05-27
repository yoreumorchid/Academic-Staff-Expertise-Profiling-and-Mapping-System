/**
 * Shared application types mirroring the backend Pydantic schemas.
 * Keep these in sync with backend/app/schemas.py when contracts evolve.
 */

export type UserRole = "academic_staff" | "faculty_administrator";

export type AccountStatus = "pending" | "active" | "rejected" | "suspended";

export type PortfolioType =
  | "faculty_manager"
  | "head_of_department"
  | "deputy_dean_research"
  | "deputy_dean_ugpg";

export interface Portfolio {
  portfolio_type: PortfolioType;
}

export interface CurrentUser {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  status: AccountStatus;
  department: string | null;
  is_dual_role: boolean;
  portfolios: Portfolio[];
  orcid_id: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: CurrentUser;
}

export type ActiveView = "staff" | "admin";
