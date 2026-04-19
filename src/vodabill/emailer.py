"""Send bill PDFs via SMTP using environment variables."""

import os
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr

from dotenv import load_dotenv

_ENV_KEYS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD")


def _env_use_tls() -> bool:
    raw = os.environ.get("SMTP_USE_TLS")
    if raw is None or raw.strip() == "":
        return True
    return raw.strip().lower() in ("1", "true", "t", "yes", "y", "on")


def load_smtp_settings_from_env() -> dict:
    load_dotenv()
    missing = [k for k in _ENV_KEYS if not os.environ.get(k, "").strip()]
    if missing:
        raise RuntimeError(
            "SMTP is not configured: set these environment variables (e.g. in .env): "
            + ", ".join(missing)
            + ". Optional: SMTP_USE_TLS (default true)."
        )
    port_raw = os.environ["SMTP_PORT"].strip()
    try:
        port = int(port_raw)
    except ValueError as e:
        raise RuntimeError(f"SMTP_PORT must be an integer, got: {port_raw!r}") from e
    return {
        "host": os.environ["SMTP_HOST"].strip(),
        "port": port,
        "use_tls": _env_use_tls(),
        "username": os.environ["SMTP_USERNAME"].strip(),
        "password": os.environ["SMTP_PASSWORD"],
    }


def _normalize_recipient(to_addr: str) -> str:
    _, addr = parseaddr(to_addr.strip())
    if not addr or "@" not in addr:
        raise ValueError("Invalid recipient email address.")
    return addr


def send_bill_pdf(
    *,
    to_addr: str,
    pdf_bytes: bytes,
    filename: str,
    subject: str | None = None,
) -> None:
    to_normalized = _normalize_recipient(to_addr)
    cfg = load_smtp_settings_from_env()

    msg = EmailMessage()
    msg["Subject"] = subject or "Vodafone Rechnung (PDF)"
    msg["From"] = cfg["username"]
    msg["To"] = to_normalized
    msg.set_content("Anbei die aktuelle Vodafone-Rechnung als PDF.")

    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=filename,
    )

    host = cfg["host"]
    port = cfg["port"]
    use_tls = cfg["use_tls"]

    try:
        with smtplib.SMTP(host, port, timeout=120) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(str(cfg["username"]), str(cfg["password"]))
            smtp.send_message(msg)
    except OSError as e:
        raise RuntimeError(f"SMTP connection failed: {e}") from e
    except smtplib.SMTPException as e:
        raise RuntimeError(f"SMTP error: {e}") from e
