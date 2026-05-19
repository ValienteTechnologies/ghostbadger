"""Orchestrate the full report → PDF pipeline."""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path

from ..reporting import ReportTemplate
from ..reporting.evidence import collect_evidence
from .chromium import render_to_html
from .resources import build
from .weasyprint import render_to_pdf

BUNDLE = Path(__file__).parents[2] / "packages" / "rendering" / "dist" / "bundle.js"

# Matches Ghostwriter's old-dot-var syntax: {{.name}}, {{.ref name}}, {{.caption name}}
_GW_TAG_RE = re.compile(r"\{\{\s*\.([^\{\}]*?)\s*\}\}")

# Matches Ghostwriter's newer TinyMCE richtext evidence div:
#   <div class="richtext-evidence" data-evidence-id="4"></div>
# Attribute order may vary; this handles both orderings.
_GW_RICHTEXT_RE = re.compile(
    r'<div\b[^>]*\bclass="richtext-evidence"[^>]*\bdata-evidence-id="(\d+)"[^>]*>\s*</div>'
    r'|'
    r'<div\b[^>]*\bdata-evidence-id="(\d+)"[^>]*\bclass="richtext-evidence"[^>]*>\s*</div>'
)

# Rich-text finding fields that Ghostwriter allows inline evidence in.
# "title" is intentionally excluded — it is plain text, never richtext.
# report.extra_fields are also excluded; Ghostwriter does not support inline
# evidence there, so we leave those fields untouched.
_FINDING_TEXT_FIELDS = (
    "affected_entities",
    "description",
    "impact",
    "mitigation",
    "recommendation",
    "replication_steps",
    "host_detection_techniques",
    "network_detection_techniques",
    "references",
)

_SEVERITY: dict[str, tuple[int, str]] = {
    "critical":      (1, "critical"),
    "high":          (2, "high"),
    "medium":        (3, "medium"),
    "low":           (4, "low"),
    "informational": (5, "info"),
    "info":          (5, "info"),
}

def _build_evidence_index(report_json: dict) -> tuple[dict[str, dict], dict[int, dict]]:
    """Build two evidence lookups from the report JSON:
      by_name: friendly_name → evidence object  (for {{.name}} tags)
      by_id:   numeric id    → evidence object  (for richtext-evidence divs)
    """
    by_name: dict[str, dict] = {}
    by_id:   dict[int, dict] = {}
    for ev in collect_evidence(report_json):
        fn = ev.get("friendly_name")
        if isinstance(fn, str) and fn:
            by_name[fn] = ev
        by_id[ev["id"]] = ev
    return by_name, by_id


def _resolve_inline_evidence(text: str, ev_index: dict[str, dict]) -> tuple[str, set[int]]:
    """Replace Ghostwriter inline evidence tags in an HTML field.

    Ghostwriter stores two tag forms in rich-text fields that are shipped as-is
    in the generateReport JSON (Jinja2 is not applied for JSON export):

        {{.friendly_name}}         → inline evidence image
        {{.ref friendly_name}}     → text reference (friendly name / caption)
        {{.caption friendly_name}} → caption label for the figure

    Returns (resolved_text, set of evidence IDs that were embedded as images).
    """
    if not ev_index or not text or "{{" not in text:
        return text, set()

    used_ids: set[int] = set()

    def _replace(m: re.Match) -> str:
        contents = m.group(1).strip()

        if contents.startswith("ref "):
            name = contents[4:].strip()
            ev = ev_index.get(name)
            if ev:
                return html.escape(ev.get("caption") or ev.get("friendly_name") or name)
            return html.escape(name)

        if contents.startswith("caption "):
            name = contents[8:].strip()
            ev = ev_index.get(name)
            if ev:
                return html.escape(ev.get("caption") or ev.get("friendly_name") or name)
            return html.escape(name)

        # Plain {{.name}} → inline evidence image wrapped in figure/figcaption
        name = contents
        ev = ev_index.get(name)
        if ev and ev.get("path"):
            used_ids.add(ev["id"])
            caption = html.escape(ev.get("caption") or ev.get("friendly_name") or name)
            path = html.escape(ev["path"])
            return (
                f'<figure>'
                f'<img src="{path}" alt="{caption}" style="max-width:100%">'
                f'<figcaption>{caption}</figcaption>'
                f'</figure>'
            )
        return m.group(0)  # unknown name — leave unchanged

    return _GW_TAG_RE.sub(_replace, text), used_ids


def _resolve_richtext_evidence(text: str, ev_by_id: dict[int, dict]) -> tuple[str, set[int]]:
    """Replace Ghostwriter richtext-evidence divs with figure/img/figcaption.

    Newer Ghostwriter TinyMCE versions store inline evidence as:
        <div class="richtext-evidence" data-evidence-id="4"></div>
    instead of the older {{.friendly_name}} tag syntax.

    Returns (resolved_text, set of evidence IDs that were embedded as images).
    """
    if not ev_by_id or not text or 'richtext-evidence' not in text:
        return text, set()

    used_ids: set[int] = set()

    def _replace(m: re.Match) -> str:
        eid_str = m.group(1) or m.group(2)
        ev = ev_by_id.get(int(eid_str))
        if ev and ev.get("path"):
            used_ids.add(ev["id"])
            caption = html.escape(ev.get("caption") or ev.get("friendly_name") or eid_str)
            path = html.escape(ev["path"])
            return (
                f'<figure>'
                f'<img src="{path}" alt="{caption}" style="max-width:100%">'
                f'<figcaption>{caption}</figcaption>'
                f'</figure>'
            )
        return m.group(0)  # unknown id — leave unchanged

    return _GW_RICHTEXT_RE.sub(_replace, text), used_ids


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)


def _is_blank(v: str) -> bool:
    """True if v contains no visible text content (handles plain strings and HTML)."""
    p = _TextExtractor()
    p.feed(v)
    return not ''.join(p._chunks).strip()


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

    report.extra_fields (Ghostwriter custom report fields):
      - about_us           markdown  Company/team introduction paragraph.
      - executive_summary  markdown  High-level summary of findings for management.
      - attack_chain       markdown  Optional narrative describing the attack chain.
      - methodology        markdown  Testing methodology and approach description.
      - scope_text         markdown  Prose addendum to the structured scope list.
      - disclaimer         markdown  Legal disclaimer / liability statement.
      - appendix           markdown  Optional appendix content; section hidden when empty.

    Blank extra_field strings (whitespace-only or HTML with no visible text) are
    normalised to None so templates can use a simple truthiness check to
    conditionally render optional sections.
    """
    ev_by_name, ev_by_id = _build_evidence_index(raw)

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
        if ev_by_name or ev_by_id:
            inline_ids: set[int] = set()
            for field in _FINDING_TEXT_FIELDS:
                raw_val = f.get(field)
                if not isinstance(raw_val, str):
                    continue
                resolved = raw_val
                if "{{" in resolved:
                    resolved, used = _resolve_inline_evidence(resolved, ev_by_name)
                    inline_ids |= used
                if "richtext-evidence" in resolved:
                    resolved, used = _resolve_richtext_evidence(resolved, ev_by_id)
                    inline_ids |= used
                f[field] = resolved
            if inline_ids and isinstance(f.get("evidence"), list):
                f["evidence"] = [ev for ev in f["evidence"] if ev.get("id") not in inline_ids]
        findings.append(f)

    report = dict(raw)
    report["findings"] = findings
    if isinstance(report.get("extra_fields"), dict):
        report["extra_fields"] = {
            k: (None if isinstance(v, str) and _is_blank(v) else v)
            for k, v in report["extra_fields"].items()
        }

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

    rendered_html = render_to_html(data, template_html, css, bundle_js, language, resources)
    return render_to_pdf(rendered_html, resources)
