<p align="center">
  <img src="app/static/ghostbadger.png" width="250" />
</p>

**Ghostbadger** is a specialized PDF rendering engine designed to bridge the gap between [Ghostwriter](https://github.com/GhostManager/Ghostwriter) and secure client delivery. It automates the generation of polished, password-protected PDF reports by integrating directly with Ghostwriter's GraphQL API and [Vaultwarden](https://github.com/dani-garcia/vaultwarden).

---

> [!NOTE]  
> This tool was developed for our specific internal workflows. It is provided "as-is" without any guarantee or formal support. Use it at your own risk and expect to customize it to fit your specific needs. We decided to polish the code, modularize the integration, and release it to the community.

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

### The Blog Post

https://valientetechnologies.com/blog/posts/introducing-ghostbadger/

### AI Generated Overview

[READMEg.md](READMEg.md)