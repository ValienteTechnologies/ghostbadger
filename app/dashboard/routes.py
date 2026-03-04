import base64
import json as _json
import logging
import queue
import threading
import time
import uuid

from flask import Response, current_app, jsonify, render_template, request, session, stream_with_context

from ..auth import require_token
from ..extensions import csrf
from ..ghostwriter import GhostwriterClient, GhostwriterError
from ..reporting import get_available_templates
from ..reporting.evidence import sync_evidence
from ..rendering.chromium import render_to_html
from ..rendering.pipeline import BUNDLE, make_vue_data
from ..rendering.resources import build
from ..rendering.weasyprint import render_to_pdf
from . import bp

_report_cache: dict[int, dict] = {}
_render_jobs:  dict[str, dict] = {}


def _client() -> GhostwriterClient:
    return GhostwriterClient(
        base_url=current_app.config["GHOSTWRITER_URL"],
        token=session["gw_token"],
    )


@bp.route("/")
@require_token
def index():
    client = _client()
    projects, error = [], None
    try:
        projects = client.get_recent_projects(limit=4)
    except GhostwriterError as exc:
        error = str(exc)
    templates = get_available_templates()
    selected = session.get("selected_template") or (templates[0].name if templates else None)
    return render_template(
        "dashboard/index.html",
        projects=projects,
        error=error,
        templates=templates,
        selected_template=selected,
    )


@bp.route("/api/template/select", methods=["POST"])
@csrf.exempt
@require_token
def select_template():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    valid = {t.name for t in get_available_templates()}
    if name not in valid:
        return jsonify({"error": "Unknown template"}), 400
    session["selected_template"] = name
    return jsonify({"selected": name})


@bp.route("/api/project/<int:project_id>/reports")
@require_token
def project_reports(project_id: int):
    try:
        reports = _client().get_project_reports(project_id)
        return jsonify({"reports": reports})
    except GhostwriterError as exc:
        return jsonify({"error": str(exc)}), 502


@bp.route("/api/report/<int:report_id>/generate", methods=["POST"])
@csrf.exempt
@require_token
def generate_report(report_id: int):
    try:
        client = _client()
        raw_b64 = client.generate_report(report_id)
        decoded = base64.b64decode(raw_b64).decode("utf-8")
        report_json = _json.loads(decoded)

        evidence_results = sync_evidence(report_json, client)
        fetched = sum(1 for ok in evidence_results.values() if ok)
        failed  = sum(1 for ok in evidence_results.values() if not ok)

        _report_cache[report_id] = report_json

        return jsonify({
            "data": report_json,
            "evidence": {"fetched": fetched, "failed": failed},
        })
    except GhostwriterError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:
        return jsonify({"error": f"Failed to decode report data: {exc}"}), 500


# ── Async render endpoints ─────────────────────────────────────────────────────

@bp.route("/api/report/<int:report_id>/render", methods=["POST"])
@csrf.exempt
@require_token
def render_report_pdf(report_id: int):
    if report_id not in _report_cache:
        return jsonify({"error": "Generate the report first."}), 400

    template_name = session.get("selected_template")
    if not template_name:
        return jsonify({"error": "No template selected."}), 400

    templates = {t.name: t for t in get_available_templates()}
    template = templates.get(template_name)
    if not template:
        return jsonify({"error": f"Template '{template_name}' not found."}), 400

    job_id = str(uuid.uuid4())
    _render_jobs[job_id] = {"q": queue.Queue(), "pdf": None, "error": None, "done": False}

    threading.Thread(
        target=_run_render,
        args=(job_id, _report_cache[report_id], template),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id}), 202


def _run_render(job_id: str, report_json: dict, template) -> None:
    job = _render_jobs[job_id]
    q   = job["q"]
    t0  = time.monotonic()

    def emit(event: str, data: dict) -> None:
        q.put((event, data))

    try:
        # ── Stage 1: Chromium ──────────────────────────────────────
        emit("stage", {"stage": "chromium", "label": "Rendering template…"})

        if not BUNDLE.exists():
            raise FileNotFoundError(f"Vue bundle not found at {BUNDLE}")

        vue_data      = make_vue_data(report_json)
        template_html = template.html_path.read_text("utf-8")
        css           = template.css_path.read_text("utf-8") if template.css_path.exists() else None
        bundle_js     = BUNDLE.read_text("utf-8")
        resources     = build(template, report_json)

        html = render_to_html(vue_data, template_html, css, bundle_js, "tr", resources)

        # ── Stage 2: WeasyPrint ────────────────────────────────────
        emit("stage", {"stage": "weasyprint", "label": "Generating PDF…"})

        class _WpHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
                msg = record.getMessage()
                # Skip CSS compatibility noise: "Ignored `xxx` at y:z, ..."
                if msg.startswith("Ignored ") and " at " in msg:
                    return
                level = "error" if record.levelno >= logging.ERROR else "warning"
                q.put(("message", {"level": level, "message": msg}))

        wp_logger = logging.getLogger("weasyprint")
        handler   = _WpHandler(logging.WARNING)
        wp_logger.addHandler(handler)
        try:
            pdf = render_to_pdf(html, resources)
        finally:
            wp_logger.removeHandler(handler)

        elapsed = round(time.monotonic() - t0, 1)
        job["pdf"]  = pdf
        job["done"] = True
        emit("done", {"success": True, "elapsed": elapsed})

    except Exception as exc:
        elapsed = round(time.monotonic() - t0, 1)
        job["error"] = str(exc)
        job["done"]  = True
        emit("render_error", {"message": str(exc)})
        emit("done", {"success": False, "elapsed": elapsed})


@bp.route("/api/render/<job_id>/stream")
@require_token
def render_stream(job_id: str):
    job = _render_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404

    def generate():
        q = job["q"]
        while True:
            try:
                event, data = q.get(timeout=90)
            except queue.Empty:
                yield ": heartbeat\n\n"
                continue
            yield f"event: {event}\ndata: {_json.dumps(data)}\n\n"
            if event == "done":
                break

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.route("/api/render/<job_id>/pdf")
@require_token
def render_pdf(job_id: str):
    job = _render_jobs.get(job_id)
    if not job or not job["done"]:
        return jsonify({"error": "Not ready"}), 404
    if job["error"] or not job["pdf"]:
        return jsonify({"error": job.get("error", "Render failed")}), 500
    return Response(
        job["pdf"],
        mimetype="application/pdf",
        headers={"Content-Disposition": "inline; filename=report.pdf"},
    )
