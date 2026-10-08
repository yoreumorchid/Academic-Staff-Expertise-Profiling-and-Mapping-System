"""UC-9 publication listing and abstract-supplementation routes."""
from __future__ import annotations

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.api.profile_responses import publication_to_out
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationFailure
from app.db.models import Publication, PublicationAbstract, User
from app.db.session import get_session
from app.schemas import PublicationOut, SupplementAbstractRequest
from app.services.document_extract import extract_text_from_upload
from app.services.embeddings import embed_text
from app.services.harvest import HarvestService
from app.services.sync_queue import ensure_user_sync_inactive
from app.services.upload_validation import read_upload_limited

logger = logging.getLogger(__name__)

router = APIRouter(tags=["profile"])


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
    return [publication_to_out(row) for row in rows]


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
    await ensure_user_sync_inactive(session, actor.id)
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
    await ensure_user_sync_inactive(session, actor.id)
    buffer = await read_upload_limited(
        file, get_settings().max_document_upload_bytes
    )
    text = await extract_text_from_upload(
        file.filename or "upload", buffer, file.content_type
    )
    await _persist_supplemented_abstract(session, actor, publication_id, text)


async def _persist_supplemented_abstract(
    session: AsyncSession,
    actor: User,
    publication_id: UUID,
    text: str,
) -> None:
    # Eager-load the relationship to avoid an async lazy load (MissingGreenlet).
    stmt = (
        select(Publication)
        .where(Publication.id == publication_id)
        .options(selectinload(Publication.abstract))
    )
    publication = (await session.execute(stmt)).scalar_one_or_none()
    if publication is None or publication.user_id != actor.id:
        raise NotFoundError("Publication not found.")
    if len(text.strip()) < 200:
        raise ValidationFailure(
            "Provide a more comprehensive abstract (minimum 200 characters) "
            "for meaningful NLP extraction.",
        )

    # Persist the user input before best-effort AI enrichment.
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
        await HarvestService(session).regenerate_tags_from_abstract(actor.id, text)
        await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception(
            "NLP tag regeneration failed for publication %s; abstract is saved",
            publication_id,
        )
        await session.rollback()
