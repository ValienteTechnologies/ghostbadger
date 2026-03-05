from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent / "resources" / "templates"
_ASSETS_DIR    = Path(__file__).parent / "resources" / "assets"


@dataclass(frozen=True)
class ReportTemplate:
    name:       str
    html_path:  Path
    css_path:   Path
    assets_dir: Path | None  # None when no per-template asset folder exists


def get_available_templates() -> list[ReportTemplate]:
    """Return every valid reporting template (requires matching .html + .css)."""
    templates: list[ReportTemplate] = []

    for html_file in sorted(_TEMPLATES_DIR.glob("*.html")):
        css_file = html_file.with_suffix(".css")
        if not css_file.exists():
            continue

        name = html_file.stem
        assets = _ASSETS_DIR / name
        templates.append(ReportTemplate(
            name=name,
            html_path=html_file,
            css_path=css_file,
            assets_dir=assets if assets.is_dir() else None,
        ))

    return templates
