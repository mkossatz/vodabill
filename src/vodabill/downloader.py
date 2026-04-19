"""Vodafone bill downloader using Playwright."""

import base64
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from vodabill import emailer


load_dotenv()

EMAIL = os.environ["VODAFONE_EMAIL"]
PASSWORD = os.environ["VODAFONE_PASSWORD"]
LOGIN_URL = "https://www.vodafone.de/meinvodafone/account/login"
BILLS_URL = "https://www.vodafone.de/meinvodafone/services/ihre-rechnungen/rechnungen"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOWNLOAD_DIR = PROJECT_ROOT / "downloads"


def nudge_page_interaction(page) -> None:
    """
    Vodafone's SPA sometimes sits behind a loading layer until the page gets a
    real focus/pointer signal (similar to clicking once manually). Not a cookie
    issue — it is common for heavy client-side bundles + consent flows.
    """
    try:
        page.bring_to_front()
    except Exception:
        pass
    try:
        page.evaluate(
            """() => {
                window.focus();
                try { document.body?.focus(); } catch (e) {}
            }"""
        )
    except Exception:
        pass
    vp = page.viewport_size
    w = int((vp or {}).get("width") or 1280)
    h = int((vp or {}).get("height") or 900)
    try:
        page.mouse.click(w // 2, h // 2)
    except Exception:
        pass
    page.wait_for_timeout(500)


def accept_cookies(page):
    for selector in ["button:has-text('Alle akzeptieren')", "#onetrust-accept-btn-handler"]:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(1500)
                return
        except Exception:
            pass


def dismiss_dip_consent(page) -> None:
    """Dismiss Vodafone DIP (#dip-consent) modal so login controls receive clicks."""
    consent = page.locator("#dip-consent")
    try:
        if not consent.is_visible(timeout=2500):
            return
    except Exception:
        return

    for pattern in (
        "button:has-text('Alle akzeptieren')",
        "button:has-text('Alle Cookies akzeptieren')",
        "button:has-text('Akzeptieren und weiter')",
        "button:has-text('Zustimmen und weiter')",
        "button:has-text('Zustimmen')",
        "button:has-text('Akzeptieren')",
    ):
        try:
            btn = consent.locator(pattern).first
            if btn.is_visible(timeout=1200):
                btn.click()
                page.wait_for_timeout(2000)
                try:
                    if not consent.is_visible(timeout=1500):
                        return
                except Exception:
                    return
        except Exception:
            pass


def login(page):
    print(f"Navigating to login: {LOGIN_URL}")
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    nudge_page_interaction(page)
    accept_cookies(page)
    dismiss_dip_consent(page)
    nudge_page_interaction(page)

    page.locator("#username-text").fill(EMAIL)
    page.locator("#passwordField-input").fill(PASSWORD)
    dismiss_dip_consent(page)

    page.locator("button[type='submit']").filter(has_text="Anmelden").first.click()
    page.wait_for_timeout(4000)
    print(f"Post-login URL: {page.url}")


def fetch_latest_bill(page, context) -> tuple[str, bytes | None]:
    """
    Navigate to the bills page, return (aria_label, pdf_bytes).
    pdf_bytes is None if interception fails.
    """
    print(f"Navigating to bills: {BILLS_URL}")
    page.goto(BILLS_URL, wait_until="load", timeout=120_000)
    nudge_page_interaction(page)
    dismiss_dip_consent(page)
    try:
        page.wait_for_load_state("networkidle", timeout=60_000)
    except Exception:
        pass

    # SPA: invoice list often appears after APIs finish; avoid fixed sleeps only.
    pdf_buttons = page.locator("button.ws10-button-link").filter(has_text="Rechnung (PDF)")
    try:
        pdf_buttons.first.wait_for(state="visible", timeout=120_000)
    except Exception:
        pdf_buttons = page.locator("button, a").filter(
            has_text=re.compile(r"Rechnung\s*\(PDF\)", re.I)
        )
        try:
            pdf_buttons.first.wait_for(state="visible", timeout=30_000)
        except Exception as e:
            raise RuntimeError(
                "No PDF bill buttons found on the bills page (page may still be loading)."
            ) from e

    count = pdf_buttons.count()
    if count == 0:
        raise RuntimeError("No PDF bill buttons found on the bills page.")

    first_pdf_btn = pdf_buttons.first
    first_pdf_btn.scroll_into_view_if_needed()
    aria_label = first_pdf_btn.get_attribute("aria-label") or "latest"

    # Intercept the PDF network response before it becomes a blob URL.
    # Vodafone fetches the PDF via XHR then wraps it in a blob: URL for the
    # new tab — we capture the raw bytes at the network layer instead.
    pdf_bytes_holder: list[bytes] = []

    # Vodafone's invoiceDocument API returns JSON with a base64-encoded PDF
    # in the "data" field.  Intercept that response directly — no blob needed.
    def handle_response(response):
        if "invoiceDocument" in response.url:
            try:
                payload = json.loads(response.body())
                raw = base64.b64decode(payload["data"])
                if raw[:4] == b"%PDF":
                    pdf_bytes_holder.append(raw)
            except Exception:
                pass

    context.on("response", handle_response)

    with context.expect_page() as new_page_info:
        first_pdf_btn.click()

    new_page_info.value  # ensure the page handle is resolved
    page.wait_for_timeout(8000)
    context.remove_listener("response", handle_response)

    return aria_label, pdf_bytes_holder[0] if pdf_bytes_holder else None


def _filename_from_label(aria_label: str) -> str:
    """'Rechnung April 2026 PDF Link' -> 'vodafone_rechnung_April_2026.pdf'"""
    parts = aria_label.split()
    if len(parts) >= 3:
        return f"vodafone_rechnung_{parts[1]}_{parts[2]}.pdf"
    return "vodafone_rechnung_latest.pdf"


def run(
    download_path: Path | None = None,
    headless: bool = True,
    send_to: str | None = None,
):
    """
    Log in, retrieve the latest bill, and optionally save or email it.

    Args:
        download_path: Where to save the PDF. If a directory, the filename is
                       derived from the bill's month/year. If None, don't save.
        headless: Run the browser without a visible window.
        send_to: If set, email the PDF to this address (requires intercepted PDF).
                 SMTP settings come from environment variables (see emailer module).
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=150 if not headless else 0)
        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": 1280, "height": 900},
        )
        # Ephemeral context is already isolated; be explicit so no prior Vodafone cookies/session bleed in.
        context.clear_cookies()
        context.clear_permissions()
        page = context.new_page()

        login(page)

        aria_label, pdf_bytes = fetch_latest_bill(page, context)
        browser.close()

    print(f"Latest bill: {aria_label}")

    pdf_filename = _filename_from_label(aria_label)

    if download_path is not None:
        if pdf_bytes is None:
            raise RuntimeError("PDF could not be intercepted from Vodafone.")

        if download_path.is_dir() or download_path.suffix.lower() != ".pdf":
            download_path = download_path / pdf_filename

        download_path.parent.mkdir(parents=True, exist_ok=True)
        download_path.write_bytes(pdf_bytes)
        print(f"Saved: {download_path} ({len(pdf_bytes):,} bytes)")

    if send_to is not None:
        if pdf_bytes is None:
            raise RuntimeError("PDF could not be intercepted from Vodafone.")

        try:
            emailer.send_bill_pdf(
                to_addr=send_to,
                pdf_bytes=pdf_bytes,
                filename=pdf_filename,
            )
        except ValueError as e:
            raise RuntimeError(str(e)) from e

        print(f"Emailed bill to {send_to}")


if __name__ == "__main__":
    run()
