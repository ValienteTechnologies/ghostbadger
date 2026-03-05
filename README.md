<p align="center">
  <img src="app/static/ghostbadger.png" width="250" />
</p>

**Ghostbadger** is a specialized PDF rendering engine designed to bridge the gap between [Ghostwriter](https://github.com/GhostManager/Ghostwriter) and secure client delivery. It automates the generation of polished, password-protected PDF reports by integrating directly with Ghostwriter's GraphQL API and [Vaultwarden](https://github.com/dani-garcia/vaultwarden).

---

> [!NOTE]  
> This tool was developed for our specific internal workflows. It is provided "as-is" without any guarantee or formal support. Use it at your own risk and expect to customize it to fit your specific needs. We decided to polish the code, modularize the integration, and release it to the community.

> [!IMPORTANT]
> Sessions are not persisted server-side — they are kept only in the client cookie. Cookie expiry is derived from the Ghostwriter JWT token (API key). Make sure to set a sufficiently long expiry when creating the API key in Ghostwriter, otherwise your session will expire mid-use.

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

### Templates

See [app/reporting/resources/README.md](app/reporting/resources/README.md) for full documentation on creating and modifying report templates, available data fields, special components, and page layout.

> [!IMPORTANT]
> `extra_fields` are custom fields defined in your Ghostwriter instance under **Commandcenter → Extra Field Configurations → Extra fields for Reports**. The field names in the demo templates reflect our own setup — yours will likely differ. Review and update all `report.extra_fields.*` references in your templates to match your Ghostwriter configuration.

---

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to submit patches, new templates, or other improvements.

---

### The Blog Post

https://valientetechnologies.com/blog/posts/introducing-ghostbadger/

### AI Generated Overview

[READMEg.md](READMEg.md)