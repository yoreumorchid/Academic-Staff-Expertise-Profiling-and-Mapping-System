"""Focused PEER-01 evidence, ordering, and representative-file regressions."""
from __future__ import annotations

import asyncio
import io
from types import SimpleNamespace
from uuid import uuid4

import pytest
from docx import Document
from pypdf import PdfWriter
from reportlab.pdfgen import canvas

from app.core.exceptions import ValidationFailure
from app.api.routes_benchmarking import _to_run_out
from app.db.models import BenchmarkType
from app.services.benchmarking import BenchmarkEvidence, BenchmarkingService
from app.services.document_extract import extract_text_from_upload
from app.services.document_representation import DocumentChunk
from app.services.internal_expertise import StaffExpertiseProfile


def _profile(name: str, vector: tuple[float, float]) -> StaffExpertiseProfile:
    return StaffExpertiseProfile(
        user_id=uuid4(),
        user_label=name,
        vector=vector,
        tag_weights=((name, 1.0),),
    )


def test_peer_evidence_keeps_all_chunks_and_exposes_staff_cluster_and_source() -> None:
    profiles = [_profile("Niche Specialist", (1.0, 0.0)), _profile("Other Staff", (0.0, 1.0))]
    chunks = [
        DocumentChunk("synthetic.pdf", f"Section {index}", f"Exact source {index}", 3)
        for index in range(30)
    ]
    vectors = [[1.0, 0.0] for _ in range(29)] + [[-1.0, 0.0]]

    results = BenchmarkingService._compute_peer_evidence(
        profiles,
        [[2 ** -0.5, 2 ** -0.5]],
        ["Broad institutional cluster"],
        vectors,
        chunks,
    )

    assert len(results) == 30
    assert results[0].source_excerpt == "Exact source 29"
    assert results[0].coverage_classification == "candidate_gap"
    assert results[-1].coverage_classification == "covered"
    assert results[-1].nearest_staff_name == "Niche Specialist"
    assert results[-1].nearest_cluster_label == "Broad institutional cluster"
    assert results[-1].nearest_cluster_distance == pytest.approx(1 - 2 ** -0.5)
    assert all(item.review_status == "pending_administrator_review" for item in results)


def test_peer_coverage_boundaries_are_inclusive_and_three_way() -> None:
    assert BenchmarkingService._coverage_classification(0.40) == "covered"
    assert BenchmarkingService._coverage_classification(0.41) == "partially_covered"
    assert BenchmarkingService._coverage_classification(0.68) == "partially_covered"
    assert BenchmarkingService._coverage_classification(0.69) == "candidate_gap"


def test_peer_api_contract_exposes_reviewable_evidence() -> None:
    staff_id = uuid4()
    evidence = SimpleNamespace(
        domain_label="synthetic.pdf — Year 4",
        displacement_score=0.71,
        recommendation="Administrator review required.",
        peer_filename="synthetic.pdf",
        detected_section="Year 4",
        source_excerpt="Quantum algorithms and error correction.",
        nearest_staff_id=staff_id,
        nearest_staff_name="Nearest Staff",
        nearest_cluster_label="Algorithms / Security",
        nearest_cluster_distance=0.74,
        coverage_classification="candidate_gap",
        review_status="pending_administrator_review",
    )
    run = SimpleNamespace(
        id=uuid4(),
        benchmark_type=BenchmarkType.PEER,
        narrative=None,
        source_payload={},
        visualization_payload={"points": []},
        white_spaces=[evidence],
    )

    response = _to_run_out(run)

    assert response.white_spaces[0].peer_filename == "synthetic.pdf"
    assert response.white_spaces[0].nearest_staff_id == staff_id
    assert response.white_spaces[0].coverage_classification == "candidate_gap"
    assert response.white_spaces[0].review_status == "pending_administrator_review"


def test_peer_narrative_prompt_cannot_claim_a_proven_gap() -> None:
    prompt = BenchmarkingService._narrative_prompt(
        [BenchmarkEvidence("Synthetic segment", 0.7)],
        scope="peer institutional curricula",
        require_administrator_review=True,
    )

    assert "Do not describe any item as a proven institutional gap" in prompt
    assert "requires administrator review" in prompt


def test_generated_text_pdf_is_readable() -> None:
    buffer = io.BytesIO()
    document = canvas.Canvas(buffer)
    document.drawString(72, 760, "Year 1 Core Curriculum")
    document.drawString(72, 740, "Students study algorithms, databases, and secure software design.")
    document.save()

    text = asyncio.run(extract_text_from_upload("synthetic-programme.pdf", buffer.getvalue(), "application/pdf"))

    assert "Year 1 Core Curriculum" in text
    assert "secure software design" in text


def test_generated_docx_table_is_preserved_as_text() -> None:
    document = Document()
    document.add_heading("Programme Structure", level=1)
    table = document.add_table(rows=2, cols=3)
    table.rows[0].cells[0].text = "Year"
    table.rows[0].cells[1].text = "Code"
    table.rows[0].cells[2].text = "Course"
    table.rows[1].cells[0].text = "2"
    table.rows[1].cells[1].text = "SYN204"
    table.rows[1].cells[2].text = "Distributed Systems and Security"
    buffer = io.BytesIO()
    document.save(buffer)

    text = asyncio.run(extract_text_from_upload(
        "synthetic-table.docx",
        buffer.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ))

    assert "Year | Code | Course" in text
    assert "2 | SYN204 | Distributed Systems and Security" in text


def test_generated_extraction_poor_pdf_is_rejected_with_ocr_guidance() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)

    with pytest.raises(ValidationFailure, match="scanned or image-only PDFs require OCR"):
        asyncio.run(extract_text_from_upload("synthetic-scan.pdf", buffer.getvalue(), "application/pdf"))
