"""Pydantic v2 request and response schemas.

Schemas are grouped by use case to make the mapping between the spec
matrix and the wire contract auditable.
"""
from __future__ import annotations

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


class _ORM(BaseModel):
    """Shared base enabling SQLAlchemy ORM conversion."""

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# UC-1 — registration
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    department: Optional[str] = Field(default=None, max_length=255)
    orcid_id: Optional[str] = Field(default=None, min_length=19, max_length=19)
    portfolio: Optional[PortfolioType] = None

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
        return self


class RegisterResponse(_ORM):
    id: UUID
    email: EmailStr
    status: AccountStatus
    role: UserRole
    is_dual_role: bool


# ---------------------------------------------------------------------------
# UC-2 — authorize registration
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# UC-3 — login
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "CurrentUserOut"


# ---------------------------------------------------------------------------
# UC-4 — reset password
# ---------------------------------------------------------------------------


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def _match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Password confirmation does not match.")
        return self


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def _match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Password confirmation does not match.")
        return self


# ---------------------------------------------------------------------------
# UC-6 — current user / portfolios
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# UC-10 — academic background
# ---------------------------------------------------------------------------


class AcademicBackgroundBase(BaseModel):
    category: AcademicBackgroundCategory
    title: str = Field(min_length=1, max_length=255)
    organization: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    start_date: date
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


# ---------------------------------------------------------------------------
# UC-9 — supplement abstract
# ---------------------------------------------------------------------------


class SupplementAbstractRequest(BaseModel):
    abstract_text: str = Field(min_length=200, max_length=20_000)


# ---------------------------------------------------------------------------
# UC-11 — expertise tags
# ---------------------------------------------------------------------------


class ExpertiseTagOut(_ORM):
    id: UUID
    canonical_label: str
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


# ---------------------------------------------------------------------------
# UC-12 — sync job
# ---------------------------------------------------------------------------


class SyncJobOut(_ORM):
    id: UUID
    trigger: SyncTrigger
    status: SyncJobStatus
    publications_added: int
    tags_added: int
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str]


# ---------------------------------------------------------------------------
# UC-13 / UC-14 — spec ingestion and mapping
# ---------------------------------------------------------------------------


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
    is_cross_department: bool


class MappingReportOut(_ORM):
    id: UUID
    spec_id: UUID
    summary: Optional[str]
    entries: List[MappingReportEntryOut]


# ---------------------------------------------------------------------------
# UC-15 / UC-16 / UC-17 — benchmarking
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# UC-18 — portfolio snapshot export
# ---------------------------------------------------------------------------


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


# Resolve forward references.
TokenResponse.model_rebuild()
PendingRegistrationOut.model_rebuild()
