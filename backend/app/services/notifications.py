"""UC-5 — Notification email service.

Sends rendered transactional emails (registration outcome and password
reset) via asynchronous SMTP. Every dispatch is recorded in
``notification_log`` so that the UC-5 exception flow (delivery failure)
can drive a retry without losing the original intent.
"""
from __future__ import annotations

import logging
from typing import Optional

import aiosmtplib
from email.message import EmailMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import NotificationKind, NotificationLog, User

logger = logging.getLogger(__name__)


class NotificationService:
    """Thin wrapper around ``aiosmtplib`` with structured logging."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    async def send(
        self,
        *,
        recipient: User,
        kind: NotificationKind,
        subject: str,
        body: str,
    ) -> NotificationLog:
        record = NotificationLog(
            recipient_user_id=recipient.id,
            recipient_email=recipient.email,
            kind=kind,
            subject=subject,
        )
        self._session.add(record)
        await self._session.flush()

        message = EmailMessage()
        message["From"] = self._settings.smtp_from
        message["To"] = recipient.email
        message["Subject"] = subject
        message.set_content(body)

        try:
            await aiosmtplib.send(
                message,
                hostname=self._settings.smtp_host,
                port=self._settings.smtp_port,
                username=self._settings.smtp_username,
                password=self._settings.smtp_password,
                start_tls=self._settings.smtp_starttls,
            )
            record.delivered = True
        except Exception as exc:  # noqa: BLE001 — log and persist failure.
            record.delivered = False
            record.error_message = str(exc)
            logger.exception("SMTP delivery failed for %s", recipient.email)
        await self._session.flush()
        return record

    # --- Convenience helpers --------------------------------------------------

    async def notify_registration_outcome(self, user: User, *, approved: bool) -> None:
        kind = (
            NotificationKind.REGISTRATION_APPROVED
            if approved
            else NotificationKind.REGISTRATION_REJECTED
        )
        verdict = "Approved" if approved else "Rejected"
        subject = f"Expertise Insight Registration {verdict}"
        body = (
            f"Hello {user.full_name},\n\n"
            f"Your Expertise Insight account registration has been {verdict}.\n"
            + (
                "You may now sign in at "
                f"{self._settings.frontend_base_url}/login.\n"
                if approved
                else "If you believe this decision was made in error, please contact your Faculty Manager.\n"
            )
            + "\nRegards,\nExpertise Insight"
        )
        await self.send(recipient=user, kind=kind, subject=subject, body=body)

    async def notify_password_reset(self, user: User, token: str) -> None:
        link = f"{self._settings.frontend_base_url}/reset-password?token={token}"
        subject = "Reset Your Expertise Insight Password"
        body = (
            f"Hello {user.full_name},\n\n"
            f"A password reset was requested for your account. The following link "
            f"is valid for {self._settings.password_reset_ttl_minutes} minutes:\n\n"
            f"{link}\n\n"
            "If you did not request this reset, you may safely ignore this message.\n\n"
            "Regards,\nExpertise Insight"
        )
        await self.send(
            recipient=user,
            kind=NotificationKind.PASSWORD_RESET,
            subject=subject,
            body=body,
        )
