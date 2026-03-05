import base64
import io
import json as _json
import logging
import queue
import threading
import time
import uuid

import pikepdf

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
from ..vaultwarden import VaultwardenError, get_vw_client, is_vault_connected, is_vaultwarden_configured
from . import bp

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
        vaultwarden_configured=is_vaultwarden_configured(current_app),
        vault_connected=is_vault_connected(),
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


# ── Combined view endpoint ─────────────────────────────────────────────────────

@bp.route("/api/report/<int:report_id>/view", methods=["POST"])
@csrf.exempt
@require_token
def view_report_pdf(report_id: int):
    template_name = session.get("selected_template")
    if not template_name:
        return jsonify({"error": "No template selected."}), 400

    templates = {t.name: t for t in get_available_templates()}
    template = templates.get(template_name)
    if not template:
        return jsonify({"error": f"Template '{template_name}' not found."}), 400

    # Capture the Ghostwriter URL + token while we're still in request context
    gw_url   = current_app.config["GHOSTWRITER_URL"]
    gw_token = session["gw_token"]

    job_id = str(uuid.uuid4())
    _render_jobs[job_id] = {"q": queue.Queue(), "pdf": None, "error": None, "done": False}

    threading.Thread(
        target=_run_view,
        args=(job_id, report_id, template, gw_url, gw_token),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id}), 202


def _run_view(job_id: str, report_id: int, template, gw_url: str, gw_token: str) -> None:
    job = _render_jobs[job_id]
    q   = job["q"]
    t0  = time.monotonic()

    def emit(event: str, data: dict) -> None:
        q.put((event, data))

    try:
        # ── Stage 1: Generate report JSON ─────────────────────────
        emit("stage", {"stage": "generate", "label": "Fetching report data…"})

        client = GhostwriterClient(base_url=gw_url, token=gw_token)
        raw_b64     = client.generate_report(report_id)
        decoded     = base64.b64decode(raw_b64).decode("utf-8")
        report_json = _json.loads(decoded)

        # ── Stage 2: Evidence ──────────────────────────────────────
        emit("stage", {"stage": "evidence", "label": "Fetching evidence…"})

        evidence_results = sync_evidence(report_json, client)
        fetched = sum(1 for ok in evidence_results.values() if ok)
        failed  = sum(1 for ok in evidence_results.values() if not ok)
        emit("evidence", {"fetched": fetched, "failed": failed})

        # ── Stage 3: Chromium ──────────────────────────────────────
        emit("stage", {"stage": "chromium", "label": "Rendering template…"})

        if not BUNDLE.exists():
            raise FileNotFoundError(f"Vue bundle not found at {BUNDLE}")

        vue_data      = make_vue_data(report_json)
        template_html = template.html_path.read_text("utf-8")
        css           = template.css_path.read_text("utf-8") if template.css_path.exists() else None
        bundle_js     = BUNDLE.read_text("utf-8")
        resources     = build(template, report_json)

        html = render_to_html(vue_data, template_html, css, bundle_js, "tr", resources)

        # ── Stage 4: WeasyPrint ────────────────────────────────────
        emit("stage", {"stage": "weasyprint", "label": "Generating PDF…"})

        class _WpHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
                msg = record.getMessage()
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


@bp.route("/api/render/<job_id>/pdf/download", methods=["POST"])
@csrf.exempt
@require_token
def download_pdf(job_id: str):
    job = _render_jobs.get(job_id)
    if not job or not job["done"]:
        return jsonify({"error": "Not ready"}), 404
    if job["error"] or not job["pdf"]:
        return jsonify({"error": job.get("error", "Render failed")}), 500

    data = request.get_json(silent=True) or {}
    owner_pw = data.get("owner_password", "").strip()
    user_pw  = data.get("user_password", "").strip()
    filename = data.get("filename", "report.pdf").strip() or "report.pdf"

    if not owner_pw or not user_pw:
        return jsonify({"error": "Both owner and user passwords are required."}), 400

    src = pikepdf.open(io.BytesIO(job["pdf"]))
    out = io.BytesIO()
    src.save(
        out,
        encryption=pikepdf.Encryption(
            owner=owner_pw,
            user=user_pw,
            R=6,
        ),
    )
    out.seek(0)

    return Response(
        out.read(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Vaultwarden routes ─────────────────────────────────────────────────────────

@bp.route("/api/vault/connect", methods=["POST"])
@csrf.exempt
@require_token
def vault_connect():
    if not is_vaultwarden_configured(current_app):
        return jsonify({"error": "Vaultwarden not configured on this server."}), 503
    data          = request.get_json(silent=True) or {}
    client_id     = data.get("client_id", "").strip()
    client_secret = data.get("client_secret", "").strip()
    master_pw     = data.get("master_password", "").strip()
    if not client_id or not client_secret or not master_pw:
        return jsonify({"error": "client_id, client_secret, and master_password are required."}), 400
    try:
        from ..vaultwarden import VaultwardenClient
        client = VaultwardenClient(
            server_url      = current_app.config["VAULTWARDEN_URL"],
            client_id       = client_id,
            client_secret   = client_secret,
            master_password = master_pw,
            org_id          = current_app.config["VAULTWARDEN_ORG_ID"],
            collection_id   = current_app.config["VAULTWARDEN_COLLECTION_ID"],
        )
        session_key = client.connect()
        # Store in Flask session (cleared on logout / JWT expiry)
        session["vw_client_id"]     = client_id
        session["vw_client_secret"] = client_secret
        session["vw_master_password"] = master_pw
        session["vw_session_key"]   = session_key
        return jsonify({"status": "unlocked"})
    except VaultwardenError as exc:
        return jsonify({"error": str(exc)}), 502


@bp.route("/api/vault/status")
@require_token
def vault_status():
    configured = is_vaultwarden_configured(current_app)
    if not configured:
        return jsonify({"configured": False, "status": "unconfigured", "server": ""})
    if not is_vault_connected():
        return jsonify({"configured": True, "status": "unauthenticated", "server": current_app.config["VAULTWARDEN_URL"]})
    try:
        data = get_vw_client().status()
        return jsonify({
            "configured": True,
            "status":     data.get("status", "unknown"),
            "server":     data.get("serverUrl", current_app.config["VAULTWARDEN_URL"]),
        })
    except VaultwardenError as exc:
        return jsonify({"configured": True, "status": "error", "error": str(exc)}), 502


@bp.route("/api/vault/credential", methods=["POST"])
@csrf.exempt
@require_token
def vault_credential():
    if not is_vaultwarden_configured(current_app):
        return jsonify({"error": "Vaultwarden not configured."}), 503
    if not is_vault_connected():
        return jsonify({"error": "Not connected to Vaultwarden. Connect first."}), 401
    data = request.get_json(silent=True) or {}
    name     = data.get("name", "").strip()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not name or not password:
        return jsonify({"error": "name and password are required."}), 400
    try:
        item = get_vw_client().add_login(
            name=name,
            username=username,
            password=password,
            url=data.get("url") or None,
            notes=data.get("notes") or None,
        )
        return jsonify(item)
    except VaultwardenError as exc:
        return jsonify({"error": str(exc)}), 502


@bp.route("/api/vault/send", methods=["POST"])
@csrf.exempt
@require_token
def vault_send():
    if not is_vaultwarden_configured(current_app):
        return jsonify({"error": "Vaultwarden not configured."}), 503
    if not is_vault_connected():
        return jsonify({"error": "Not connected to Vaultwarden. Connect first."}), 401
    data = request.get_json(silent=True) or {}
    name        = data.get("name", "").strip()
    text        = data.get("text", "").strip()
    delete_days = int(data.get("delete_days", 7))
    password    = data.get("password") or None
    if not name or not text:
        return jsonify({"error": "name and text are required."}), 400
    try:
        send = get_vw_client().create_text_send(
            name=name,
            text=text,
            delete_days=delete_days,
            password=password,
        )
        return jsonify(send)
    except VaultwardenError as exc:
        return jsonify({"error": str(exc)}), 502
