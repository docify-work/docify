"""Email sending behind one small interface (D23): SES in the cloud, SMTP (Mailpit) locally."""

from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

from docify.config import Settings, get_settings
from docify.observability.logging import get_logger

log = get_logger(__name__)


@dataclass
class Email:
    to: str
    subject: str
    text: str


class EmailSender(Protocol):
    async def send(self, email: Email) -> None: ...


class SmtpSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _send_sync(self, email: Email) -> None:
        msg = EmailMessage()
        msg["From"] = self.settings.email_from
        msg["To"] = email.to
        msg["Subject"] = email.subject
        msg.set_content(email.text)
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as smtp:
            smtp.send_message(msg)

    async def send(self, email: Email) -> None:
        await asyncio.to_thread(self._send_sync, email)


class SesSender:
    def __init__(self, settings: Settings) -> None:
        import boto3

        self.settings = settings
        self.client = boto3.client("sesv2", region_name=settings.aws_region)

    def _send_sync(self, email: Email) -> None:
        self.client.send_email(
            FromEmailAddress=self.settings.email_from,
            Destination={"ToAddresses": [email.to]},
            Content={"Simple": {
                "Subject": {"Data": email.subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": email.text, "Charset": "UTF-8"}},
            }},
        )

    async def send(self, email: Email) -> None:
        await asyncio.to_thread(self._send_sync, email)


@dataclass
class MemorySender:
    """Used by tests: collects emails instead of sending them."""

    outbox: list[Email] = field(default_factory=list)

    async def send(self, email: Email) -> None:
        self.outbox.append(email)


class ConsoleSender:
    async def send(self, email: Email) -> None:
        log.info("email.console", to=email.to, subject=email.subject)


_sender: EmailSender | None = None


def get_email_sender() -> EmailSender:
    global _sender
    if _sender is None:
        s = get_settings()
        sender: EmailSender
        if s.email_backend == "smtp":
            sender = SmtpSender(s)
        elif s.email_backend == "ses":
            sender = SesSender(s)
        else:
            sender = ConsoleSender()
        _sender = sender
    return _sender


def set_email_sender(sender: EmailSender | None) -> None:
    global _sender
    _sender = sender


async def send_safely(email: Email) -> None:
    """Email failures must not break the user flow (they can press "resend")."""
    try:
        await get_email_sender().send(email)
    except Exception as exc:
        log.warning("email.send_failed", subject=email.subject, error=type(exc).__name__)


_background: set[asyncio.Task[None]] = set()


def send_in_background(email: Email) -> None:
    """Fire-and-forget, so response time doesn't reveal whether an email was sent (no enumeration by timing)."""
    if isinstance(_sender, MemorySender):  # tests: collect immediately
        _sender.outbox.append(email)
        return
    task = asyncio.create_task(send_safely(email))
    _background.add(task)
    task.add_done_callback(_background.discard)
