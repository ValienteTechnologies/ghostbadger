"""Orchestrate the full report → PDF pipeline."""
from __future__ import annotations

from pathlib import Path

from ..reporting import ReportTemplate
from .chromium import render_to_html
from .resources import build
from .weasyprint import render_to_pdf

_BUNDLE = Path(__file__).parents[2] / "packages" / "rendering" / "dist" / "bundle.js"

_SEVERITY: dict[str, tuple[int, str]] = {
    "critical":      (1, "critical"),
    "high":          (2, "high"),
    "medium":        (3, "medium"),
    "low":           (4, "low"),
    "informational": (5, "info"),
    "info":          (5, "info"),
}


def _augment_findings(raw: dict) -> dict:
    """Return a shallow copy of the report JSON with a `cvss` helper added to
    each finding.  Everything else is the raw Ghostwriter JSON untouched."""
    data = dict(raw)
    findings = []
    for f in data.get("findings") or []:
        f = dict(f)
        sev = (f.get("severity") or "info").lower()
        level_num, level = _SEVERITY.get(sev, (5, "info"))
        f["cvss"] = {
            "level":        level,
            "level_number": level_num,
            "score":        float(f.get("cvss_score") or 0),
            "vector":       f.get("cvss_vector") or "n/a",
        }
        findings.append(f)
    data["findings"] = findings
    return data


def render_report(
    report_json: dict,
    template: ReportTemplate,
    language: str = "tr",
) -> bytes:
    """Full pipeline: Ghostwriter JSON → augmented data → HTML → PDF.

    Args:
        report_json: Raw decoded report dict from Ghostwriter's generateReport mutation.
        template:    Selected ReportTemplate (html_path, css_path, assets_dir).
        language:    BCP-47 language tag for the HTML document (default: "tr").

    Returns:
        PDF as bytes.

    Raises:
        FileNotFoundError: If the Vue rendering bundle is missing.
        RuntimeError: If Chromium or WeasyPrint rendering fails.
    """
    if not _BUNDLE.exists():
        raise FileNotFoundError(
            f"Vue rendering bundle not found at {_BUNDLE}. "
            "Run: cd packages/rendering && npm install && npm run build"
        )

    data         = _augment_findings(report_json)
    template_html = template.html_path.read_text("utf-8")
    css          = template.css_path.read_text("utf-8") if template.css_path.exists() else None
    bundle_js    = _BUNDLE.read_text("utf-8")
    resources    = build(template, report_json)

    html = render_to_html(data, template_html, css, bundle_js, language, resources)
    return render_to_pdf(html, resources)
