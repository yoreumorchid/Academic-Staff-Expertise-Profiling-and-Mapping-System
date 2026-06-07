"""SQLAlchemy ORM models covering every entity in UC-1 through UC-18.

Schema overview (one table per concept, FK cascades aligned with the
deletion semantics described in the use cases):

* ``users``                  — credentials, status (UC-1/2/3/4).
* ``portfolios``             — administrator portfolio assignments (UC-6).
* ``orcid_profiles``         — ORCID linkage and last-sync state (UC-8/12).
* ``publications``           — DOI/abstract metadata (UC-8/9).
* ``publication_abstracts``  — supplemented abstracts (UC-9).
* ``expertise_tags``         — canonical normalized tag vocabulary.
* ``user_expertise_tags``    — many-to-many between users and tags (UC-8/11).
* ``academic_background``    — manually-entered roles/awards/education (UC-10).
* ``sync_jobs``              — manual or quarterly sync ledger (UC-12).
* ``course_grant_specs``     — ingested specifications (UC-13).
* ``mapping_reports``        — generated semantic matches (UC-14).
* ``mapping_report_entries`` — ranked staff results (UC-14).
* ``benchmark_runs``         — global/peer benchmarking executions (UC-15/16).
* ``benchmark_white_spaces`` — derived gap data points (UC-15/16/17).
* ``password_reset_tokens``  — UC-4.
* ``notification_log``       — UC-5 dispatch ledger.
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class UserRole(str, enum.Enum):
    """High-level account role chosen at registration (UC-1 step 3)."""

    ACADEMIC_STAFF = "academic_staff"
    FACULTY_ADMINISTRATOR = "faculty_administrator"


class PortfolioType(str, enum.Enum):
    """Administrator portfolios (UC-1 step 4 / UC-6)."""

    FACULTY_MANAGER = "faculty_manager"
    HEAD_OF_DEPARTMENT = "head_of_department"
    DEPUTY_DEAN_RESEARCH = "deputy_dean_research"
    DEPUTY_DEAN_UGPG = "deputy_dean_ugpg"


class AccountStatus(str, enum.Enum):
    """UC-1 / UC-2 account lifecycle."""

    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class AcademicBackgroundCategory(str, enum.Enum):
    """UC-10 input categories."""

    ADMINISTRATIVE_ROLE = "administrative_role"
    AWARD = "award"
    EDUCATION = "education"


class SyncJobStatus(str, enum.Enum):
    """UC-8 / UC-12 ledger states."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NO_NEW_DATA = "no_new_data"


class SyncTrigger(str, enum.Enum):
    FIRST_LOGIN = "first_login"
    MANUAL = "manual"
    QUARTERLY = "quarterly"


class SpecificationType(str, enum.Enum):
    """UC-13 — distinguishes course mapping from grant mapping."""

    COURSE = "course"
    GRANT = "grant"


class BenchmarkType(str, enum.Enum):
    """UC-15 / UC-16."""

    GLOBAL = "global"
    PEER = "peer"


class NotificationKind(str, enum.Enum):
    """UC-5 templates."""

    REGISTRATION_APPROVED = "registration_approved"
    REGISTRATION_REJECTED = "registration_rejected"
    PASSWORD_RESET = "password_reset"


# ---------------------------------------------------------------------------
# Core identity
# ---------------------------------------------------------------------------


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status"),
        nullable=False,
        default=AccountStatus.PENDING,
    )
    department: Mapped[Optional[str]] = mapped_column(String(255))
    is_dual_role: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    first_login_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    portfolios: Mapped[List["Portfolio"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    orcid_profile: Mapped[Optional["OrcidProfile"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    publications: Mapped[List["Publication"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    expertise_links: Mapped[List["UserExpertiseTag"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    academic_background: Mapped[List["AcademicBackground"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sync_jobs: Mapped[List["SyncJob"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reset_tokens: Mapped[List["PasswordResetToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Portfolio(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        UniqueConstraint("user_id", "portfolio_type", name="uq_user_portfolio"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_type: Mapped[PortfolioType] = mapped_column(
        Enum(PortfolioType, name="portfolio_type"), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="portfolios")


# ---------------------------------------------------------------------------
# ORCID + publications + abstracts (UC-8, UC-9)
# ---------------------------------------------------------------------------


class OrcidProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orcid_profiles"
    __table_args__ = (
        UniqueConstraint("orcid_id", name="uq_orcid_id"),
        CheckConstraint(
            "orcid_id ~ '^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]$'",
            name="ck_orcid_format",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    orcid_id: Mapped[str] = mapped_column(String(19), nullable=False)
    # Cached OpenAlex author identifier resolved on first sync.
    openalex_author_id: Mapped[Optional[str]] = mapped_column(String(64))
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="orcid_profile")


class Publication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "publications"
    __table_args__ = (
        UniqueConstraint("user_id", "doi", name="uq_publication_user_doi"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doi: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    venue: Mapped[Optional[str]] = mapped_column(String(512))
    publication_year: Mapped[Optional[int]] = mapped_column(Integer)
    openalex_id: Mapped[Optional[str]] = mapped_column(String(64))
    abstract_missing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(ARRAY(Float))

    user: Mapped[User] = relationship(back_populates="publications")
    abstract: Mapped[Optional["PublicationAbstract"]] = relationship(
        back_populates="publication", cascade="all, delete-orphan", uselist=False
    )


class PublicationAbstract(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "publication_abstracts"

    publication_id: Mapped[UUID] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    abstract_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="openalex")
    supplemented_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    publication: Mapped[Publication] = relationship(back_populates="abstract")


# ---------------------------------------------------------------------------
# Expertise tags (UC-8, UC-11)
# ---------------------------------------------------------------------------


class ExpertiseTag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expertise_tags"
    __table_args__ = (UniqueConstraint("canonical_label", name="uq_expertise_canonical"),)

    canonical_label: Mapped[str] = mapped_column(String(255), nullable=False)
    # parent_label: one level above canonical_label used for coarse-grained
    # course/grant mapping (e.g. "Computer Vision" for "Image Forensics").
    parent_label: Mapped[Optional[str]] = mapped_column(String(255))
    domain: Mapped[Optional[str]] = mapped_column(String(255))
    embedding: Mapped[Optional[List[float]]] = mapped_column(ARRAY(Float))

    user_links: Mapped[List["UserExpertiseTag"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )


class UserExpertiseTag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_expertise_tags"
    __table_args__ = (
        UniqueConstraint("user_id", "tag_id", name="uq_user_expertise_pair"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_id: Mapped[UUID] = mapped_column(
        ForeignKey("expertise_tags.id", ondelete="CASCADE"), nullable=False, index=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="ai")
    validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="expertise_links")
    tag: Mapped[ExpertiseTag] = relationship(back_populates="user_links")


# ---------------------------------------------------------------------------
# Academic background (UC-10)
# ---------------------------------------------------------------------------


class AcademicBackground(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "academic_background"
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_academic_background_chronology",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[AcademicBackgroundCategory] = mapped_column(
        Enum(AcademicBackgroundCategory, name="academic_background_category"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    organization: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date)

    user: Mapped[User] = relationship(back_populates="academic_background")


# ---------------------------------------------------------------------------
# Sync jobs (UC-8, UC-12)
# ---------------------------------------------------------------------------


class SyncJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sync_jobs"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trigger: Mapped[SyncTrigger] = mapped_column(
        Enum(SyncTrigger, name="sync_trigger"), nullable=False
    )
    status: Mapped[SyncJobStatus] = mapped_column(
        Enum(SyncJobStatus, name="sync_job_status"),
        nullable=False,
        default=SyncJobStatus.QUEUED,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    publications_added: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tags_added: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped[User] = relationship(back_populates="sync_jobs")


# ---------------------------------------------------------------------------
# Course / grant specifications + mapping reports (UC-13, UC-14)
# ---------------------------------------------------------------------------


class CourseGrantSpec(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "course_grant_specs"

    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    spec_type: Mapped[SpecificationType] = mapped_column(
        Enum(SpecificationType, name="specification_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_filename: Mapped[Optional[str]] = mapped_column(String(255))
    embedding: Mapped[Optional[List[float]]] = mapped_column(ARRAY(Float))

    reports: Mapped[List["MappingReport"]] = relationship(
        back_populates="spec", cascade="all, delete-orphan"
    )


class MappingReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mapping_reports"

    spec_id: Mapped[UUID] = mapped_column(
        ForeignKey("course_grant_specs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generated_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    summary: Mapped[Optional[str]] = mapped_column(Text)

    spec: Mapped[CourseGrantSpec] = relationship(back_populates="reports")
    entries: Mapped[List["MappingReportEntry"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="MappingReportEntry.rank",
    )


class MappingReportEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mapping_report_entries"
    __table_args__ = (
        UniqueConstraint("report_id", "user_id", name="uq_mapping_report_user"),
    )

    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("mapping_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    cosine_score: Mapped[float] = mapped_column(Float, nullable=False)
    spreading_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    combined_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_cross_department: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    report: Mapped[MappingReport] = relationship(back_populates="entries")


# ---------------------------------------------------------------------------
# Benchmarking (UC-15, UC-16, UC-17)
# ---------------------------------------------------------------------------


class BenchmarkRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_runs"

    triggered_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    benchmark_type: Mapped[BenchmarkType] = mapped_column(
        Enum(BenchmarkType, name="benchmark_type"), nullable=False
    )
    source_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    visualization_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    narrative: Mapped[Optional[str]] = mapped_column(Text)

    white_spaces: Mapped[List["BenchmarkWhiteSpace"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class BenchmarkWhiteSpace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_white_spaces"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain_label: Mapped[str] = mapped_column(String(255), nullable=False)
    displacement_score: Mapped[float] = mapped_column(Float, nullable=False)
    recommendation: Mapped[Optional[str]] = mapped_column(Text)

    run: Mapped[BenchmarkRun] = relationship(back_populates="white_spaces")


# ---------------------------------------------------------------------------
# Password reset + notifications (UC-4, UC-5)
# ---------------------------------------------------------------------------


class PasswordResetToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (UniqueConstraint("token", name="uq_password_reset_token"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="reset_tokens")


class NotificationLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_log"

    recipient_user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    kind: Mapped[NotificationKind] = mapped_column(
        Enum(NotificationKind, name="notification_kind"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
