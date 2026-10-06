"""Focused regressions for SEC-01 authentication and upload controls."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import ValidationFailure
from app.core.security import hash_reset_token
from app.services import auth
from app.services.auth import AuthService
from app.services.document_extract import extract_text_from_upload
from app.services.upload_validation import decode_csv_upload, read_upload_limited


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


def _settings() -> SimpleNamespace:
    return SimpleNamespace(password_reset_ttl_minutes=30)


@pytest.mark.parametrize(
    ("record", "message"),
    [
        (None, "no longer valid"),
        (
            SimpleNamespace(
                consumed_at=None,
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                user_id=uuid4(),
            ),
            "expired",
        ),
    ],
)
def test_reset_token_rejects_invalid_and_expired_records(
    monkeypatch: pytest.MonkeyPatch,
    record: object | None,
    message: str,
) -> None:
    class FakeSession:
        async def execute(self, statement: object) -> _ScalarResult:
            return _ScalarResult(record)

    monkeypatch.setattr(auth, "get_settings", _settings)
    service = AuthService(FakeSession())  # type: ignore[arg-type]

    with pytest.raises(ValidationFailure, match=message):
        asyncio.run(service.consume_reset_token("invalid-token", "NewPassword1!"))


def test_new_reset_token_is_stored_only_as_a_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_token = "a-high-entropy-reset-token"
    user = SimpleNamespace(
        id=uuid4(), email="member@example.edu", full_name="Test Member"
    )

    class FakeSession:
        def __init__(self) -> None:
            self.execute_calls = 0
            self.added: list[object] = []

        async def execute(self, statement: object) -> _ScalarResult:
            self.execute_calls += 1
            return _ScalarResult(user if self.execute_calls == 1 else None)

        def add(self, value: object) -> None:
            self.added.append(value)

        async def commit(self) -> None:
            return None

    delivered_tokens: list[str] = []

    class FakeNotificationService:
        def __init__(self, session: object) -> None:
            pass

        async def notify_password_reset(self, recipient: object, token: str) -> None:
            delivered_tokens.append(token)

    monkeypatch.setattr(auth, "get_settings", _settings)
    monkeypatch.setattr(auth, "generate_reset_token", lambda: raw_token)
    monkeypatch.setattr(auth, "NotificationService", FakeNotificationService)

    session = FakeSession()
    asyncio.run(AuthService(session).request_password_reset(user.email))  # type: ignore[arg-type]

    stored = session.added[0]
    assert stored.token_hash == hash_reset_token(raw_token)
    assert stored.token_hash != raw_token
    assert delivered_tokens == [raw_token]


def test_oversized_upload_is_rejected_before_full_read() -> None:
    class FakeUpload:
        def __init__(self) -> None:
            self.requested_size = 0

        async def read(self, size: int) -> bytes:
            self.requested_size = size
            return b"x" * size

    upload = FakeUpload()
    with pytest.raises(ValidationFailure, match="size limit"):
        asyncio.run(read_upload_limited(upload, 10))  # type: ignore[arg-type]

    assert upload.requested_size == 11


def test_csv_rejects_binary_content_disguised_by_extension() -> None:
    with pytest.raises(ValidationFailure, match="does not appear to be CSV"):
        decode_csv_upload("records.csv", "text/csv", b"%PDF-1.7\n")


@pytest.mark.parametrize("filename", ["fake.pdf", "fake.docx"])
def test_document_rejects_content_that_does_not_match_extension(filename: str) -> None:
    with pytest.raises(ValidationFailure, match="does not match"):
        asyncio.run(extract_text_from_upload(filename, b"plain text in disguise"))
