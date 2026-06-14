"""Pydantic v2 request and response schemas.

Schemas are grouped by use case to make the mapping between the spec
matrix and the wire contract auditable.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.security import is_valid_orcid
from app.db.models import (
    AcademicBackgroundCategory,
    AccountStatus,
    BenchmarkType,
    NotificationKind,
    PortfolioType,
    SpecificationType,
    SyncJobStatus,
    SyncTrigger,
    UserRole,
)


# Shared validation primitives (UM Email, password complexity, department).


UM_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@(um\.edu\.my|siswa\.um\.edu\.my)$")
# 8-16 chars: at least one lower, upper, digit and special.
PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)"
    r"(?=.*[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~])"
    r".{8,16}$"
)
DEPARTMENT_PATTERN = re.compile(r"^(?=.*[A-Za-z]).{2,100}$")


def _validate_um_email(value: str) -> str:
    v = value.strip().lower()
    if not UM_EMAIL_PATTERN.match(v):
        raise ValueError("UM Email must end with @um.edu.my")
    return v


def _validate_password(value: str) -> str:
    if not PASSWORD_PATTERN.match(value):
        raise ValueError(
            "Password must be 8-16 characters and include upper case, "
            "lower case, a digit, and a special character."
        )
    return value


def _validate_department(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    v = value.strip()
    if not DEPARTMENT_PATTERN.match(v):
        raise ValueError(
            "Department must be 2-100 characters and contain alphabetic characters."
        )
    return v


def _normalize_full_name(value: str) -> str:
    v = " ".join(value.split())  # collapse interior whitespace
    if not (1 <= len(v) <= 161):  # 80+1+80
        raise ValueError("Full name must be 1-161 characters.")
    return v.upper()


class _ORM(BaseModel):
    """Shared base enabling SQLAlchemy ORM conversion."""

    model_config = ConfigDict(from_attributes=True)



# UC-1 — registration



class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    department: Optional[str] = Field(default=None, max_length=255)
    orcid_id: Optional[str] = Field(default=None, min_length=19, max_length=19)
    portfolio: Optional[PortfolioType] = None

    @field_validator("full_name")
    @classmethod
    def _check_full_name(cls, v: str) -> str:
        return _normalize_full_name(v)

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return _validate_um_email(v)

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("department")
    @classmethod
    def _check_department(cls, v: Optional[str]) -> Optional[str]:
        return _validate_department(v)

    @field_validator("orcid_id")
    @classmethod
    def _check_orcid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not is_valid_orcid(v):
            raise ValueError("ORCID ID must match 0000-0000-0000-000X format.")
        return v

    @model_validator(mode="after")
    def _check_role_inputs(self) -> "RegisterRequest":
        # UC-1 Step 4.1: Academic Staff MUST provide ORCID + department.
        if self.role == UserRole.ACADEMIC_STAFF:
            if not self.orcid_id:
                raise ValueError("Academic Staff registration requires an ORCID ID.")
            if not self.department:
                raise ValueError("Academic Staff registration requires a department.")
        # UC-1 Step 4.2: Faculty Administrator MUST select a portfolio.
        if self.role == UserRole.FACULTY_ADMINISTRATOR and self.portfolio is None:
            raise ValueError("Faculty Administrator registration requires a portfolio.")
        # Dual role: when an admin provides ORCID, department is mandatory.
        if (
            self.role == UserRole.FACULTY_ADMINISTRATOR
            and self.orcid_id
            and not self.department
        ):
            raise ValueError(
                "Department is required when providing an ORCID as a Faculty Administrator."
            )
        return self


class RegisterResponse(_ORM):
    id: UUID
    email: EmailStr
    status: AccountStatus
    role: UserRole
    is_dual_role: bool



# UC-2 — authorize registration



class PendingRegistrationOut(_ORM):
    id: UUID
    full_name: str
    email: EmailStr
    role: UserRole
    department: Optional[str]
    portfolios: List["PortfolioOut"]
    orcid_id: Optional[str] = None
    created_at: datetime


class AuthorizeRequest(BaseModel):
    approve: bool



# UC-3 — login



class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "CurrentUserOut"



# UC-4 — reset password



class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _check_new_password(cls, v: str) -> str:
        return _validate_password(v)

    @model_validator(mode="after")
    def _match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Password confirmation does not match.")
        return self


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _check_new_password(cls, v: str) -> str:
        return _validate_password(v)

    @model_validator(mode="after")
    def _match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Password confirmation does not match.")
        return self



# UC-6 — current user / portfolios



class PortfolioOut(_ORM):
    portfolio_type: PortfolioType


class CurrentUserOut(_ORM):
    id: UUID
    full_name: str
    email: EmailStr
    role: UserRole
    status: AccountStatus
    department: Optional[str]
    is_dual_role: bool
    portfolios: List[PortfolioOut]
    orcid_id: Optional[str] = None



# UC-10 — academic background



class AcademicBackgroundBase(BaseModel):
    category: AcademicBackgroundCategory
    title: str = Field(min_length=1, max_length=255)
    organization: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @model_validator(mode="after")
    def _chronology(self) -> "AcademicBackgroundBase":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        return self


class AcademicBackgroundCreate(AcademicBackgroundBase):
    pass


class AcademicBackgroundUpdate(AcademicBackgroundBase):
    pass


class AcademicBackgroundOut(_ORM, AcademicBackgroundBase):
    id: UUID



# UC-9 — supplement abstract



class SupplementAbstractRequest(BaseModel):
    abstract_text: str = Field(min_length=200, max_length=20_000)



# UC-11 — expertise tags



class ExpertiseTagOut(_ORM):
    id: UUID
    canonical_label: str
    parent_label: Optional[str]
    domain: Optional[str]


class UserExpertiseTagOut(_ORM):
    id: UUID
    tag: ExpertiseTagOut
    confidence: float
    source: str
    validated: bool


class RefineTagsRequest(BaseModel):
    remove_tag_ids: List[UUID] = Field(default_factory=list)
    validate_tag_ids: List[UUID] = Field(default_factory=list)
    add_labels: List[str] = Field(default_factory=list)



# UC-12 — sync job



class SyncJobOut(_ORM):
    id: UUID
    trigger: SyncTrigger
    status: SyncJobStatus
    publications_added: int
    tags_added: int
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str]


class SyncStatusOut(BaseModel):
    """Lightweight payload for the sync-progress poller (UC-12)."""

    running: bool
    trigger: Optional[SyncTrigger] = None
    started_at: Optional[datetime] = None



# UC-13 / UC-14 — spec ingestion and mapping



class SpecIngestRequest(BaseModel):
    spec_type: SpecificationType
    title: str = Field(min_length=1, max_length=255)
    raw_text: str = Field(min_length=80)


class MappingReportEntryOut(_ORM):
    user_id: UUID
    rank: int
    cosine_score: float
    spreading_score: float
    combined_score: float


class MappingReportOut(_ORM):
    id: UUID
    spec_id: UUID
    spec_title: str
    spec_text: str
    summary: Optional[str]
    entries: List[MappingReportEntryOut]



# UC-15 / UC-16 / UC-17 — benchmarking



class BenchmarkWhiteSpaceOut(_ORM):
    domain_label: str
    displacement_score: float
    recommendation: Optional[str]


class BenchmarkRunOut(_ORM):
    id: UUID
    benchmark_type: BenchmarkType
    narrative: Optional[str]
    visualization_payload: Optional[dict]
    white_spaces: List[BenchmarkWhiteSpaceOut]



# UC-18 — portfolio snapshot export



class ExportSnapshotRequest(BaseModel):
    include_tag_ids: List[UUID] = Field(default_factory=list)
    include_publication_ids: List[UUID] = Field(default_factory=list)
    include_background_ids: List[UUID] = Field(default_factory=list)
    format: str = Field(default="pdf", pattern="^(pdf|docx)$")
    use_defaults: bool = False

    @model_validator(mode="after")
    def _non_empty(self) -> "ExportSnapshotRequest":
        if not self.use_defaults and not (
            self.include_tag_ids or self.include_publication_ids or self.include_background_ids
        ):
            raise ValueError(
                "Select at least one data point or enable use_defaults (UC-18 exception)."
            )
        return self



# UC-7 — staff directory & search



class StaffDirectoryEntry(_ORM):
    id: UUID
    full_name: str
    email: EmailStr
    department: Optional[str]
    tag_labels: List[str]


class StaffProfileDetail(StaffDirectoryEntry):
    publications: List["PublicationOut"]
    expertise: List["UserExpertiseTagOut"]


class StaffSearchQuery(BaseModel):
    q: Optional[str] = None
    department: Optional[str] = None
    tag_label: Optional[str] = None
    category: Optional[str] = Field(
        default=None,
        pattern="^(all|name|expertise|publication|department)$",
        description="UC-7 alt flow — global header search category. 'all' performs a full-text scan across name, department, expertise, and publication metadata.",
    )



# UC-9 — publications view (with abstract status)



class PublicationOut(_ORM):
    id: UUID
    doi: str
    title: Optional[str]
    venue: Optional[str]
    publication_year: Optional[int]
    abstract_missing: bool
    abstract_text: Optional[str] = None



# UC-13 — file ingest response wrapper



class SpecIngestResponse(_ORM):
    id: UUID
    spec_type: SpecificationType
    title: str
    source_filename: Optional[str]
    latest_report_id: Optional[UUID] = None



# UC-17 — combined gap analysis report payload



class GapAnalysisItem(BaseModel):
    source: str
    domain_label: str
    displacement_score: float
    recommendation: Optional[str]


class GapAnalysisReport(BaseModel):
    narrative: str
    white_spaces: List[GapAnalysisItem]
    global_run_id: Optional[UUID] = None
    peer_run_id: Optional[UUID] = None


# Resolve forward references.
TokenResponse.model_rebuild()
PendingRegistrationOut.model_rebuild()
StaffProfileDetail.model_rebuild()
