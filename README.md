# Vodabill

Vodabill is a small command-line tool that signs in to [MeinVodafone](https://www.vodafone.de/meinvodafone/), opens your bills page, and works with the **latest** bill (the first “Rechnung (PDF)” entry shown there). It can print which bill that is, save the PDF to disk, and optionally email the PDF via SMTP.

- You supply Vodafone login credentials locally (environment variables).
- A real Chromium browser is driven with [Playwright](https://playwright.dev/).
- Email is optional and uses SMTP settings from environment variables (typically in `.env`).

## Prerequisites

- **Python** 3.14 or newer (`requires-python = ">=3.14"` in this project).
- **[Poetry](https://python-poetry.org/)** 2.x (the build uses `poetry-core` 2.x).
- A Vodafone account that can log in on the German customer portal.
- For `--send-to`, an SMTP account you are allowed to use, configured via `SMTP_*` variables (see below).

## Setup with Poetry

1. Clone or copy this repository and open a terminal in the project root (the directory that contains `pyproject.toml`).

2. Install dependencies:

   ```bash
   poetry install
   ```

3. Install the Chromium browser used by Playwright (this project launches Chromium only):

   ```bash
   poetry run playwright install chromium
   ```

4. Create a `.env` file in the **project root** with your Vodafone credentials:

   ```env
   VODAFONE_EMAIL=you@example.com
   VODAFONE_PASSWORD=your-password
   ```

   These names must match exactly. The application loads them when it runs.

5. **Optional — email:** To use `--send-to`, add SMTP variables to your **project root** `.env`:

   ```env
   SMTP_HOST=smtp.example.com
   SMTP_PORT=587
   SMTP_USE_TLS=true
   SMTP_USERNAME=smtp-user@example.com
   SMTP_PASSWORD=your-smtp-password
   ```

   `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, and `SMTP_PASSWORD` are required for sending mail. `SMTP_USE_TLS` is optional and defaults to `true` (STARTTLS) when unset or empty.  
   `.env` is listed in `.gitignore` so it is not committed by default. A legacy `smtp_config.json` in the project root is still ignored if present but is no longer read by the application.

## How to run

After `poetry install`, invoke the CLI through Poetry:

```bash
poetry run vodabill --help
poetry run vodabill latest-bill --help
```

If you prefer, activate the virtual environment Poetry created (`poetry shell`) and run `vodabill` the same way without the `poetry run` prefix.

---

## Command reference

The entry point is the `vodabill` program. It is a Click **command group** with a short help string (“Vodafone bill automation.”). Today the only subcommand is `latest-bill`.

### `vodabill`

Running `vodabill` with no subcommand shows group help and lists `latest-bill`. Use `vodabill --help` for the same.

### `vodabill latest-bill`

**What it does:** Starts Chromium, logs into MeinVodafone with `VODAFONE_EMAIL` / `VODAFONE_PASSWORD`, goes to the bills page, treats the **first** “Rechnung (PDF)” control as the latest bill, and prints a line such as:

```text
Latest bill: Rechnung April 2026 PDF Link
```

The exact text after `Latest bill:` comes from the portal (typically an accessibility label).

**Saving and emailing** both need the PDF to be retrieved successfully in that session. If retrieval fails, the command exits with an error and no file is written and no mail is sent.

#### Options

| Option | Description |
|--------|-------------|
| `--download` | Controls whether a PDF is written to disk. See below. |
| `--browser-headless` / `--no-browser-headless` | Whether Chromium runs without a window. **Default:** headless (`--browser-headless` is the default). |
| `--send-to EMAIL` | Send the PDF to `EMAIL` using `SMTP_*` variables from the environment (e.g. `.env`). |

##### `--download`

Three cases:

1. **Omit `--download` entirely**  
   No PDF is saved. The run still logs in, opens bills, and prints `Latest bill: …`. You may still use `--send-to` if you want only email.

2. **`--download` with no value** (flag only)  
   Saves the PDF under the project’s `downloads/` directory. The filename is generated from the bill label (month and year in the label become something like `vodafone_rechnung_April_2026.pdf`). The `downloads/` folder is created if needed.

3. **`--download /absolute/or/relative/path/to/file.pdf`**  
   Saves the PDF to that path. Requirements enforced by the CLI:

   - The path must end with `.pdf` (case-insensitive). Otherwise the command fails with a parameter error.
   - The **parent directory must already exist**. If it does not, the command fails with a clear error.

##### `--browser-headless` / `--no-browser-headless`

- **Default:** headless mode (no visible browser window).
- **`--no-browser-headless`:** Opens a visible Chromium window. Useful if consent dialogs, overlays, or other steps are easier to complete or observe when you can see the UI.

##### `--send-to EMAIL`

- Sends one email with the PDF attached, using SMTP settings from the environment (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and optionally `SMTP_USE_TLS`).
- Default message subject is **Vodafone Rechnung (PDF)**; the body is a short German line stating that the current Vodafone bill is attached.
- The address must be valid; malformed addresses are rejected with an error.

#### Combining options

Examples (run from the project root or ensure `.env` is loaded as you expect):

- Latest bill info only, visible browser:

  ```bash
  poetry run vodabill latest-bill --no-browser-headless
  ```

- Save to default `downloads/` folder and email:

  ```bash
  poetry run vodabill latest-bill --download --send-to you@example.com
  ```

- Save to a specific file and keep the browser visible:

  ```bash
  poetry run vodabill latest-bill --download /path/to/existing/dir/rechnung.pdf --no-browser-headless
  ```

- Email only (no `--download`):

  ```bash
  poetry run vodabill latest-bill --send-to you@example.com
  ```

---

## Troubleshooting

- **Browser / Playwright errors** — Run `poetry run playwright install chromium` again after upgrades or on a new machine.
- **Python version** — Use Python 3.14+; older interpreters will not satisfy `pyproject.toml`.
- **Login failures** — Check `VODAFONE_EMAIL` and `VODAFONE_PASSWORD` in `.env`; try `--no-browser-headless` to see what the portal shows.
- **`--send-to` fails** — Ensure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, and `SMTP_PASSWORD` are set in `.env` (and optional `SMTP_USE_TLS` matches your provider). Check host, port, TLS, and credentials.

## Disclaimer

This project is **not** affiliated with or endorsed by Vodafone. The MeinVodafone website can change at any time, which may break automation. Use at your own risk and only with credentials and accounts you are authorized to use.
