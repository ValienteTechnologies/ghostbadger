<p align="center">
  <img src="app/static/ghostbadger.png" width="250" />
</p>

**Ghostbadger** is a specialized PDF rendering engine designed to bridge the gap between [Ghostwriter](https://github.com/GhostManager/Ghostwriter) and secure client delivery. It automates the generation of polished, password-protected PDF reports by integrating directly with Ghostwriter's GraphQL API and [Vaultwarden](https://github.com/dani-garcia/vaultwarden).


---

> [!NOTE]  
> This tool was developed for our specific internal workflows. It is provided "as-is" without any guarantee or formal support. Use it at your own risk and expect to customize it to fit your specific needs. We decided to polish the code, modularize the integration, and release it to the community.

### The Blog Post

https://valientetechnologies.com/blog/posts/introducing-ghostbadger/

### Quick Setup

**With Docker Compose (recommended)**

```bash
# 1. Create an env file
cat > .env <<'EOF'
SECRET_KEY=change-me
GHOSTWRITER_URL=https://your-ghostwriter-instance
VAULTWARDEN_URL=
VAULTWARDEN_ORG_ID=
VAULTWARDEN_COLLECTION_ID=
EOF

# 2. Pull and start
docker compose pull
docker compose up -d
```

> [!IMPORTANT]
> Sessions are not persisted server-side — they are kept only in the client cookie. Cookie expiry is derived from the Ghostwriter JWT token (API key). Make sure to set a sufficiently long expiry when creating the API key in Ghostwriter, otherwise your session will expire mid-use.

Templates and assets are seeded from the image on first run into `./resources/` — edit them freely.

> [!WARNING]
> The included templates are for demo purposes only. Do not use them for real client deliverables without reviewing and customizing them to your needs.

---

**Without Docker Compose**

```bash
docker run -d \
  --name ghostbadger \
  -p 80:80 \
  -e SECRET_KEY=change-me \
  -e GHOSTWRITER_URL=https://your-ghostwriter-instance \
  -v $(pwd)/resources:/app/reporting/resources \
  --restart unless-stopped \
  ghcr.io/valientetechnologies/ghostbadger:latest
```

> To serve under a subpath (e.g. `/ghostbadger`), add `-e APPLICATION_ROOT=/ghostbadger` to the `docker run` command, or uncomment the line in `compose.yaml`.

---

### Local Development

**Requirements**

- Python 3.12+
- Node.js (for the SysReptor rendering bundle and `bw` CLI)
- Chromium (installed by Playwright)

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd ghostbadger

# 2. Create a venv
python3 -m venv venv

# 3. Install Python dependencies
venv/bin/pip install -r requirements.txt

# 4. Install Playwright's Chromium browser
venv/bin/playwright install chromium

# 5. Install Markdown package dependencies
cd packages/markdown && npm install && cd ../..

# 6. Build the SysReptor Vue rendering bundle
cd packages/rendering && npm install && npm run build && cd ../..

# 7. (Optional) Install Bitwarden CLI for Vaultwarden integration
cd packages/bitwarden && npm install && cd ../..

# 8. Configure environment
cp .env.example .env
# Edit .env and set SECRET_KEY, GHOSTWRITER_URL, and optionally VAULTWARDEN_* values
```

**Running**

```bash
FLASK_DEBUG=1 venv/bin/flask --app wsgi:application run
```

Open http://localhost:5000, paste a Ghostwriter JWT token, and proceed to the dashboard.

**Tests**

```bash
.venv/bin/pytest tests/ -v
```

---

### Project Structure

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

---

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Flask session signing key |
| `GHOSTWRITER_URL` | Yes | Base URL of Ghostwriter instance |
| `VAULTWARDEN_URL` | No | Vaultwarden server URL |
| `VAULTWARDEN_ORG_ID` | No | Organisation ID for vault items |
| `VAULTWARDEN_COLLECTION_ID` | No | Collection ID for vault items |

---

### Templates

See [app/reporting/resources/README.md](app/reporting/resources/README.md) for full documentation on creating and modifying report templates, available data fields, special components, and page layout.

> [!IMPORTANT]
> `extra_fields` are custom fields defined in your Ghostwriter instance under **Commandcenter → Extra Field Configurations → Extra fields for Reports**. The field names in the demo templates reflect our own setup — yours will likely differ. Review and update all `report.extra_fields.*` references in your templates to match your Ghostwriter configuration.

---

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to submit patches, new templates, or other improvements.

---

### Acknowledgements

The PDF rendering pipeline is inspired by [SysReptor](https://github.com/Syslifters/sysreptor)'s PDF export engine, reusing its Vue-based template rendering bundle and template format.