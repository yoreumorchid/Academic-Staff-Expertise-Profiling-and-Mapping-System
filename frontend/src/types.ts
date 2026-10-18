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
  sync_job_id: string | null;
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
  start_date: string | null;
  end_date: string | null;
}

export interface AcademicBackgroundInput {
  category: AcademicBackgroundCategory;
  title: string;
  organization?: string | null;
  description?: string | null;
  start_date?: string | null;
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

export type SyncProgressStage =
  | "queued"
  | "resolving_profile"
  | "fetching_publications"
  | "processing_abstracts"
  | "extracting_keywords"
  | "normalizing_tags"
  | "saving_results"
  | "finalizing"
  | "completed"
  | "failed";

export interface SyncJob {
  id: string;
  trigger: SyncTrigger;
  status: SyncJobStatus;
  progress_stage: SyncProgressStage;
  publications_added: number;
  tags_added: number;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
}

export interface SyncStatus {
  active: boolean;
  job_id: string | null;
  status: SyncJobStatus | null;
  progress_stage: SyncProgressStage | null;
  trigger: SyncTrigger | null;
  started_at: string | null;
  finished_at: string | null;
  publications_added: number;
  tags_added: number;
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

export interface StaffDirectoryPage {
  items: StaffDirectoryEntry[];
  total: number;
  department_count: number;
  tagged_count: number;
  page: number;
  page_size: number;
  total_pages: number;
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

export interface DocumentPreviewSection {
  id: string;
  filename: string;
  section: string;
  excerpt: string;
  included_by_default: boolean;
  token_count: number;
}

export interface DocumentPreview {
  sections: DocumentPreviewSection[];
  warnings: string[];
  appears_single_course: boolean;
  embedding_model: string;
  chunk_max_tokens: number;
  overlap_tokens: number;
  max_source_tokens: number;
  max_chunks: number;
  warning_source_tokens: number;
}

export interface SpecIngestResponse {
  id: string;
  spec_type: SpecificationType;
  title: string;
  source_filename: string | null;
  latest_report_id: string | null;
}

export interface MappingReportEntry {
  user_id: string;
  rank: number;
  cosine_score: number;
  spreading_score: number;
  combined_score: number;
}

export interface MappingReport {
  id: string;
  spec_id: string;
  spec_title: string;
  spec_text: string;
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
  peer_filename: string | null;
  detected_section: string | null;
  source_excerpt: string | null;
  nearest_staff_id: string | null;
  nearest_staff_name: string | null;
  nearest_cluster_label: string | null;
  nearest_cluster_distance: number | null;
  coverage_classification: "covered" | "partially_covered" | "candidate_gap" | null;
  review_status: "pending_administrator_review" | null;
  external_source_id: string | null;
  external_subfield: string | null;
  external_works_count: number | null;
  external_updated_date: string | null;
}

export interface BenchmarkSourcePayload {
  provider?: string;
  retrieved_at?: string;
  scope?: { id?: string; display_name?: string; updated_date?: string };
  selection?: {
    strategy?: string;
    topics_per_subfield?: number;
    time_series_used?: boolean;
  };
  embedding_model?: string;
  distance_formula?: string;
  interpretation?: string;
  [key: string]: unknown;
}

export interface BenchmarkRun {
  id: string;
  benchmark_type: BenchmarkType;
  narrative: string | null;
  source_payload: BenchmarkSourcePayload | null;
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
  source_relative_priority: number;
  source_weight: number;
  weighted_priority_score: number;
  recommendation: string | null;
  peer_filename: string | null;
  detected_section: string | null;
  source_excerpt: string | null;
  nearest_staff_id: string | null;
  nearest_staff_name: string | null;
  nearest_cluster_label: string | null;
  nearest_cluster_distance: number | null;
  coverage_classification: "covered" | "partially_covered" | "candidate_gap" | null;
  review_status: "pending_administrator_review" | null;
  external_source_id: string | null;
  external_subfield: string | null;
  external_works_count: number | null;
  external_updated_date: string | null;
}

export interface GapAnalysisWeighting {
  status: "provisional_pending_faculty_uat";
  global_weight: number;
  peer_weight: number;
  normalization: "within_source_dense_rank_percentile";
  formula: string;
  interpretation: string;
}

export interface GapAnalysisReport {
  narrative: string;
  white_spaces: GapAnalysisItem[];
  global_run_id: string | null;
  peer_run_id: string | null;
  missing_sources: BenchmarkType[];
  warnings: string[];
  weighting: GapAnalysisWeighting;
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

