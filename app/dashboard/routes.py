import base64
import json

from flask import Response, current_app, jsonify, render_template, request, session

from ..auth import require_token
from ..extensions import csrf
from ..ghostwriter import GhostwriterClient, GhostwriterError
from ..reporting import get_available_templates
from ..reporting.evidence import sync_evidence
from ..rendering import render_report
from . import bp

# In-memory cache of the last generated JSON per report_id.
# Single-user tool: a plain dict is sufficient.
_report_cache: dict[int, dict] = {}


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
        projects = client.get_recent_projects(limit=5)
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
        report_json = json.loads(decoded)

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

    try:
        pdf_bytes = render_report(_report_cache[report_id], template)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="report-{report_id}.pdf"',
            },
        )
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:
        current_app.logger.exception("Rendering failed for report %d", report_id)
        return jsonify({"error": f"Rendering failed: {exc}"}), 500
