"""Critical UC-16 behavior: long peer documents are fully represented."""
from app.services.document_representation import SourceSection, chunk_sections


def test_long_peer_document_is_split_without_losing_its_end() -> None:
    text = " ".join(f"topic-{index}" for index in range(500))

    chunks = chunk_sections(
        [SourceSection("id", "peer-curriculum.pdf", "Topics", text, True)],
        count_tokens=lambda value: len(value.split()),
        max_tokens=30,
        overlap_tokens=5,
    )

    assert len(chunks) > 1
    assert "topic-0" in chunks[0].excerpt
    assert "topic-499" in chunks[-1].excerpt
    assert all(chunk.token_count <= 30 for chunk in chunks)
