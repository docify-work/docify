"""Plain-text email bodies. Kept tiny and readable on purpose."""

from __future__ import annotations

from docify.config import get_settings
from docify.email.sender import Email


def _base() -> str:
    return get_settings().public_base_url.rstrip("/")


def verify_email(to: str, token: str) -> Email:
    return Email(to, "Verify your Docify email", (
        "Welcome to Docify!\n\n"
        f"Confirm your email address by opening this link (valid for 24 hours):\n{_base()}/verify-email?token={token}\n\n"
        "If you didn't sign up, you can ignore this email."
    ))


def signup_notice(to: str) -> Email:
    return Email(to, "Someone tried to sign up with your email", (
        "Someone (maybe you) tried to create a Docify account with this email address, "
        "but an account already exists.\n\n"
        f"Sign in: {_base()}/login\nForgot your password? {_base()}/forgot-password\n\n"
        "If this wasn't you, no action is needed."
    ))


def reset_password(to: str, token: str) -> Email:
    return Email(to, "Reset your Docify password", (
        f"Open this link to choose a new password (valid for 1 hour):\n{_base()}/reset-password?token={token}\n\n"
        "If you didn't ask for this, ignore this email; your password stays the same."
    ))


def invite(to: str, token: str, workspace_name: str, inviter: str) -> Email:
    return Email(to, f"You're invited to {workspace_name} on Docify", (
        f"{inviter} invited you to the '{workspace_name}' workspace on Docify.\n\n"
        f"Accept the invite (valid for 7 days):\n{_base()}/invite/{token}\n"
    ))
