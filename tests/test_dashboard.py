import base64
import json
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


def test_generate_report_decodes_base64(auth_client):
    payload = {"client": "Acme", "findings": []}
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()

    with patch("app.dashboard.routes.GhostwriterClient") as MockClient:
        MockClient.return_value.generate_report.return_value = encoded
        resp = auth_client.post("/dashboard/api/report/10/generate")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["client"] == "Acme"


def test_generate_report_gql_error(auth_client):
    with patch("app.dashboard.routes.GhostwriterClient") as MockClient:
        MockClient.return_value.generate_report.side_effect = GhostwriterError("not found")
        resp = auth_client.post("/dashboard/api/report/10/generate")
    assert resp.status_code == 502


def test_generate_report_requires_session(app):
    resp = app.test_client().post("/dashboard/api/report/10/generate")
    assert resp.status_code == 302
