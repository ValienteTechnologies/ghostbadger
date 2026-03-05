# Ghostbadger

Flask web app that connects to a [Ghostwriter](https://github.com/GhostManager/Ghostwriter) instance, generates report JSON via GraphQL, and renders password-encrypted PDF reports using a headless Chromium + WeasyPrint pipeline.

Optionally integrates with [Vaultwarden](https://github.com/dani-garcia/vaultwarden) to store PDF passwords and create Bitwarden Send links.

## Requirements

- Python 3.12+
- Node.js (for the SysReptor rendering bundle and `bw` CLI)
- Chromium (installed by Playwright)

## Setup

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd ghostbadger

# 2. Create and activate venv
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Playwright's Chromium browser
playwright install chromium

# 5. Build the SysReptor Vue rendering bundle
cd packages/rendering && npm install && npm run build && cd ../..

# 6. (Optional) Install Bitwarden CLI for Vaultwarden integration
cd packages/bitwarden && npm install && cd ../..

# 7. Configure environment
cp .env.example .env
# Edit .env and set SECRET_KEY, GHOSTWRITER_URL, and optionally VAULTWARDEN_* values
```

## Running

```bash
FLASK_DEBUG=1 .venv/bin/flask --app wsgi:application run
```

Open http://localhost:5000, paste a Ghostwriter JWT token, and proceed to the dashboard.

## Tests

```bash
.venv/bin/pytest tests/ -v
```

## Project structure

```
app/
  __init__.py          # App factory
  config.py            # Dev / Prod / Test config
  ghostwriter.py       # Ghostwriter GraphQL client
  vaultwarden.py       # Vaultwarden / bw CLI integration
  auth/                # JWT validation + require_token decorator
  onboarding/          # Login blueprint (/, /logout)
  dashboard/           # Main blueprint + all API routes
  reporting/           # Report templates (.html + .css) and evidence cache
  rendering/           # PDF pipeline: Chromium → HTML → WeasyPrint → PDF
  static/              # CSS
  templates/           # Jinja2 templates
packages/
  rendering/           # SysReptor Vue rendering bundle (pre-built)
  bitwarden/           # Local bw CLI install
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Flask session signing key |
| `GHOSTWRITER_URL` | Yes | Base URL of Ghostwriter instance |
| `VAULTWARDEN_URL` | No | Vaultwarden server URL |
| `VAULTWARDEN_ORG_ID` | No | Organisation ID for vault items |
| `VAULTWARDEN_COLLECTION_ID` | No | Collection ID for vault items |
