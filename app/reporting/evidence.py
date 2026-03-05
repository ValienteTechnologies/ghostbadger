"""Fetch and persist report evidence files from Ghostwriter."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..ghostwriter import GhostwriterClient, GhostwriterError

_EVIDENCE_DIR = Path(__file__).parent / "resources" / "assets" / "_evidence"


def local_path(evidence_path: str) -> Path:
    """Return the local filesystem path for a given evidence path string.

    evidence_path is relative, e.g. 'evidence/2/adminpanel.png'.
    Result: <_EVIDENCE_DIR>/2/adminpanel.png  (strips leading 'evidence/')
    """
    return _EVIDENCE_DIR / Path(evidence_path).relative_to("evidence")


def collect_paths(obj: object) -> set[str]:
    """Recursively find all evidence path strings in the report JSON."""
    paths: set[str] = set()
    if isinstance(obj, dict):
        p = obj.get("path")
        if isinstance(p, str) and p.startswith("evidence/"):
            paths.add(p)
        for v in obj.values():
            paths |= collect_paths(v)
    elif isinstance(obj, list):
        for item in obj:
            paths |= collect_paths(item)
    return paths


def _fetch_and_save(client: GhostwriterClient, path: str) -> tuple[str, bool]:
    dest = local_path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.write_bytes(client.fetch_evidence(path))
        return path, True
    except GhostwriterError:
        return path, False


def sync_evidence(
    report_json: dict,
    client: GhostwriterClient,
    max_workers: int = 6,
) -> dict[str, bool]:
    """Fetch all evidence referenced in report_json and save under _evidence/.

    Returns {evidence_path: success} for every path found.
    Missing files are saved silently; the caller sees False for failures.
    """
    paths = collect_paths(report_json)
    if not paths:
        return {}

    results: dict[str, bool] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_and_save, client, p): p for p in paths}
        for fut in as_completed(futures):
            path, ok = fut.result()
            results[path] = ok

    return results
