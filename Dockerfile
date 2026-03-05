# Stage 1: Build JS packages
FROM node:22-bookworm-slim AS js-builder

WORKDIR /build

# markdown must be installed first — rendering depends on it as a local path dep
COPY packages/markdown ./packages/markdown
RUN cd packages/markdown && npm install

COPY packages/rendering ./packages/rendering
RUN cd packages/rendering && npm install && npm run build

COPY packages/bitwarden ./packages/bitwarden
RUN cd packages/bitwarden && npm install

# Stage 2: Python runtime
FROM python:3.12-slim-bookworm

# System deps for WeasyPrint + Node.js (needed to run bw CLI at runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    libfontconfig1 \
    libharfbuzz0b \
    fonts-liberation \
    fonts-dejavu-core \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium + all its system dependencies
RUN playwright install --with-deps chromium

COPY . .

# Copy built JS artifacts from js-builder
COPY --from=js-builder /build/packages/rendering/dist/ ./packages/rendering/dist/
COPY --from=js-builder /build/packages/bitwarden/node_modules/ ./packages/bitwarden/node_modules/

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
# Required when running as root (default in Docker)
ENV PLAYWRIGHT_CHROMIUM_NO_SANDBOX=1

EXPOSE 80

CMD ["gunicorn", "--bind", "0.0.0.0:80", "--workers", "4", "--timeout", "180", "wsgi:application"]
