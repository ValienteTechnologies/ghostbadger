import base64
import json

from flask import current_app, jsonify, render_template, session

from ..auth import require_token
from ..extensions import csrf
from ..ghostwriter import GhostwriterClient, GhostwriterError
from . import bp


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
    return render_template("dashboard/index.html", projects=projects, error=error)


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
        raw_b64 = _client().generate_report(report_id)
        decoded = base64.b64decode(raw_b64).decode("utf-8")
        report_json = json.loads(decoded)
        return jsonify({"data": report_json})
    except GhostwriterError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:
        return jsonify({"error": f"Failed to decode report data: {exc}"}), 500
