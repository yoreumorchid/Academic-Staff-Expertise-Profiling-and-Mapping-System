"""Critical UC-16 behavior: long peer documents are fully represented."""
from app.services.benchmarking import chunk_peer_documents


def test_long_peer_document_is_split_without_losing_its_end() -> None:
    text = " ".join(f"topic-{index}" for index in range(500))

    chunks, labels = chunk_peer_documents(
        [("peer-curriculum.pdf", text)],
        max_chars=200,
    )

    assert len(chunks) > 1
    assert "topic-0" in chunks[0]
    assert "topic-499" in chunks[-1]
    assert len(chunks) == len(labels)
    assert all(len(chunk) <= 200 for chunk in chunks)
