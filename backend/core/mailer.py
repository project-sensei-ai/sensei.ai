"""Outbound email.

Optional by design: with no SMTP settings the app still works — the API returns
the invite link and the owner copies it from the UI. That matters for reviewers,
who cannot receive mail at an address they do not own.
"""
import asyncio
import smtplib
from email.message import EmailMessage

from core.config import settings


def is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM)


def _send_sync(to: str, subject: str, text: str, html: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    if settings.SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
        if settings.SMTP_STARTTLS:
            server.starttls()
    with server:
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


async def send_invite(to: str, workspace: str, inviter: str, link: str) -> bool:
    """
    Email an invite link. Returns True if it was actually sent.

    The link carries a single-use token; the recipient sets their own password on
    arrival. No password is ever put in an email — they leak into inboxes, get
    forwarded, and never expire.
    """
    if not is_configured():
        return False

    subject = f"{inviter} added you to {workspace} on Sensei"
    text = (
        f"{inviter} added you to the project \"{workspace}\" on Sensei.\n\n"
        f"Set your password and join here:\n{link}\n\n"
        f"The link works once and expires in 7 days.\n"
        f"If you were not expecting this, ignore this email — nothing was created for you.\n"
    )
    html = f"""\
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
            max-width:480px;margin:0 auto;padding:32px 24px;color:#14161a">
  <h2 style="margin:0 0 8px;font-size:20px">You've been added to {workspace}</h2>
  <p style="margin:0 0 24px;color:#5f6570;font-size:14px;line-height:1.6">
    {inviter} added you to this project on Sensei. Set your password to join —
    the agent already knows the project and can answer your questions with sources.
  </p>
  <a href="{link}" style="display:inline-block;background:#14161a;color:#fff;
     text-decoration:none;padding:11px 20px;border-radius:8px;font-size:14px;font-weight:600">
    Set password and join
  </a>
  <p style="margin:24px 0 0;color:#8b919b;font-size:12px;line-height:1.6">
    This link works once and expires in 7 days.<br>
    If you weren't expecting this, ignore it — no account was created for you.
  </p>
</div>"""
    try:
        await asyncio.to_thread(_send_sync, to, subject, text, html)
        return True
    except Exception as exc:
        print(f"[mail] invite to {to} failed: {exc}")
        return False
