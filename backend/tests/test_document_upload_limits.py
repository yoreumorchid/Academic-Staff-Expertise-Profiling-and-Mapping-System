"""Focused DOCREP-01 request-level upload-limit regressions."""
import asyncio
from types import SimpleNamespace

import pytest

from app.api.routes_benchmarking import _extract_peer_uploads
from app.core.exceptions import ValidationFailure


def test_peer_upload_rejects_too_many_files_before_parsing(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes_benchmarking.get_settings",
        lambda: SimpleNamespace(
            peer_document_max_files=2,
            max_document_upload_bytes=10,
            peer_document_max_total_bytes=20,
        ),
    )

    with pytest.raises(ValidationFailure, match="at most 2"):
        asyncio.run(_extract_peer_uploads([object(), object(), object()]))


def test_peer_upload_rejects_combined_size_before_extraction(monkeypatch) -> None:
    extracted: list[str] = []

    async def fake_read(upload, max_bytes):
        return b"123456"

    async def fake_extract(filename, buffer, content_type):
        extracted.append(filename)
        return "meaningful extracted curriculum text"

    monkeypatch.setattr(
        "app.api.routes_benchmarking.get_settings",
        lambda: SimpleNamespace(
            peer_document_max_files=8,
            max_document_upload_bytes=10,
            peer_document_max_total_bytes=10,
        ),
    )
    monkeypatch.setattr("app.api.routes_benchmarking.read_upload_limited", fake_read)
    monkeypatch.setattr("app.api.routes_benchmarking.extract_text_from_upload", fake_extract)
    files = [
        SimpleNamespace(filename="one.pdf", content_type="application/pdf"),
        SimpleNamespace(filename="two.pdf", content_type="application/pdf"),
    ]

    with pytest.raises(ValidationFailure, match="combined peer upload"):
        asyncio.run(_extract_peer_uploads(files))

    assert extracted == ["one.pdf"]
