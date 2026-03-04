"""Orchestrate the full report → PDF pipeline."""
from __future__ import annotations

from pathlib import Path

from ..reporting import ReportTemplate
from .chromium import render_to_html
from .resources import build
from .weasyprint import render_to_pdf

BUNDLE = Path(__file__).parents[2] / "packages" / "rendering" / "dist" / "bundle.js"

_SEVERITY: dict[str, tuple[int, str]] = {
    "critical":      (1, "critical"),
    "high":          (2, "high"),
    "medium":        (3, "medium"),
    "low":           (4, "low"),
    "informational": (5, "info"),
    "info":          (5, "info"),
}


def make_vue_data(raw: dict) -> dict:
    """Reshape raw Ghostwriter JSON into the three top-level variables the
    SysReptor rendering bundle exposes to templates: report, finding_groups,
    pentesters.

    - report        → the full raw JSON (all Ghostwriter fields accessible as
                       report.<field>), with augmented findings stored under
                       report.findings so templates can still iterate them.
    - finding_groups→ [{"findings": <augmented list>}] for templates that loop
                       over finding_groups[0].findings.
    - pentesters    → raw team list (alias kept for bundle compatibility).
    """
    findings = []
    for f in raw.get("findings") or []:
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

    report = dict(raw)
    report["findings"] = findings

    return {
        "report":        report,
        "finding_groups": [{"findings": findings}],
        "pentesters":    raw.get("team") or [],
    }


def render_report(
    report_json: dict,
    template: ReportTemplate,
    language: str = "tr",
) -> bytes:
    """Full pipeline: Ghostwriter JSON → Vue data → HTML → PDF."""
    if not BUNDLE.exists():
        raise FileNotFoundError(
            f"Vue rendering bundle not found at {BUNDLE}. "
            "Run: cd packages/rendering && npm install && npm run build"
        )

    data          = make_vue_data(report_json)
    template_html = template.html_path.read_text("utf-8")
    css           = template.css_path.read_text("utf-8") if template.css_path.exists() else None
    bundle_js     = BUNDLE.read_text("utf-8")
    resources     = build(template, report_json)

    html = render_to_html(data, template_html, css, bundle_js, language, resources)
    return render_to_pdf(html, resources)
