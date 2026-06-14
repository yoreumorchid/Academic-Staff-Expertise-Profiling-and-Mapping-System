"""Staff-side profile, expertise and academic-background endpoints.

Covers:

* UC-7  — administrator browsing of staff directory and global header
          search (also exposed here because the data shape is identical).
* UC-9  — supplementing missing publication abstracts.
* UC-10 — manual academic background CRUD.
* UC-11 — expertise tag refinement (validate, remove, add).
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationFailure
from app.db.models import (
    AcademicBackground,
    AcademicBackgroundCategory,
    AccountStatus,
    ExpertiseTag,
    Publication,
    PublicationAbstract,
    User,
    UserExpertiseTag,
    UserRole,
)
from app.db.session import get_session
from app.schemas import (
    AcademicBackgroundCreate,
    AcademicBackgroundOut,
    AcademicBackgroundUpdate,
    ExpertiseTagOut,
    PublicationOut,
    RefineTagsRequest,
    StaffDirectoryEntry,
    StaffProfileDetail,
    StaffSearchQuery,
    SupplementAbstractRequest,
    UserExpertiseTagOut,
)
from app.services.document_extract import extract_text_from_upload
from app.services.embeddings import embed_text, embed_texts
from app.services.harvest import HarvestService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


# ===========================================================================
# UC-7 — staff directory and search
# ===========================================================================


@router.get(
    "/staff",
    response_model=List[StaffDirectoryEntry],
    summary="UC-7 — Faculty Administrator browses or searches staff profiles.",
)
async def search_staff(
    query: StaffSearchQuery = Depends(),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> List[StaffDirectoryEntry]:
    # UC-7 alt flow: a global header search providing the keyword without
    # a category is treated as a name search by default.
    if actor.role != UserRole.FACULTY_ADMINISTRATOR and not actor.is_dual_role:
        raise ForbiddenError("Only administrators may browse the staff directory.")

    stmt = (
        select(User)
        # Include true academic staff AND dual-role faculty admins who
        # also hold an academic-staff identity (FR-012). Without the
        # ``is_dual_role`` branch a dual-role admin would never surface
        # in the global header search.
        .where(
            or_(
                User.role == UserRole.ACADEMIC_STAFF,
                User.is_dual_role.is_(True),
            )
        )
        .where(User.status == AccountStatus.ACTIVE)
        .options(
            selectinload(User.expertise_links).selectinload(UserExpertiseTag.tag),
            selectinload(User.publications),
        )
    )
    if query.department:
        stmt = stmt.where(User.department.ilike(f"%{query.department}%"))

    rows = list((await session.execute(stmt)).scalars().all())

    if query.q:
        keyword = query.q.strip().lower()
        if not keyword:
            raise ValidationFailure("Provide a search term to query staff profiles.")
        category = query.category or "name"

        def matches(user: User) -> bool:
            if category == "name":
                return keyword in user.full_name.lower()
            if category == "department":
                return bool(user.department and keyword in user.department.lower())
            if category == "expertise":
                return any(
                    keyword in link.tag.canonical_label.lower()
                    for link in user.expertise_links
                )
            if category == "publication":
                return any(
                    keyword in ((pub.title or "") + " " + (pub.venue or "") + " " + (pub.doi or "")).lower()
                    for pub in user.publications
                )
            if category == "all":
                # UC-7 — full-text deep search when no filter is active.
                if keyword in user.full_name.lower():
                    return True
                if user.department and keyword in user.department.lower():
                    return True
                if any(
                    keyword in link.tag.canonical_label.lower()
                    for link in user.expertise_links
                ):
                    return True
                if any(
                    keyword in ((pub.title or "") + " " + (pub.venue or "") + " " + (pub.doi or "")).lower()
                    for pub in user.publications
                ):
                    return True
                return False
            return False

        rows = [u for u in rows if matches(u)]

    if query.tag_label:
        rows = [
            u
            for u in rows
            if any(
                query.tag_label.lower() in link.tag.canonical_label.lower()
                for link in u.expertise_links
            )
        ]

    return [
        StaffDirectoryEntry(
            id=u.id,
            full_name=u.full_name,
            email=u.email,
            department=u.department,
            tag_labels=[link.tag.canonical_label for link in u.expertise_links],
        )
        for u in rows
    ]


@router.get(
    "/staff/{user_id}",
    response_model=StaffProfileDetail,
    summary="UC-7 — Render the comprehensive staff expertise profile.",
)
async def get_staff_profile(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> StaffProfileDetail:
    if actor.role != UserRole.FACULTY_ADMINISTRATOR and actor.id != user_id:
        raise ForbiddenError("You may only view your own profile.")
    user = await _load_full_profile(session, user_id)
    return StaffProfileDetail(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        department=user.department,
        tag_labels=[link.tag.canonical_label for link in user.expertise_links],
        publications=[_pub_to_out(p) for p in user.publications],
        expertise=[_link_to_out(link) for link in user.expertise_links],
    )


# ===========================================================================
# UC-9 — publication abstract supplementation
# ===========================================================================


@router.get(
    "/publications",
    response_model=List[PublicationOut],
    summary="UC-9 — List harvested publications and flag missing abstracts.",
)
async def list_my_publications(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> List[PublicationOut]:
    stmt = (
        select(Publication)
        .where(Publication.user_id == actor.id)
        .options(selectinload(Publication.abstract))
        .order_by(Publication.publication_year.desc().nullslast())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_pub_to_out(row) for row in rows]


@router.post(
    "/publications/{publication_id}/abstract",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="UC-9 — Supplement a missing abstract via pasted text.",
)
async def supplement_abstract_text(
    publication_id: UUID,
    payload: SupplementAbstractRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> None:
    await _persist_supplemented_abstract(
        session, actor, publication_id, payload.abstract_text
    )


@router.post(
    "/publications/{publication_id}/abstract/upload",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="UC-9 alt — Supplement a missing abstract via PDF/DOCX upload.",
)
async def supplement_abstract_file(
    publication_id: UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> None:
    buffer = await file.read()
    text = await extract_text_from_upload(file.filename or "upload", buffer)
    await _persist_supplemented_abstract(session, actor, publication_id, text)


# ===========================================================================
# UC-10 — academic background CRUD
# ===========================================================================


@router.get(
    "/background",
    response_model=List[AcademicBackgroundOut],
    summary="UC-10 — List the actor's academic background records.",
)
async def list_background(
    category: Optional[AcademicBackgroundCategory] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> List[AcademicBackgroundOut]:
    stmt = select(AcademicBackground).where(AcademicBackground.user_id == actor.id)
    if category is not None:
        stmt = stmt.where(AcademicBackground.category == category)
    stmt = stmt.order_by(AcademicBackground.start_date.desc())
    rows = (await session.execute(stmt)).scalars().all()
    return [AcademicBackgroundOut.model_validate(row) for row in rows]


@router.post(
    "/background",
    response_model=AcademicBackgroundOut,
    status_code=status.HTTP_201_CREATED,
    summary="UC-10 — Create a new background record.",
)
async def create_background(
    payload: AcademicBackgroundCreate,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> AcademicBackgroundOut:
    record = AcademicBackground(user_id=actor.id, **payload.model_dump())
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return AcademicBackgroundOut.model_validate(record)


@router.put(
    "/background/{record_id}",
    response_model=AcademicBackgroundOut,
    summary="UC-10 alt — Update an existing background record.",
)
async def update_background(
    record_id: UUID,
    payload: AcademicBackgroundUpdate,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> AcademicBackgroundOut:
    record = await session.get(AcademicBackground, record_id)
    if record is None or record.user_id != actor.id:
        raise NotFoundError("Background record not found.")
    for key, value in payload.model_dump().items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return AcademicBackgroundOut.model_validate(record)


@router.delete(
    "/background/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="UC-10 — Delete a background record.",
)
async def delete_background(
    record_id: UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> None:
    record = await session.get(AcademicBackground, record_id)
    if record is None or record.user_id != actor.id:
        raise NotFoundError("Background record not found.")
    await session.delete(record)
    await session.commit()


# ===========================================================================
# UC-10 alt — CSV bulk upload + template download
# ===========================================================================

_VALID_CATEGORIES = {c.value for c in AcademicBackgroundCategory}
_BACKGROUND_CSV_HEADER = [
    "category", "title", "organization",
    "description", "start_date", "end_date",
]
_TEMPLATE_EXAMPLE = """category,title,organization,description,start_date,end_date
education,PhD in Computer Science,University of Malaya,Dissertation on semantic mapping algorithms,2018-09-01,2022-06-30
award,Best Paper Award,IEEE,Outstanding contribution to semantic web research,2023-06-15,
"""


@router.get(
    "/background/template",
    summary="UC-10 — Download a CSV template for bulk academic background import.",
)
async def download_background_template(
    actor: User = Depends(get_current_user),
) -> Response:
    """Return a pre-formatted CSV file that users can populate offline."""
    return Response(
        content=_TEMPLATE_EXAMPLE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=academic_background_template.csv"},
    )


@router.post(
    "/background/upload",
    response_model=List[AcademicBackgroundOut],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "UC-10 alt — Bulk-import academic background records from a CSV file."
    ),
)
async def upload_background_csv(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> List[AcademicBackgroundOut]:
    """Parse, validate, and insert academic background records from CSV."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise ValidationFailure("Only CSV files are accepted.")

    raw = (await file.read()).decode("utf-8-sig").strip()
    if not raw:
        raise ValidationFailure("The uploaded CSV file is empty.")

    reader = csv.DictReader(io.StringIO(raw))
    if reader.fieldnames is None:
        raise ValidationFailure("Could not parse CSV header.")

    # Normalise header to lower-case, stripped.
    actual_cols = [h.strip().lower() for h in reader.fieldnames]
    if actual_cols != _BACKGROUND_CSV_HEADER:
        raise ValidationFailure(
            "CSV header mismatch. Expected columns: "
            + ", ".join(_BACKGROUND_CSV_HEADER)
            + ". Got: "
            + ", ".join(actual_cols)
        )

    row_errors: List[str] = []
    parsed_rows: List[dict] = []

    for idx, raw_row in enumerate(reader, start=2):  # row 1 = header
        row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items()}
        errors: List[str] = []

        # --- category ---
        cat = row.get("category", "").strip().lower()
        if not cat:
            errors.append("category is required")
        elif cat not in _VALID_CATEGORIES:
            errors.append(
                f"category '{cat}' is invalid; must be one of: "
                + ", ".join(sorted(_VALID_CATEGORIES))
            )

        # --- title ---
        title = row.get("title", "")
        if not title:
            errors.append("title is required")
        elif len(title) > 255:
            errors.append("title exceeds 255 characters")

        # --- organization ---
        org = row.get("organization", "")
        if len(org) > 255:
            errors.append("organization exceeds 255 characters")

        # --- description ---
        desc = row.get("description", "")

        # --- start_date / end_date ---
        start_date_str = row.get("start_date", "")
        end_date_str = row.get("end_date", "")

        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = date.fromisoformat(start_date_str)
            except ValueError:
                errors.append(
                    f"start_date '{start_date_str}' is not a valid YYYY-MM-DD date"
                )
        if end_date_str:
            try:
                end_date = date.fromisoformat(end_date_str)
            except ValueError:
                errors.append(
                    f"end_date '{end_date_str}' is not a valid YYYY-MM-DD date"
                )

        if start_date and end_date and end_date < start_date:
            errors.append(
                f"end_date ({end_date_str}) is before start_date ({start_date_str})"
            )

        if errors:
            row_errors.append(f"Row {idx}: " + "; ".join(errors))
        else:
            parsed_rows.append(
                {
                    "category": cat,
                    "title": title,
                    "organization": org or None,
                    "description": desc or None,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )

    if row_errors:
        raise ValidationFailure(
            "CSV validation failed:\n" + "\n".join(row_errors[:20])
        )

    if not parsed_rows:
        raise ValidationFailure("CSV contains no valid data rows.")

    records: List[AcademicBackground] = []
    for pr in parsed_rows:
        rec = AcademicBackground(user_id=actor.id, **pr)
        session.add(rec)
        records.append(rec)

    await session.commit()
    for rec in records:
        await session.refresh(rec)

    return [AcademicBackgroundOut.model_validate(r) for r in records]


# ===========================================================================
# UC-11 — expertise tag refinement
# ===========================================================================


@router.get(
    "/expertise",
    response_model=List[UserExpertiseTagOut],
    summary="UC-11 — List the actor's AI-generated expertise tags.",
)
async def list_expertise(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> List[UserExpertiseTagOut]:
    stmt = (
        select(UserExpertiseTag)
        .where(UserExpertiseTag.user_id == actor.id)
        .options(selectinload(UserExpertiseTag.tag))
        .order_by(UserExpertiseTag.confidence.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_link_to_out(link) for link in rows]


@router.post(
    "/expertise/refine",
    response_model=List[UserExpertiseTagOut],
    summary="UC-11 — Validate, remove, or add expertise tags.",
)
async def refine_expertise(
    payload: RefineTagsRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> List[UserExpertiseTagOut]:
    # Remove unwanted tags first.
    if payload.remove_tag_ids:
        stmt = (
            select(UserExpertiseTag)
            .where(UserExpertiseTag.user_id == actor.id)
            .where(UserExpertiseTag.tag_id.in_(payload.remove_tag_ids))
        )
        for link in (await session.execute(stmt)).scalars().all():
            await session.delete(link)

    # Mark validated tags.
    if payload.validate_tag_ids:
        stmt = (
            select(UserExpertiseTag)
            .where(UserExpertiseTag.user_id == actor.id)
            .where(UserExpertiseTag.tag_id.in_(payload.validate_tag_ids))
        )
        for link in (await session.execute(stmt)).scalars().all():
            link.validated = True
            link.source = "user_validated"

    # Add custom labels — perform a lightweight real-time normalization
    # by reusing the canonical_label exact-match index.
    added_labels = [lbl.strip() for lbl in payload.add_labels if lbl.strip()]
    if added_labels:
        existing_stmt = select(ExpertiseTag).where(
            ExpertiseTag.canonical_label.in_(added_labels)
        )
        existing = {
            row.canonical_label: row
            for row in (await session.execute(existing_stmt)).scalars().all()
        }
        to_embed = [lbl for lbl in added_labels if lbl not in existing]
        new_tag_map: dict[str, ExpertiseTag] = {}
        for label in to_embed:
            tag = ExpertiseTag(canonical_label=label)
            session.add(tag)
            new_tag_map[label] = tag
        if to_embed:
            vectors = await embed_texts(to_embed)
            for label, vector in zip(to_embed, vectors):
                new_tag_map[label].embedding = vector
        await session.flush()

        link_stmt = select(UserExpertiseTag.tag_id).where(
            UserExpertiseTag.user_id == actor.id
        )
        owned = {row[0] for row in (await session.execute(link_stmt)).all()}

        for label in added_labels:
            tag = existing.get(label) or new_tag_map.get(label)
            if tag is None or tag.id in owned:
                continue
            session.add(
                UserExpertiseTag(
                    user_id=actor.id,
                    tag_id=tag.id,
                    confidence=1.0,
                    source="user_added",
                    validated=True,
                )
            )

    await session.commit()

    # UC-11 exception: refuse to leave the profile empty.
    remaining_stmt = (
        select(UserExpertiseTag)
        .where(UserExpertiseTag.user_id == actor.id)
        .options(selectinload(UserExpertiseTag.tag))
    )
    remaining = (await session.execute(remaining_stmt)).scalars().all()
    if not remaining:
        raise ValidationFailure(
            "A profile requires at least one expertise tag for institutional "
            "visibility. Add or restore a tag before saving.",
        )
    return [_link_to_out(link) for link in remaining]


# ===========================================================================
# Helpers
# ===========================================================================


async def _load_full_profile(session: AsyncSession, user_id: UUID) -> User:
    stmt = (
        select(User)
        .where(
            User.id == user_id,
            or_(User.role == UserRole.ACADEMIC_STAFF, User.is_dual_role.is_(True)),
        )
        .options(
            selectinload(User.expertise_links).selectinload(UserExpertiseTag.tag),
            selectinload(User.publications).selectinload(Publication.abstract),
        )
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise NotFoundError("Academic staff profile not found.")
    return user


def _pub_to_out(pub: Publication) -> PublicationOut:
    return PublicationOut(
        id=pub.id,
        doi=pub.doi,
        title=pub.title,
        venue=pub.venue,
        publication_year=pub.publication_year,
        abstract_missing=pub.abstract_missing,
        abstract_text=pub.abstract.abstract_text if pub.abstract else None,
    )


def _link_to_out(link: UserExpertiseTag) -> UserExpertiseTagOut:
    return UserExpertiseTagOut(
        id=link.id,
        tag=ExpertiseTagOut.model_validate(link.tag),
        confidence=link.confidence,
        source=link.source,
        validated=link.validated,
    )


async def _persist_supplemented_abstract(
    session: AsyncSession,
    actor: User,
    publication_id: UUID,
    text: str,
) -> None:
    # Eager-load the abstract relationship — touching ``publication.abstract``
    # later would otherwise trigger a lazy load that crashes inside an async
    # session with ``MissingGreenlet``.
    stmt = (
        select(Publication)
        .where(Publication.id == publication_id)
        .options(selectinload(Publication.abstract))
    )
    publication = (await session.execute(stmt)).scalar_one_or_none()
    if publication is None or publication.user_id != actor.id:
        raise NotFoundError("Publication not found.")
    if len(text.strip()) < 200:
        # UC-9 exception: insufficient text length.
        raise ValidationFailure(
            "Provide a more comprehensive abstract (minimum 200 characters) "
            "for meaningful NLP extraction.",
        )

    # Step A — store the user-supplied abstract first. This must succeed
    # on its own; everything after is best-effort AI enrichment.
    if publication.abstract is None:
        publication.abstract = PublicationAbstract(
            publication_id=publication.id,
            abstract_text=text,
            source="manual",
            supplemented_by_user_id=actor.id,
        )
    else:
        publication.abstract.abstract_text = text
        publication.abstract.source = "manual"
        publication.abstract.supplemented_by_user_id = actor.id

    publication.abstract_missing = False
    await session.commit()

    # Step B — best-effort: refresh the publication embedding and re-run
    # the NLP/LLM pipeline. Any failure here is logged but never bubbles
    # up as a 500: the abstract is already saved and the user can
    # re-trigger NLP enrichment from the next quarterly sync.
    try:
        publication.embedding = await embed_text(text)
        await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception(
            "Embedding refresh failed for publication %s; abstract is saved",
            publication_id,
        )
        await session.rollback()

    try:
        await HarvestService(session).regenerate_tags_from_abstract(
            actor.id, text
        )
        await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception(
            "NLP tag regeneration failed for publication %s; abstract is saved",
            publication_id,
        )
        await session.rollback()
