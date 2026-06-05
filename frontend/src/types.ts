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

// ---------------------------------------------------------------------------
// UC-11 — expertise tags
// ---------------------------------------------------------------------------

export interface ExpertiseTag {
  id: string;
  canonical_label: string;
  domain: string | null;
}

export interface UserExpertiseTag {
  id: string;
  tag: ExpertiseTag;
  confidence: number;
  source: string;
  validated: boolean;
}

export interface RefineTagsRequest {
  remove_tag_ids: string[];
  validate_tag_ids: string[];
  add_labels: string[];
}

// ---------------------------------------------------------------------------
// UC-10 — academic background
// ---------------------------------------------------------------------------

export type AcademicBackgroundCategory =
  | "education"
  | "appointment"
  | "award"
  | "service";

export interface AcademicBackground {
  id: string;
  category: AcademicBackgroundCategory;
  title: string;
  organization: string | null;
  description: string | null;
  start_date: string;
  end_date: string | null;
}

export interface AcademicBackgroundInput {
  category: AcademicBackgroundCategory;
  title: string;
  organization?: string | null;
  description?: string | null;
  start_date: string;
  end_date?: string | null;
}

// ---------------------------------------------------------------------------
// UC-9 — publications
// ---------------------------------------------------------------------------

export interface Publication {
  id: string;
  doi: string;
  title: string | null;
  venue: string | null;
  publication_year: number | null;
  abstract_missing: boolean;
  abstract_text: string | null;
}

// ---------------------------------------------------------------------------
// UC-12 — sync jobs
// ---------------------------------------------------------------------------

export type SyncTrigger = "first_login" | "manual" | "quarterly";

export type SyncJobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "no_new_data"
  | "failed";

export interface SyncJob {
  id: string;
  trigger: SyncTrigger;
  status: SyncJobStatus;
  publications_added: number;
  tags_added: number;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
}

// ---------------------------------------------------------------------------
// UC-7 — staff directory
// ---------------------------------------------------------------------------

export interface StaffDirectoryEntry {
  id: string;
  full_name: string;
  email: string;
  department: string | null;
  tag_labels: string[];
}

export interface StaffProfileDetail extends StaffDirectoryEntry {
  publications: Publication[];
  expertise: UserExpertiseTag[];
}

export type StaffSearchCategory =
  | "all"
  | "name"
  | "expertise"
  | "publication"
  | "department";

// ---------------------------------------------------------------------------
// UC-13 / UC-14 — mapping
// ---------------------------------------------------------------------------

export type SpecificationType = "course" | "grant";

export interface SpecIngestResponse {
  id: string;
  spec_type: SpecificationType;
  title: string;
  source_filename: string | null;
}

export interface MappingReportEntry {
  user_id: string;
  rank: number;
  cosine_score: number;
  spreading_score: number;
  combined_score: number;
  is_cross_department: boolean;
}

export interface MappingReport {
  id: string;
  spec_id: string;
  summary: string | null;
  entries: MappingReportEntry[];
}

// ---------------------------------------------------------------------------
// UC-15 / UC-16 / UC-17 — benchmarking
// ---------------------------------------------------------------------------

export type BenchmarkType = "global" | "peer";

export interface BenchmarkWhiteSpace {
  domain_label: string;
  displacement_score: number;
  recommendation: string | null;
}

export interface BenchmarkRun {
  id: string;
  benchmark_type: BenchmarkType;
  narrative: string | null;
  visualization_payload: VisualizationPayload | null;
  white_spaces: BenchmarkWhiteSpace[];
}

export interface VisualizationPoint {
  x: number;
  y: number;
  label: string;
  cluster: number | null;
  kind: "internal" | "global" | "peer";
}

export interface VisualizationPayload {
  points: VisualizationPoint[];
}

export interface GapAnalysisItem {
  source: string;
  domain_label: string;
  displacement_score: number;
  recommendation: string | null;
}

export interface GapAnalysisReport {
  narrative: string;
  white_spaces: GapAnalysisItem[];
  global_run_id: string | null;
  peer_run_id: string | null;
}

// ---------------------------------------------------------------------------
// UC-18 — export snapshot
// ---------------------------------------------------------------------------

export interface ExportSnapshotRequest {
  include_tag_ids: string[];
  include_publication_ids: string[];
  include_background_ids: string[];
  format: "pdf" | "docx";
  use_defaults: boolean;
}

