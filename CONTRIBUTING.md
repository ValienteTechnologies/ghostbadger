# Contributing to Ghostbadger

Contributions are welcome. This document covers the main ways you can contribute.

---

## Ways to Contribute

- **Bug fixes** — patches for broken behavior, edge cases, rendering issues
- **New report templates** — additional HTML/CSS templates for different report styles
- **Ghostwriter field support** — handling new or missing fields from the Ghostwriter API
- **Documentation improvements** — clarifications, corrections, better examples
- **Feature additions** — new integrations or rendering capabilities that fit the scope of the tool

---

## Submitting a Patch

1. Fork the repository and create a branch from `main`
2. Make your changes — keep them focused and minimal
3. Test your changes locally before submitting
4. Open a pull request with a clear description of what the patch does and why

There is no strict commit message format, but be descriptive enough that the change is self-explanatory.

---

## Submitting a New Template

Templates live in `app/reporting/resources/templates/`. A valid template requires:

- `templates/<name>.html` — Vue + HTML markup
- `templates/<name>.css` — styles
- `assets/<name>/` — (optional) static files such as logos

See [app/reporting/resources/README.md](app/reporting/resources/README.md) for the full template authoring guide including available data fields and special components.

When submitting a template:

- Make sure it contains no client-specific or confidential content
- Use placeholder text and a generic logo if needed
- Keep it self-contained — no external URLs or fonts that require network access at render time

> [!WARNING]
> Do not submit templates that contain real client data, internal company information, or any sensitive content.

---

## Development Setup

```bash
git clone https://github.com/ValienteTechnologies/ghostbadger
cd ghostbadger

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

playwright install chromium

# Build the rendering bundle
cd packages/markdown && npm install && cd ../..
cd packages/rendering && npm install && npm run build && cd ../..
cd packages/bitwarden && npm install

FLASK_DEBUG=1 flask --app wsgi:application run
```

Tests:

```bash
.venv/bin/pytest tests/ -v
```

---

## Scope

This tool is built for a specific internal workflow and released as-is. Not every feature request will be accepted. If you are unsure whether a contribution fits, open an issue first to discuss it before investing time in the implementation.
