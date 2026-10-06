"""Shared bounded reads and lightweight validation for user uploads."""
from __future__ import annotations

from fastapi import UploadFile

from app.core.exceptions import ValidationFailure


async def read_upload_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Read at most one byte beyond the configured limit, then reject."""
    buffer = await upload.read(max_bytes + 1)
    if len(buffer) > max_bytes:
        limit_mb = max_bytes / (1024 * 1024)
        raise ValidationFailure(
            f"Uploaded file exceeds the {limit_mb:g} MB size limit."
        )
    return buffer


def decode_csv_upload(filename: str, content_type: str | None, buffer: bytes) -> str:
    """Validate a CSV extension/type and return safe UTF-8 text."""
    if not filename or not filename.lower().endswith(".csv"):
        raise ValidationFailure("Only CSV files are accepted.")

    allowed_types = {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "text/plain",
        "application/octet-stream",
    }
    normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_type and normalized_type not in allowed_types:
        raise ValidationFailure("The uploaded file type is not a supported CSV type.")
    if not buffer:
        raise ValidationFailure("The uploaded CSV file is empty.")
    if b"\x00" in buffer or buffer.startswith(
        (b"%PDF-", b"PK\x03\x04", b"\xd0\xcf\x11\xe0")
    ):
        raise ValidationFailure(
            "The uploaded file content does not appear to be CSV text."
        )

    try:
        return buffer.decode("utf-8-sig").strip()
    except UnicodeDecodeError:
        raise ValidationFailure(
            "The uploaded CSV file is not valid UTF-8. Please re-save it as CSV UTF-8."
        ) from None
