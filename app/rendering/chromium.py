"""Render a Vue report template to HTML using headless Chromium via Playwright."""
from __future__ import annotations

import asyncio
import json

from playwright.async_api import async_playwright

# All local resources are served under this origin so relative URLs
# in templates resolve predictably in both Chromium and WeasyPrint.
RENDER_ORIGIN = "http://render.local"


async def _render(
    data: dict,
    template_html: str,
    css: str | None,
    bundle_js: str,
    language: str,
    resources: dict[str, bytes],
) -> str:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page    = await browser.new_page()

        # Surface template/JS errors in output instead of producing a blank page
        page.on("console",   lambda m: None)  # suppress noise; errors handled below
        page.on("pageerror", lambda e: None)

        # Intercept every request: serve from resources dict, block everything else
        async def handle_route(route):
            url  = route.request.url
            path = url.removeprefix(RENDER_ORIGIN).lstrip("/")
            if path in resources:
                await route.fulfill(body=resources[path], status=200)
            else:
                await route.abort()

        await page.route("**/*", handle_route)

        # Minimal shell with a base tag so all relative URLs resolve under RENDER_ORIGIN
        await page.set_content(
            f'<!DOCTYPE html>'
            f'<html lang="{language}">'
            f'<head>'
            f'<meta charset="utf-8"/>'
            f'<base href="{RENDER_ORIGIN}/"/>'
            f'</head>'
            f'<body></body>'
            f'</html>',
            base_url=f"{RENDER_ORIGIN}/",
        )

        if css:
            await page.add_style_tag(content=css)

        await page.add_script_tag(content=bundle_js)

        payload = json.dumps(
            {"template": template_html, "reportData": data},
            ensure_ascii=False,
        )

        await page.evaluate(
            """(payload) => {
                const { template, reportData } = JSON.parse(payload);
                window.REPORT_TEMPLATE  = template;
                window.REPORT_DATA      = reportData;
                window.RENDERING_COMPLETED = false;
                try {
                    window.renderReportTemplate();
                } catch (e) {
                    document.body.innerHTML =
                        '<pre style="white-space:pre-wrap;font-family:monospace">'
                        + 'Render error: ' + String(e)
                        + (e && e.stack ? '\\n' + String(e.stack) : '')
                        + '</pre>';
                    window.RENDERING_COMPLETED = true;
                }
            }""",
            payload,
        )

        await page.wait_for_function(
            "window.RENDERING_COMPLETED === true",
            timeout=60_000,
        )

        # Strip script tags — WeasyPrint does not need them
        await page.evaluate(
            "() => document.querySelectorAll('script').forEach(s => s.remove())"
        )

        html = await page.content()
        await browser.close()

    return html


def render_to_html(
    data: dict,
    template_html: str,
    css: str | None,
    bundle_js: str,
    language: str,
    resources: dict[str, bytes],
) -> str:
    """Sync wrapper — safe to call from a Flask route (creates its own event loop)."""
    return asyncio.run(_render(data, template_html, css, bundle_js, language, resources))
