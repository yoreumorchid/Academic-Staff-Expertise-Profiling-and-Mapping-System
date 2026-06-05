"""End-to-end expertise harvesting pipeline (UC-8 and UC-12).

This service orchestrates the full data flow specified in
instructions.md §3.1:

    ORCID -> OpenAlex -> SciBERT -> LLM normalization -> PostgreSQL

It is invoked from three places:

1. ``routes_auth.login`` — UC-3 first-login automatic sync.
2. ``routes_sync.trigger_sync`` — UC-12 manual sync.
3. ``app.services.scheduler`` — UC-12 alt flow quarterly auto-sync.

All blocking model inference is dispatched through the per-service async
helpers (``embed_texts``, ``extract_keywords``, ``normalize_keywords``).
Failures bubble up as :class:`ExternalServiceError` (HTTP 503) or are
captured in the ``sync_jobs`` row when the harvest can be partially
completed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ExternalServiceError, NotFoundError
from app.db.models import (
    ExpertiseTag,
    OrcidProfile,
    Publication,
    PublicationAbstract,
    SyncJob,
    SyncJobStatus,
    SyncTrigger,
    User,
    UserExpertiseTag,
)
from app.services.embeddings import embed_text, embed_texts
from app.services.external_apis import OpenAlexClient, OrcidClient
from app.services.llm_normalize import NormalizedTag, normalize_keywords
from app.services.nlp_pipeline import extract_keywords

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class HarvestService:
    """Coordinates external data ingestion and tag generation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._orcid = OrcidClient()
        self._openalex = OpenAlexClient()

    # ------------------------------------------------------------------ UC-12
    async def run_for_user(
        self, user_id: UUID, *, trigger: SyncTrigger
    ) -> SyncJob:
        """Run the full UC-8 pipeline for a single user and return the job row."""
        user = await self._load_user(user_id)
        if user.orcid_profile is None:
            raise NotFoundError(
                "This user does not have an ORCID identifier configured.",
                details={"user_id": str(user_id)},
            )

        job = SyncJob(
            user_id=user.id,
            trigger=trigger,
            status=SyncJobStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        self._session.add(job)
        await self._session.flush()

        try:
            publications_added, tags_added, no_new_data = await self._harvest(
                user, user.orcid_profile
            )
            job.publications_added = publications_added
            job.tags_added = tags_added
            job.status = (
                SyncJobStatus.NO_NEW_DATA if no_new_data else SyncJobStatus.SUCCEEDED
            )
        except ExternalServiceError as exc:
            job.status = SyncJobStatus.FAILED
            job.error_message = exc.message
            job.finished_at = datetime.now(timezone.utc)
            await self._session.commit()
            raise
        except Exception as exc:  # noqa: BLE001
            job.status = SyncJobStatus.FAILED
            job.error_message = str(exc)
            logger.exception("Harvest pipeline failed for user %s", user.id)
            job.finished_at = datetime.now(timezone.utc)
            await self._session.commit()
            raise

        job.finished_at = datetime.now(timezone.utc)
        user.orcid_profile.last_sync_at = job.finished_at
        await self._session.commit()
        await self._session.refresh(job)
        return job

    # ------------------------------------------------------------------ Helpers
    async def _load_user(self, user_id: UUID) -> User:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.orcid_profile),
                selectinload(User.publications).selectinload(Publication.abstract),
                selectinload(User.expertise_links).selectinload(
                    UserExpertiseTag.tag
                ),
            )
        )
        user = (await self._session.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise NotFoundError("User not found.")
        return user

    async def _harvest(
        self, user: User, orcid: OrcidProfile
    ) -> Tuple[int, int, bool]:
        """Execute the UC-8 pipeline; returns (pub_added, tag_added, no_new)."""
        # Step 1: ORCID -> DOI list.
        dois = await self._orcid.fetch_doi_list(orcid.orcid_id)
        if not dois:
            return 0, 0, True

        existing_dois = {p.doi for p in user.publications}
        new_dois = [d for d in dois if d not in existing_dois]
        if not new_dois:
            return 0, 0, True

        # Step 2/3: OpenAlex -> publication metadata + abstract.
        abstract_corpus: List[str] = []
        publications_added = 0

        for doi in new_dois:
            try:
                payload = await self._openalex.fetch_work_by_doi(doi)
            except ExternalServiceError as exc:
                # Missing record at OpenAlex is non-fatal for UC-9 fallback —
                # store an empty publication row flagged as missing-abstract.
                logger.warning("OpenAlex lookup failed for %s: %s", doi, exc.message)
                payload = {}

            title = payload.get("title")
            year = payload.get("publication_year")
            openalex_id = (payload.get("id") or "").split("/")[-1] or None
            venue = (
                (payload.get("host_venue") or {}).get("display_name")
                or (payload.get("primary_location") or {}).get("source", {}).get(
                    "display_name"
                )
            )
            abstract_text = self._openalex.reconstruct_abstract(
                payload.get("abstract_inverted_index")
            )

            publication = Publication(
                user_id=user.id,
                doi=doi,
                title=title,
                venue=venue,
                publication_year=year,
                openalex_id=openalex_id,
                abstract_missing=not bool(abstract_text),
            )
            self._session.add(publication)
            await self._session.flush()
            publications_added += 1

            if abstract_text:
                self._session.add(
                    PublicationAbstract(
                        publication_id=publication.id,
                        abstract_text=abstract_text,
                        source="openalex",
                    )
                )
                abstract_corpus.append(abstract_text)
                # Persist a publication-level embedding for downstream UC-14
                # spreading-activation lookups.
                publication.embedding = await embed_text(abstract_text)

        await self._session.flush()

        if not abstract_corpus:
            # UC-8 exception: nothing to extract from yet — UC-9 will handle it.
            return publications_added, 0, False

        # Steps 4–7: SciBERT keywords -> LLM normalization -> persist tags.
        candidate_phrases = await self._extract_candidate_phrases(abstract_corpus)
        if not candidate_phrases:
            return publications_added, 0, False

        # Pass the combined abstracts as context so the LLM can
        # disambiguate generic candidate words (e.g. "product",
        # "feature") against the actual research topic.
        combined_context = "\n\n".join(abstract_corpus[:5])
        normalized = await normalize_keywords(
            candidate_phrases, abstract=combined_context
        )
        tags_added = await self._persist_tags(user, normalized)
        return publications_added, tags_added, False

    async def _extract_candidate_phrases(self, abstracts: List[str]) -> List[str]:
        """Run SciBERT on every abstract and merge the keyword sets."""
        merged: Dict[str, float] = {}
        for abstract in abstracts:
            try:
                keywords = await extract_keywords(abstract, top_k=15)
            except Exception:  # noqa: BLE001 — skip the abstract, keep going.
                logger.exception("SciBERT extraction failed on one abstract")
                continue
            for phrase, score in keywords:
                merged[phrase] = max(merged.get(phrase, 0.0), score)
        # Sort by score and cap to keep the LLM prompt compact.
        ordered = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
        return [phrase for phrase, _ in ordered[:60]]

    async def _persist_tags(
        self, user: User, tags: Iterable[NormalizedTag]
    ) -> int:
        """Upsert canonical tags and attach them to the user."""
        labels = [t.canonical_label.strip() for t in tags if t.canonical_label.strip()]
        if not labels:
            return 0

        existing_stmt = select(ExpertiseTag).where(
            ExpertiseTag.canonical_label.in_(labels)
        )
        existing_rows = (await self._session.execute(existing_stmt)).scalars().all()
        existing_map: Dict[str, ExpertiseTag] = {
            row.canonical_label: row for row in existing_rows
        }

        # Create missing canonical tags and assign embeddings in one batch.
        to_embed: List[str] = []
        new_tags_by_label: Dict[str, ExpertiseTag] = {}
        for tag_payload in tags:
            label = tag_payload.canonical_label.strip()
            if not label or label in existing_map or label in new_tags_by_label:
                continue
            tag = ExpertiseTag(canonical_label=label, domain=tag_payload.domain)
            self._session.add(tag)
            new_tags_by_label[label] = tag
            to_embed.append(label)

        if to_embed:
            vectors = await embed_texts(to_embed)
            for label, vector in zip(to_embed, vectors):
                new_tags_by_label[label].embedding = vector
        await self._session.flush()

        # Attach to user (avoid duplicate links).
        link_stmt = select(UserExpertiseTag).where(
            UserExpertiseTag.user_id == user.id
        )
        existing_links = {
            link.tag_id for link in (await self._session.execute(link_stmt)).scalars()
        }

        added = 0
        for tag_payload in tags:
            label = tag_payload.canonical_label.strip()
            tag = existing_map.get(label) or new_tags_by_label.get(label)
            if tag is None or tag.id in existing_links:
                continue
            self._session.add(
                UserExpertiseTag(
                    user_id=user.id,
                    tag_id=tag.id,
                    confidence=float(tag_payload.confidence or 0.0),
                    source="ai",
                    validated=False,
                )
            )
            existing_links.add(tag.id)
            added += 1
        await self._session.flush()
        return added

    # ------------------------------------------------------------------ UC-9
    async def regenerate_tags_from_abstract(
        self, user_id: UUID, abstract_text: str
    ) -> int:
        """Reprocess a single supplemented abstract through the pipeline (UC-9)."""
        user = await self._load_user(user_id)
        keywords = await extract_keywords(abstract_text, top_k=15)
        if not keywords:
            return 0
        normalized = await normalize_keywords(
            [k for k, _ in keywords], abstract=abstract_text
        )
        return await self._persist_tags(user, normalized)


# ---------------------------------------------------------------------------
# Quarterly auto-sync helper (UC-12 alt flow)
# ---------------------------------------------------------------------------


async def list_users_for_quarterly_sync(session: AsyncSession) -> List[User]:
    """Return every Active user that owns an ORCID profile."""
    stmt = (
        select(User)
        .join(OrcidProfile, OrcidProfile.user_id == User.id)
        .options(selectinload(User.orcid_profile))
    )
    return list((await session.execute(stmt)).scalars().all())
