import base64
import json
import queue
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.ghostwriter import GhostwriterError

_VALID_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxIn0"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)

_FAKE_PROJECTS = [
    {
        "id": 1,
        "codename": "Alpha",
        "complete": False,
        "startDate": "2025-01-01",
        "endDate": "2025-03-01",
        "client": {"name": "Acme Corp", "shortName": "Acme"},
    }
]

_FAKE_REPORTS = [{"id": 10, "title": "Final Report", "complete": True, "last_update": "2025-02-01"}]


@pytest.fixture()
def app():
    return create_app("testing")


@pytest.fixture()
def auth_client(app):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["gw_token"] = _VALID_TOKEN
    return client


def test_dashboard_lists_projects(auth_client):
    with patch("app.dashboard.routes.GhostwriterClient") as MockClient:
        MockClient.return_value.get_recent_projects.return_value = _FAKE_PROJECTS
        resp = auth_client.get("/dashboard/")
    assert resp.status_code == 200
    assert b"Alpha" in resp.data


def test_dashboard_shows_gql_error(auth_client):
    with patch("app.dashboard.routes.GhostwriterClient") as MockClient:
        MockClient.return_value.get_recent_projects.side_effect = GhostwriterError("boom")
        resp = auth_client.get("/dashboard/")
    assert resp.status_code == 200
    assert b"boom" in resp.data


def test_project_reports_api(auth_client):
    with patch("app.dashboard.routes.GhostwriterClient") as MockClient:
        MockClient.return_value.get_project_reports.return_value = _FAKE_REPORTS
        resp = auth_client.get("/dashboard/api/project/1/reports")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["reports"][0]["title"] == "Final Report"


def test_project_reports_api_error(auth_client):
    with patch("app.dashboard.routes.GhostwriterClient") as MockClient:
        MockClient.return_value.get_project_reports.side_effect = GhostwriterError("bad token")
        resp = auth_client.get("/dashboard/api/project/1/reports")
    assert resp.status_code == 502


def test_view_report_starts_job(auth_client):
    """POST /view with a selected template returns 202 with a job_id."""
    with auth_client.session_transaction() as sess:
        sess["selected_template"] = "testing"

    with patch("app.dashboard.routes.get_available_templates") as mock_tpl, \
         patch("app.dashboard.routes.threading.Thread"):
        tpl = MagicMock()
        tpl.name = "testing"
        mock_tpl.return_value = [tpl]
        resp = auth_client.post("/dashboard/api/report/10/view")

    assert resp.status_code == 202
    body = resp.get_json()
    assert "job_id" in body


def test_view_report_no_template(auth_client):
    """POST /view without a selected template returns 400."""
    resp = auth_client.post("/dashboard/api/report/10/view")
    assert resp.status_code == 400


def test_api_route_returns_json_401_without_session(app):
    resp = app.test_client().post("/dashboard/api/report/10/view")
    assert resp.status_code == 401
    assert resp.content_type == "application/json"
    assert resp.get_json()["error"] == "session_expired"


def test_non_api_route_redirects_without_session(app):
    resp = app.test_client().get("/dashboard/")
    assert resp.status_code == 302


# ── SSE stream helpers ──────────────────────────────────────────────────────


def _parse_sse(text):
    events = []
    current = {}
    for line in text.splitlines():
        if line.startswith("id:"):
            current["id"] = int(line[3:].strip())
        elif line.startswith("event:"):
            current["event"] = line[6:].strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line[5:].strip())
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


def _make_done_job(events_data):
    events = [(i, name, data) for i, (name, data) in enumerate(events_data)]
    return {
        "q": queue.Queue(),
        "events": events,
        "pdf": b"fake-pdf",
        "pdf_hash": "abc123",
        "error": None,
        "done": True,
        "created_at": 0,
    }


_FAKE_SSE_EVENTS = [
    ("stage", {"stage": "generate", "label": "Fetching report data…"}),
    ("stage", {"stage": "weasyprint", "label": "Generating PDF…"}),
    ("done", {"success": True, "elapsed": 5.0, "pdf_hash": "abc123"}),
]


# ── SSE stream tests ────────────────────────────────────────────────────────


def test_render_stream_streams_all_events(auth_client):
    job_id = "job-all"
    fake_job = _make_done_job(_FAKE_SSE_EVENTS)
    with patch.dict("app.dashboard.routes._render_jobs", {job_id: fake_job}):
        resp = auth_client.get(f"/dashboard/api/render/{job_id}/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.content_type
    events = _parse_sse(resp.data.decode())
    assert len(events) == 3
    assert events[0]["id"] == 0 and events[0]["event"] == "stage"
    assert events[2]["id"] == 2 and events[2]["event"] == "done"


def test_render_stream_replays_from_last_event_id(auth_client):
    job_id = "job-replay"
    fake_job = _make_done_job(_FAKE_SSE_EVENTS)
    with patch.dict("app.dashboard.routes._render_jobs", {job_id: fake_job}):
        resp = auth_client.get(
            f"/dashboard/api/render/{job_id}/stream",
            headers={"Last-Event-Id": "0"},
        )
    assert resp.status_code == 200
    events = _parse_sse(resp.data.decode())
    assert len(events) == 2
    assert events[0]["id"] == 1
    assert events[1]["id"] == 2 and events[1]["event"] == "done"


def test_render_stream_empty_when_fully_caught_up(auth_client):
    job_id = "job-caught-up"
    fake_job = _make_done_job(_FAKE_SSE_EVENTS)
    last_id = len(_FAKE_SSE_EVENTS) - 1
    with patch.dict("app.dashboard.routes._render_jobs", {job_id: fake_job}):
        resp = auth_client.get(
            f"/dashboard/api/render/{job_id}/stream",
            headers={"Last-Event-Id": str(last_id)},
        )
    assert resp.status_code == 200
    assert _parse_sse(resp.data.decode()) == []


def test_render_stream_invalid_last_event_id_starts_from_beginning(auth_client):
    job_id = "job-bad-id"
    fake_job = _make_done_job(_FAKE_SSE_EVENTS)
    with patch.dict("app.dashboard.routes._render_jobs", {job_id: fake_job}):
        resp = auth_client.get(
            f"/dashboard/api/render/{job_id}/stream",
            headers={"Last-Event-Id": "not-a-number"},
        )
    assert resp.status_code == 200
    events = _parse_sse(resp.data.decode())
    assert len(events) == 3
    assert events[0]["id"] == 0


def test_render_stream_unknown_job_returns_404(auth_client):
    resp = auth_client.get("/dashboard/api/render/nonexistent/stream")
    assert resp.status_code == 404
