"""Convert rendered HTML to PDF using WeasyPrint with a local resource fetcher."""
from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import unquote

from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration
from weasyprint.urls import default_url_fetcher

from .chromium import RENDER_ORIGIN

logger = logging.getLogger(__name__)

_MIME = {
    "png":  "image/png",
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "gif":  "image/gif",
    "svg":  "image/svg+xml",
    "webp": "image/webp",
    "woff": "font/woff",
    "woff2": "font/woff2",
    "ttf":  "font/ttf",
}

_ORIGIN_PREFIX = RENDER_ORIGIN + "/"

_TRANSPARENT_1PX_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9cb\x00"
    b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _make_fetcher(resources: dict[str, bytes]):
    def fetcher(url: str) -> dict:
        if url.startswith(_ORIGIN_PREFIX):
            path = unquote(url[len(_ORIGIN_PREFIX):])
            if path in resources:
                ext  = Path(path).suffix.lower().lstrip(".")
                mime = _MIME.get(ext, "application/octet-stream")
                return {"string": resources[path], "mime_type": mime}
            logger.warning("WeasyPrint: resource not in bundle, using placeholder: %s", path)
            return {"string": _TRANSPARENT_1PX_PNG, "mime_type": "image/png"}
        # Non-local URLs (e.g. file:// for system fonts): use WeasyPrint default
        return default_url_fetcher(url)

    return fetcher


def render_to_pdf(html: str, resources: dict[str, bytes]) -> bytes:
    """Render HTML produced by Chromium stage to a PDF byte string."""
    font_config = FontConfiguration()
    doc = HTML(
        string=html,
        base_url=_ORIGIN_PREFIX,
        url_fetcher=_make_fetcher(resources),
    )
    return doc.write_pdf(
        font_config=font_config,
        presentational_hints=True,
        optimize_images=True,
    )
