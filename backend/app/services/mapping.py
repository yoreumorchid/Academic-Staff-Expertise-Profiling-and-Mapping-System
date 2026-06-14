"""Semantic course / grant mapping service (UC-13 and UC-14).

Pipeline (instructions.md §3.2):

1. Vectorize the incoming specification text (UC-13).
2. Compute cosine similarity against every staff expertise centroid
   stored in PostgreSQL (UC-14 step 3).
3. Run a Spreading Activation pass across the tag co-occurrence graph
   to surface latent experts whose vocabulary differs but whose
   foundational competencies match (UC-14 step 4).
4. Aggregate the two signals into a single comprehensive score and
   persist the ranked report (UC-14 steps 5–7).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Sequence, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationFailure
from app.db.models import (
    CourseGrantSpec,
    ExpertiseTag,
    MappingReport,
    MappingReportEntry,
    SpecificationType,
    User,
    UserExpertiseTag,
)
from app.services.embeddings import cosine_similarity, embed_text
from app.services.llm import get_chat_llm

logger = logging.getLogger(__name__)

_EXPLANATION_PROMPT = """You are a faculty expertise analyst. Below is a course or research grant specification, followed by the top 3 matching academic staff with their expertise tags and semantic similarity scores.

Specification:
{spec_title}
{spec_text}

Top-3 Matched Staff:
{staff_summary}

Write a concise paragraph (150-250 words) interpreting these results. Explain which expertise areas drove the high scores, what makes these staff suitable, and any notable patterns (e.g. all top matches share a common subfield, or the scores drop significantly after rank 2). Use natural academic language suitable for a faculty dean or HoD reading this. Do NOT repeat the raw scores verbatim — synthesize insights.

Response format: plain English paragraph only, no markdown, no bullet points."""


COSINE_WEIGHT = 0.7
SPREADING_WEIGHT = 0.3
MIN_SCORE_THRESHOLD = 0.05
SPREADING_DECAY = 0.5


class MappingService:
    """Implements UC-13 ingestion and UC-14 ranked matching."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ UC-13
    async def ingest_specification(
        self,
        *,
        created_by: UUID,
        spec_type: SpecificationType,
        title: str,
        raw_text: str,
        source_filename: str | None = None,
    ) -> CourseGrantSpec:
        if len(raw_text.strip()) < 80:
            raise ValidationFailure(
                "Provide a more detailed specification (minimum 80 characters)."
            )
        embedding = await embed_text(raw_text)
        spec = CourseGrantSpec(
            created_by=created_by,
            spec_type=spec_type,
            title=title.strip(),
            raw_text=raw_text.strip(),
            source_filename=source_filename,
            embedding=embedding,
        )
        self._session.add(spec)
        await self._session.commit()
        await self._session.refresh(spec)
        return spec

    # ------------------------------------------------------------------ UC-14
    async def generate_report(
        self, *, spec_id: UUID, generated_by: UUID, top_n: int = 25
    ) -> MappingReport:
        spec = await self._load_spec(spec_id)
        if not spec.embedding:
            spec.embedding = await embed_text(spec.raw_text)
            await self._session.flush()

        # Pull every (user, tag, confidence) triple plus the tag embedding.
        triples = await self._load_user_tag_triples()
        if not triples:
            raise ValidationFailure(
                "No processed expertise profiles exist. Run a sync first.",
            )

        cosine_scores = self._cosine_against_users(spec.embedding, triples)
        spreading_scores = self._spreading_activation(spec.embedding, triples)

        combined: Dict[UUID, float] = {}
        for user_id in set(cosine_scores) | set(spreading_scores):
            combined[user_id] = (
                COSINE_WEIGHT * cosine_scores.get(user_id, 0.0)
                + SPREADING_WEIGHT * spreading_scores.get(user_id, 0.0)
            )

        ranked = sorted(
            (
                (uid, score)
                for uid, score in combined.items()
                if score >= MIN_SCORE_THRESHOLD
            ),
            key=lambda item: item[1],
            reverse=True,
        )[:top_n]

        report = MappingReport(spec_id=spec.id, generated_by=generated_by)
        self._session.add(report)
        await self._session.flush()

        for rank, (user_id, score) in enumerate(ranked, start=1):
            self._session.add(
                MappingReportEntry(
                    report_id=report.id,
                    user_id=user_id,
                    rank=rank,
                    cosine_score=cosine_scores.get(user_id, 0.0),
                    spreading_score=spreading_scores.get(user_id, 0.0),
                    combined_score=score,
                )
            )

        await self._session.commit()
        await self._session.refresh(report)

        # Generate AI explanation for the top-3 matches.
        try:
            report = await self._generate_explanation(report, ranked[:3], spec)
            await self._session.commit()
            await self._session.refresh(report)
        except Exception:
            logger.warning("LLM explanation generation failed, continuing without summary.")

        return await self._load_report(report.id)

    async def _generate_explanation(
        self,
        report: MappingReport,
        top3: List[Tuple[UUID, float]],
        spec: CourseGrantSpec,
    ) -> MappingReport:
        """Generate an LLM-powered explanation for the top-3 matches."""
        try:
            llm = get_chat_llm()
        except Exception:
            logger.warning("LLM not configured, skipping explanation.")
            return report

        staff_summary = await self._build_top3_staff_summary(top3)
        prompt = _EXPLANATION_PROMPT.format(
            spec_title=spec.title,
            spec_text=spec.raw_text[:2000],
            staff_summary=staff_summary,
        )
        try:
            response = await llm.ainvoke(prompt)
            report.summary = response.content.strip()
        except Exception as exc:
            logger.warning("LLM explanation call failed: %s", exc)
        return report

    async def _build_top3_staff_summary(
        self, top3: List[Tuple[UUID, float]]
    ) -> str:
        """Build a text summary of the top-3 staff for the LLM prompt."""
        user_ids = [uid for uid, _ in top3]
        stmt = select(User).where(User.id.in_(user_ids))
        users = (await self._session.execute(stmt)).scalars().all()
        user_map: Dict[UUID, User] = {u.id: u for u in users}

        # Load expertise tags for these users.
        tag_stmt = (
            select(UserExpertiseTag)
            .where(UserExpertiseTag.user_id.in_(user_ids))
            .options(selectinload(UserExpertiseTag.tag))
        )
        tag_links = (await self._session.execute(tag_stmt)).scalars().all()
        user_tags: Dict[UUID, List[str]] = defaultdict(list)
        for link in tag_links:
            user_tags[link.user_id].append(link.tag.canonical_label)

        lines: List[str] = []
        for rank, (uid, score) in enumerate(top3, start=1):
            user = user_map.get(uid)
            name = user.full_name if user else str(uid)
            dept = user.department if user and user.department else "N/A"
            tags = user_tags.get(uid, [])[:5]
            tag_str = ", ".join(tags) if tags else "no tags"
            lines.append(
                f"Rank {rank}: {name} | Department: {dept} | "
                f"Combined Score: {score:.4f} | Tags: {tag_str}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------ Loaders
    async def _load_spec(self, spec_id: UUID) -> CourseGrantSpec:
        spec = await self._session.get(CourseGrantSpec, spec_id)
        if spec is None:
            raise NotFoundError("Specification not found.")
        return spec

    async def _load_report(self, report_id: UUID) -> MappingReport:
        stmt = (
            select(MappingReport)
            .where(MappingReport.id == report_id)
            .options(
                selectinload(MappingReport.entries),
                selectinload(MappingReport.spec),
            )
        )
        report = (await self._session.execute(stmt)).scalar_one_or_none()
        if report is None:
            raise NotFoundError("Report not found.")
        return report

    async def _load_user_tag_triples(
        self,
    ) -> List[Tuple[UUID, ExpertiseTag, float]]:
        stmt = select(UserExpertiseTag).options(selectinload(UserExpertiseTag.tag))
        rows = (await self._session.execute(stmt)).scalars().all()
        result: List[Tuple[UUID, ExpertiseTag, float]] = []
        for link in rows:
            if link.tag.embedding:
                result.append((link.user_id, link.tag, float(link.confidence or 0.5)))
        return result

    # ------------------------------------------------------------------ Scoring
    @staticmethod
    def _cosine_against_users(
        spec_vector: Sequence[float],
        triples: List[Tuple[UUID, ExpertiseTag, float]],
    ) -> Dict[UUID, float]:
        """Best-of-tag cosine similarity per user, weighted by confidence."""
        scores: Dict[UUID, float] = defaultdict(float)
        for user_id, tag, confidence in triples:
            sim = cosine_similarity(spec_vector, tag.embedding or [])
            weighted = sim * (0.5 + 0.5 * confidence)
            if weighted > scores[user_id]:
                scores[user_id] = weighted
        return dict(scores)

    @staticmethod
    def _spreading_activation(
        spec_vector: Sequence[float],
        triples: List[Tuple[UUID, ExpertiseTag, float]],
    ) -> Dict[UUID, float]:
        """One-hop spreading activation across the tag co-occurrence graph.

        Step A — score every tag by direct cosine similarity to the spec.
        Step B — for each user, aggregate the activation that "spreads"
                 from their owned tags to neighbouring tags that share
                 co-authorship through other users. Latent experts are
                 those whose own tags are weakly similar but whose
                 neighbourhood lights up.
        """
        # Tag-level direct activation.
        tag_activation: Dict[UUID, float] = {}
        tag_index: Dict[UUID, ExpertiseTag] = {}
        for _, tag, _ in triples:
            if tag.id in tag_activation:
                continue
            tag_index[tag.id] = tag
            tag_activation[tag.id] = max(
                0.0, cosine_similarity(spec_vector, tag.embedding or [])
            )

        # Build user -> tags map and tag -> users map for one-hop spread.
        user_tags: Dict[UUID, List[UUID]] = defaultdict(list)
        tag_users: Dict[UUID, List[UUID]] = defaultdict(list)
        for user_id, tag, _ in triples:
            user_tags[user_id].append(tag.id)
            tag_users[tag.id].append(user_id)

        # Each user's spreading score: average of (decay * neighbour
        # activation) over every tag held by a co-tagged peer.
        scores: Dict[UUID, float] = defaultdict(float)
        for user_id, owned in user_tags.items():
            neighbour_activations: List[float] = []
            visited_tags: set[UUID] = set(owned)
            for tag_id in owned:
                for peer_id in tag_users.get(tag_id, []):
                    if peer_id == user_id:
                        continue
                    for peer_tag_id in user_tags.get(peer_id, []):
                        if peer_tag_id in visited_tags:
                            continue
                        visited_tags.add(peer_tag_id)
                        neighbour_activations.append(
                            SPREADING_DECAY * tag_activation.get(peer_tag_id, 0.0)
                        )
            if neighbour_activations:
                scores[user_id] = sum(neighbour_activations) / len(
                    neighbour_activations
                )
        return dict(scores)
