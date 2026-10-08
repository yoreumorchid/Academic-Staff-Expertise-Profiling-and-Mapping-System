"""UC-11 expertise-tag review and refinement routes."""
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.api.profile_responses import expertise_link_to_out
from app.core.exceptions import ValidationFailure
from app.db.models import ExpertiseTag, User, UserExpertiseTag
from app.db.session import get_session
from app.schemas import RefineTagsRequest, UserExpertiseTagOut
from app.services.embeddings import embed_texts
from app.services.sync_queue import ensure_user_sync_inactive

router = APIRouter(tags=["profile"])


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
    return [expertise_link_to_out(link) for link in rows]


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
    await ensure_user_sync_inactive(session, actor.id)

    if payload.remove_tag_ids:
        stmt = (
            select(UserExpertiseTag)
            .where(UserExpertiseTag.user_id == actor.id)
            .where(UserExpertiseTag.tag_id.in_(payload.remove_tag_ids))
        )
        for link in (await session.execute(stmt)).scalars().all():
            await session.delete(link)

    if payload.validate_tag_ids:
        stmt = (
            select(UserExpertiseTag)
            .where(UserExpertiseTag.user_id == actor.id)
            .where(UserExpertiseTag.tag_id.in_(payload.validate_tag_ids))
        )
        for link in (await session.execute(stmt)).scalars().all():
            link.validated = True
            link.source = "user_validated"

    added_labels = [label.strip() for label in payload.add_labels if label.strip()]
    if added_labels:
        await _add_custom_tags(session, actor.id, added_labels)

    await session.commit()

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
    return [expertise_link_to_out(link) for link in remaining]


async def _add_custom_tags(
    session: AsyncSession, user_id: UUID, labels: List[str]
) -> None:
    existing_stmt = select(ExpertiseTag).where(
        ExpertiseTag.canonical_label.in_(labels)
    )
    existing = {
        row.canonical_label: row
        for row in (await session.execute(existing_stmt)).scalars().all()
    }
    labels_to_embed = [label for label in labels if label not in existing]
    new_tags: dict[str, ExpertiseTag] = {}
    for label in labels_to_embed:
        tag = ExpertiseTag(canonical_label=label)
        session.add(tag)
        new_tags[label] = tag

    if labels_to_embed:
        vectors = await embed_texts(labels_to_embed)
        for label, vector in zip(labels_to_embed, vectors):
            new_tags[label].embedding = vector
    await session.flush()

    link_stmt = select(UserExpertiseTag.tag_id).where(
        UserExpertiseTag.user_id == user_id
    )
    owned = {row[0] for row in (await session.execute(link_stmt)).all()}

    for label in labels:
        tag = existing.get(label) or new_tags.get(label)
        if tag is None or tag.id in owned:
            continue
        session.add(
            UserExpertiseTag(
                user_id=user_id,
                tag_id=tag.id,
                confidence=1.0,
                source="user_added",
                validated=True,
            )
        )
