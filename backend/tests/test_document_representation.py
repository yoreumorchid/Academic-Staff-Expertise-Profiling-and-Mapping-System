"""Focused DOCREP-01 regressions for deterministic cleaning and chunking."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4
import pytest

from app.core.exceptions import ValidationFailure
from app.db.models import SpecificationType
from app.services.document_representation import (
    DocumentChunk,
    build_chunks,
    chunk_sections,
    extract_sections,
    preview_documents,
)
from app.services.mapping import MappingService


def _word_tokens(text: str) -> int:
    return len(text.split())


def test_repeated_page_furniture_and_admin_noise_are_default_excluded() -> None:
    raw = """FACULTY HANDBOOK
Learning Outcomes
Students design secure distributed systems and evaluate their performance.
Page 1
\f
FACULTY HANDBOOK
Technical Topics
Cloud orchestration, threat modelling, observability, and resilient storage.
Page 2
\f
FACULTY HANDBOOK
Document Control
Version history approved by the faculty office.
Page 3"""

    sections = extract_sections("curriculum.pdf", raw)

    assert all("FACULTY HANDBOOK" not in section.excerpt for section in sections)
    assert any(section.section == "Learning Outcomes" and section.included_by_default for section in sections)
    assert any(section.section == "Document Control" and not section.included_by_default for section in sections)


def test_sentence_chunks_keep_overlap_boundary_topic_and_final_text() -> None:
    text = " ".join(
        f"Topic {index} develops applied computing capability."
        for index in range(18)
    ) + " Final capstone covers trustworthy autonomous systems."
    section = extract_sections("programme.docx", f"Learning Outcomes\n{text}")[0]

    chunks = chunk_sections(
        [section], count_tokens=_word_tokens, max_tokens=28, overlap_tokens=6
    )

    assert len(chunks) > 1
    assert all(chunk.token_count <= 28 for chunk in chunks)
    assert "Final capstone" in chunks[-1].excerpt
    assert set(chunks[0].excerpt.split()) & set(chunks[1].excerpt.split())
    assert all(chunk.filename == "programme.docx" for chunk in chunks)
    assert all(chunk.section == "Learning Outcomes" for chunk in chunks)


def test_unfamiliar_heading_free_layout_falls_back_to_paragraphs() -> None:
    raw = (
        "Students investigate data-intensive systems and distributed algorithms.\n\n"
        "Practical work covers secure deployment, monitoring, and incident response."
    )

    sections = extract_sections("unstructured.pdf", raw)

    assert [section.section for section in sections] == ["Paragraph 1", "Paragraph 2"]
    assert all(section.included_by_default for section in sections)


def test_mapping_chunks_are_embedded_in_one_batch(monkeypatch) -> None:
    calls: list[list[str]] = []

    async def fake_embed_texts(texts):
        materialized = list(texts)
        calls.append(materialized)
        return [[1.0, 0.0], [0.0, 1.0]]

    class Session:
        def add(self, value): self.value = value
        async def commit(self): pass
        async def refresh(self, value): pass

    monkeypatch.setattr("app.services.mapping.embed_texts", fake_embed_texts)
    chunks = [
        DocumentChunk("spec.pdf", "Objectives", "Design secure systems.", 4),
        DocumentChunk("spec.pdf", "Requirements", "Evaluate distributed platforms.", 4),
    ]
    session = Session()
    spec = asyncio.run(MappingService(session).ingest_specification(
        created_by=uuid4(), spec_type=SpecificationType.COURSE,
        title="Distributed Systems", raw_text="Detailed specification " * 8,
        source_filename="spec.pdf", document_chunks=chunks,
    ))

    assert calls == [[chunk.excerpt for chunk in chunks]]
    assert spec.embedding == pytest.approx([2 ** -0.5, 2 ** -0.5])
    assert spec.document_payload["chunks"][1]["section"] == "Requirements"


def test_preview_reports_exact_token_budget_and_build_rejects_over_limit(monkeypatch) -> None:
    class Tokenizer:
        @staticmethod
        def encode(text, **kwargs):
            return text.split()

    settings = SimpleNamespace(
        embedding_model="test-model",
        document_chunk_max_tokens=8,
        document_chunk_overlap_tokens=2,
    )
    monkeypatch.setattr(
        "app.services.document_representation.get_embedding_tokenizer",
        lambda: (Tokenizer(), 10, 12),
    )
    monkeypatch.setattr(
        "app.services.document_representation.get_settings", lambda: settings
    )
    text = "Objectives\nOne two three four five six seven eight nine ten eleven."

    preview = preview_documents(
        [("spec.pdf", text)], max_source_tokens=10, max_chunks=3
    )

    assert preview.sections[0].token_count == 11
    assert preview.warning_source_tokens == 8
    with pytest.raises(ValidationFailure, match="11 source tokens"):
        build_chunks(
            preview.sections, max_source_tokens=10, max_chunks=3
        )
