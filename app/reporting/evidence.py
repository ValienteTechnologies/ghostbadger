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


def collect_evidence(obj: object) -> list[dict]:
    """Recursively find all evidence objects in the report JSON.

    An evidence object is any dict with a 'path' starting with 'evidence/'
    and an integer 'id'.
    """
    found: list[dict] = []
    if isinstance(obj, dict):
        p = obj.get("path")
        eid = obj.get("id")
        if isinstance(p, str) and p.startswith("evidence/") and isinstance(eid, int):
            found.append(obj)
        for v in obj.values():
            found.extend(collect_evidence(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_evidence(item))
    return found


def collect_paths(obj: object) -> dict[str, int]:
    """Recursively find all evidence objects in the report JSON.

    Returns a mapping of path -> evidence_id, e.g. {"evidence/2/foo.png": 3}.
    """
    return {ev["path"]: ev["id"] for ev in collect_evidence(obj)}


def _fetch_and_save(client: GhostwriterClient, evidence_id: int, path: str, media_path: Path | None) -> tuple[str, bool]:
    dest = local_path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Try HTTP first (works for remote Ghostwriter instances with proper ALLOWED_HOSTS)
    try:
        dest.write_bytes(client.fetch_evidence(evidence_id, path))
        return path, True
    except GhostwriterError:
        pass

    # Fall back to direct volume read (for local Docker deployments)
    if media_path is not None:
        src = media_path / path
        if src.exists():
            dest.write_bytes(src.read_bytes())
            return path, True

    return path, False


def clear_evidence_cache() -> int:
    """Delete all cached evidence files. Returns the number of files removed."""
    if not _EVIDENCE_DIR.exists():
        return 0
    count = 0
    for f in _EVIDENCE_DIR.rglob("*"):
        if f.is_file():
            f.unlink()
            count += 1
    for d in sorted(_EVIDENCE_DIR.rglob("*"), reverse=True):
        if d.is_dir():
            try:
                d.rmdir()
            except OSError:
                pass
    return count


def sync_evidence(
    report_json: dict,
    client: GhostwriterClient,
    media_path: str = "",
    max_workers: int = 6,
) -> dict[str, bool]:
    """Fetch all evidence referenced in report_json and save under _evidence/.

    media_path: optional filesystem path to Ghostwriter's media volume (fallback
    for local Docker deployments where the volume is mounted into this container).

    Returns {evidence_path: success} for every path found.
    """
    paths = collect_paths(report_json)
    if not paths:
        return {}

    mp = Path(media_path) if media_path else None

    results: dict[str, bool] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_and_save, client, eid, p, mp): p for p, eid in paths.items()}
        for fut in as_completed(futures):
            path, ok = fut.result()
            results[path] = ok

    return results
