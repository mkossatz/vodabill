"""Vodabill CLI."""

from pathlib import Path
import click
from vodabill import downloader


@click.group()
def cli():
    """Vodafone bill automation."""


@cli.command("latest-bill")
@click.option(
    "--download",
    default=None,
    is_flag=False,
    flag_value="__default__",
    metavar="[PATH]",
    help=(
        "Download the latest bill PDF. "
        "Use without a value to save to the default downloads/ directory, "
        "or provide a path like /some/dir/bill.pdf."
    ),
)
@click.option(
    "--browser-headless/--no-browser-headless",
    default=True,
    show_default=True,
    help="Run the browser headlessly (no visible window).",
)
@click.option(
    "--send-to",
    "send_to",
    default=None,
    metavar="EMAIL",
    help="Email the latest bill PDF to this address (requires SMTP_* variables in .env).",
)
def latest_bill(download: str | None, browser_headless: bool, send_to: str | None):
    """Show info about the latest bill and optionally download the PDF."""
    download_path: Path | None = None

    if download == "__default__":
        download_path = downloader.DOWNLOAD_DIR  # filename derived from bill label

    elif download is not None:
        p = Path(download)
        if p.suffix.lower() != ".pdf":
            raise click.BadParameter(
                f"'{download}' does not end with .pdf",
                param_hint="--download",
            )
        if not p.parent.exists():
            raise click.BadParameter(
                f"Directory does not exist: {p.parent}",
                param_hint="--download",
            )
        download_path = p

    try:
        downloader.run(
            download_path=download_path,
            headless=browser_headless,
            send_to=send_to,
        )
    except RuntimeError as e:
        raise click.ClickException(str(e)) from e
