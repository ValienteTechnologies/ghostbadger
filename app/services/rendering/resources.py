"""Build the resource map (URL path -> bytes) for a render job.

Both the Chromium and WeasyPrint stages use this dict to serve local files
(template images, evidence screenshots) without making external HTTP requests.
"""
from __future__ import annotations

from pathlib import Path

from ...reporting import ReportTemplate
from ...reporting.evidence import collect_paths, local_path


def build(template: ReportTemplate, report_json: dict) -> dict[str, bytes]:
    """Return a mapping of URL path -> file bytes for all assets in this report.

    Keys follow the URL paths the Vue template produces:
      - Template assets  → bare filename, e.g. "testing.png"
      - Evidence files   → "evidence/{project_id}/{filename}"
    """
    resources: dict[str, bytes] = {}

    # Template-specific image assets (logo, background, etc.)
    if template.assets_dir and template.assets_dir.is_dir():
        for f in template.assets_dir.iterdir():
            if f.is_file():
                resources[f.name] = f.read_bytes()

    # Evidence files fetched during the generate step
    for path in collect_paths(report_json):
        local = local_path(path)
        if local.exists():
            resources[path] = local.read_bytes()

    return resources
