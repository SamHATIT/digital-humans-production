"""
EmailSender — minimal abstraction so we can ship the email-verification flow
today without committing to a specific transactional email provider.

Backends:
- ``console`` (default in dev): writes the message to the structured logs.
  The verify link shows up in ``journalctl -u digital-humans-backend``.
- ``smtp``: standard smtplib over STARTTLS. Configure via env vars; if any
  required var is missing the sender raises at startup so we fail fast.

Switch via the EMAIL_BACKEND env var.

GHOST-001 (backlog) will pick a real provider (Mailgun or Postmark) for both
Ghost and the platform — once that's chosen, swap the backend to ``smtp``
or add a provider-specific subclass here.
"""
from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EmailMessageSpec:
    """Plain-data view of an email — no transport details."""
    to_email: str
    to_name: Optional[str]
    subject: str
    body_text: str
    body_html: Optional[str] = None


class EmailSender:
    """Base interface — subclasses implement ``send``."""

    def send(self, msg: EmailMessageSpec) -> None:  # pragma: no cover - abstract
        raise NotImplementedError


class ConsoleSender(EmailSender):
    """Logs the message with full body so devs can copy-paste the verify link."""

    def send(self, msg: EmailMessageSpec) -> None:
        logger.info(
            "[EMAIL/console] to=%s subject=%r\n--- begin body ---\n%s\n--- end body ---",
            msg.to_email,
            msg.subject,
            msg.body_text,
        )


class SmtpSender(EmailSender):
    """Plain SMTP+STARTTLS sender. Production-ready when SMTP_* env vars are set."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        from_name: str,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.from_name = from_name

    def send(self, msg: EmailMessageSpec) -> None:
        em = EmailMessage()
        em["From"] = f"{self.from_name} <{self.from_email}>"
        em["To"] = f"{msg.to_name} <{msg.to_email}>" if msg.to_name else msg.to_email
        em["Subject"] = msg.subject
        em.set_content(msg.body_text)
        if msg.body_html:
            em.add_alternative(msg.body_html, subtype="html")

        with smtplib.SMTP(self.host, self.port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(self.username, self.password)
            smtp.send_message(em)
        logger.info("[EMAIL/smtp] sent to=%s subject=%r", msg.to_email, msg.subject)


def _build_sender_from_env() -> EmailSender:
    backend = os.getenv("EMAIL_BACKEND", "console").lower()
    if backend == "smtp":
        try:
            return SmtpSender(
                host=os.environ["SMTP_HOST"],
                port=int(os.environ.get("SMTP_PORT", "587")),
                username=os.environ["SMTP_USERNAME"],
                password=os.environ["SMTP_PASSWORD"],
                from_email=os.environ["SMTP_FROM_EMAIL"],
                from_name=os.environ.get("SMTP_FROM_NAME", "Digital Humans"),
            )
        except KeyError as exc:
            raise RuntimeError(
                f"EMAIL_BACKEND=smtp but missing env var {exc.args[0]}"
            ) from exc
    return ConsoleSender()


# Module-level singleton — built once at import time.
_sender: EmailSender = _build_sender_from_env()


def get_sender() -> EmailSender:
    return _sender


def send_signup_verification_email(
    *, to_email: str, to_name: str, verify_url: str, lang: str = "fr"
) -> None:
    """Compose and send the signup verification email."""
    if lang == "en":
        subject = "Confirm your email · Digital · Humans"
        body_text = (
            f"Hi {to_name},\n\n"
            f"Welcome to Digital · Humans. Please confirm your email by opening this link:\n\n"
            f"{verify_url}\n\n"
            f"The link is valid for 30 minutes. If you didn't request this, just ignore the email — "
            f"no account has been created.\n\n"
            f"— The studio"
        )
    else:
        subject = "Confirme ton e-mail · Digital · Humans"
        body_text = (
            f"Bonjour {to_name},\n\n"
            f"Bienvenue dans Digital · Humans. Confirme ton adresse e-mail en ouvrant ce lien :\n\n"
            f"{verify_url}\n\n"
            f"Le lien est valable 30 minutes. Si tu n'es pas à l'origine de cette demande, ignore "
            f"simplement ce message — aucun compte n'a été créé.\n\n"
            f"— Le studio"
        )

    body_html = (
        f"<p>{body_text.split(verify_url)[0].replace(chr(10), '<br>')}</p>"
        f"<p><a href=\"{verify_url}\" style=\"display:inline-block;padding:12px 20px;"
        f"background:#c8a97e;color:#0a0a0b;text-decoration:none;font-family:monospace;"
        f"letter-spacing:0.1em;text-transform:uppercase;font-size:11px;\">"
        f"{'Verify email' if lang == 'en' else 'Confirmer mon e-mail'}</a></p>"
        f"<p>{body_text.split(verify_url)[1].replace(chr(10), '<br>')}</p>"
    )

    get_sender().send(
        EmailMessageSpec(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )
    )
