"""PDF / DOCX text extraction (UC-9 alt flow, UC-13 alt flow, UC-16).

Both ``pypdf`` and ``python-docx`` are pure-Python and synchronous; we
wrap them in ``asyncio.to_thread`` so large uploads don't block the
event loop. Unsupported or corrupt files raise :class:`ValidationFailure`
which the FastAPI handler converts to a 422 envelope.
"""
from __future__ import annotations

import asyncio
import io
import logging
from typing import Tuple

from app.core.exceptions import ValidationFailure

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


def _extract_pdf_sync(buffer: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(buffer))
    except Exception as exc:  # noqa: BLE001
        raise ValidationFailure(
            "Uploaded PDF is corrupt or unreadable."
        ) from exc

    chunks: list[str] = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 — skip the page but keep going.
            continue
    return "\n".join(chunk.strip() for chunk in chunks if chunk and chunk.strip())


def _extract_docx_sync(buffer: bytes) -> str:
    from docx import Document

    try:
        document = Document(io.BytesIO(buffer))
    except Exception as exc:  # noqa: BLE001
        raise ValidationFailure(
            "Uploaded Word document is corrupt or unreadable."
        ) from exc
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


async def extract_text_from_upload(filename: str, buffer: bytes) -> str:
    """Dispatch to the correct parser based on the filename extension."""
    if not filename:
        raise ValidationFailure("Uploaded file is missing a filename.")
    lower = filename.lower()
    ext = next((e for e in _SUPPORTED_EXTENSIONS if lower.endswith(e)), None)
    if ext is None:
        raise ValidationFailure(
            "Unsupported file format. Upload a PDF or Word (.docx) document."
        )
    if not buffer:
        raise ValidationFailure("Uploaded file is empty.")

    if ext == ".pdf":
        text = await asyncio.to_thread(_extract_pdf_sync, buffer)
    else:
        text = await asyncio.to_thread(_extract_docx_sync, buffer)

    if not text or len(text.strip()) < 40:
        raise ValidationFailure(
            "Could not extract meaningful text from the uploaded document."
        )
    return text


def detect_kind(filename: str) -> Tuple[str, str]:
    """Return ``(extension, mime_type)`` for the upload, validating support."""
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        return ".pdf", "application/pdf"
    if lower.endswith(".docx"):
        return (
            ".docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    raise ValidationFailure(
        "Unsupported file format. Upload a PDF or Word (.docx) document."
    )
