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
# Helpers
# ---------------------------------------------------------------------------

def _normalize_doi(doi: str) -> str:
    """Return a lowercase bare DOI, stripping any URL prefix.

    OpenAlex returns full URLs (``https://doi.org/10.xxx``); ORCID returns
    bare strings (``10.xxx``). Normalising both sides prevents duplicate
    publication rows caused purely by formatting differences.
    """
    return (
        doi.strip()
        .lower()
        .removeprefix("https://doi.org/")
        .removeprefix("http://doi.org/")
        .removeprefix("doi:")
    )


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

        # Guard against concurrent syncs for the same user.  A RUNNING job
        # from a background first-login task can overlap with a manual trigger
        # arriving seconds later, causing duplicate-publication IntegrityErrors.
        running_stmt = (
            select(SyncJob)
            .where(SyncJob.user_id == user_id)
            .where(SyncJob.status == SyncJobStatus.RUNNING)
        )
        if (await self._session.execute(running_stmt)).scalar_one_or_none():
            raise ExternalServiceError(
                "A sync is already running for this user. Please wait for it to complete."
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
        # Step 1: Resolve OpenAlex author ID from ORCID (cached after first sync).
        if not orcid.openalex_author_id:
            author_id = await self._openalex.fetch_author_by_orcid(orcid.orcid_id)
            if author_id:
                orcid.openalex_author_id = author_id
                await self._session.flush()
        else:
            author_id = orcid.openalex_author_id

        # Step 2: Fetch publication payloads.
        # Primary path: OpenAlex author works (comprehensive — picks up papers
        # the author didn't register on ORCID themselves).
        # Fallback: ORCID DOI list → individual OpenAlex DOI lookups.
        payloads: Dict[str, Any]
        if author_id:
            works = await self._openalex.fetch_works_by_author(author_id)
            payloads = {}
            for w in works:
                raw_doi = (w.get("doi") or "").strip()
                if not raw_doi:
                    continue
                # OpenAlex returns full URLs like "https://doi.org/10.xxx".
                doi_key = _normalize_doi(raw_doi)
                payloads[doi_key] = w
        else:
            # ORCID fallback: fetch DOIs then look up each one individually.
            dois = await self._orcid.fetch_doi_list(orcid.orcid_id)
            payloads = {}
            for doi in dois:
                doi_key = _normalize_doi(doi)
                try:
                    payloads[doi_key] = await self._openalex.fetch_work_by_doi(doi)
                except ExternalServiceError as exc:
                    logger.warning(
                        "OpenAlex lookup failed for %s: %s", doi, exc.message
                    )
                    payloads[doi_key] = {}

        if not payloads:
            return 0, 0, True

        existing_dois = {_normalize_doi(p.doi) for p in user.publications}
        new_items = {
            doi: payload
            for doi, payload in payloads.items()
            if doi not in existing_dois
        }
        if not new_items:
            # If the user already has tags, nothing more to do.
            if user.expertise_links:
                return 0, 0, True
            # No new publications BUT no tags either — the NLP phase must have
            # crashed on a previous sync (partial-success recovery).  Fall
            # through and re-run NLP on the already-persisted abstract corpus.
            abstract_corpus = [
                p.abstract.abstract_text
                for p in user.publications
                if p.abstract is not None and p.abstract.abstract_text
            ]
            if not abstract_corpus:
                return 0, 0, True
            # Jump straight to NLP — skip publication persistence loop.
            candidate_phrases = await self._extract_candidate_phrases(abstract_corpus)
            if not candidate_phrases:
                return 0, 0, True
            combined_context = "\n\n".join(abstract_corpus[:5])
            normalized = await normalize_keywords(candidate_phrases, abstract=combined_context)
            tags_added = await self._persist_tags(user, normalized)
            return 0, tags_added, False

        # Step 3: Persist publications + abstracts.
        abstract_corpus: List[str] = []
        publications_added = 0

        for doi_key, payload in new_items.items():
            title = payload.get("title")
            year = payload.get("publication_year")
            openalex_id = (payload.get("id") or "").split("/")[-1] or None
            primary_location = payload.get("primary_location") or {}
            host_venue = payload.get("host_venue") or {}
            primary_source = primary_location.get("source") or {}
            venue = (
                host_venue.get("display_name")
                or primary_source.get("display_name")
            )
            abstract_text = self._openalex.reconstruct_abstract(
                payload.get("abstract_inverted_index")
            )

            publication = Publication(
                user_id=user.id,
                doi=doi_key,
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
                publication.embedding = await embed_text(abstract_text)

        await self._session.flush()

        if not abstract_corpus:
            return publications_added, 0, False

        # Steps 4–7: SciBERT keywords -> LLM normalization -> persist tags.
        # No artificial cap: SciBERT iterates abstract-by-abstract (≈50ms each
        # on CPU) and individual failures are swallowed.  For a 100-paper
        # researcher this takes ~5s before LLM dispatch.
        candidate_phrases = await self._extract_candidate_phrases(abstract_corpus)
        if not candidate_phrases:
            return publications_added, 0, False

        # Batch LLM normalization to avoid blowing up the prompt or hitting
        # provider response limits when the candidate set is large.
        normalized = await self._normalize_in_batches(
            candidate_phrases, abstract_corpus
        )
        tags_added = await self._persist_tags(user, normalized)
        return publications_added, tags_added, False

    async def _normalize_in_batches(
        self,
        phrases: List[str],
        abstracts: List[str],
        batch_size: int = 50,
    ) -> List[NormalizedTag]:
        """Call the LLM in batches and concatenate the resulting tags.

        For prolific researchers (50+ abstracts → 200+ candidate phrases) a
        single LLM call risks truncation, timeouts, or unparseable JSON.
        Batching keeps each call small while still giving the LLM enough
        abstract context to make accurate domain decisions.
        """
        from app.services.llm_normalize import NormalizedTag

        # Use a rotating window of abstracts as context: chunk N of the
        # phrase list gets abstracts[N*5 : N*5+10] for variety.
        all_tags: List[NormalizedTag] = []
        seen_labels: set[str] = set()
        for batch_idx in range(0, len(phrases), batch_size):
            chunk = phrases[batch_idx : batch_idx + batch_size]
            ctx_start = (batch_idx // batch_size) * 5
            ctx = "\n\n".join(abstracts[ctx_start : ctx_start + 10]) or "\n\n".join(
                abstracts[:10]
            )
            try:
                batch_tags = await normalize_keywords(chunk, abstract=ctx)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "LLM normalization batch %d/%d failed; continuing",
                    batch_idx // batch_size + 1,
                    (len(phrases) + batch_size - 1) // batch_size,
                )
                continue
            for tag in batch_tags:
                key = tag.canonical_label.strip().lower()
                if key and key not in seen_labels:
                    seen_labels.add(key)
                    all_tags.append(tag)
        return all_tags

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
        # Sort by score; let downstream batching control LLM prompt size.
        # For 100-abstract corpora this is typically ~200–400 unique phrases.
        ordered = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
        return [phrase for phrase, _ in ordered[:300]]

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
            tag = ExpertiseTag(
                canonical_label=label,
                parent_label=(tag_payload.parent_label or "").strip() or None,
                domain=tag_payload.domain,
            )
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
