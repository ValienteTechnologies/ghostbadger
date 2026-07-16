import pytest

from app import create_app
from app.ghostwriter import GhostwriterClient, GhostwriterError, parse_expires

GWAT_TOKEN = "gwat_2b51d6f6718928a0_DVJbHBPMDOZABCHhzvxeh1OfPfXmWNOjswVUaP5_uWE"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"


@pytest.fixture()
def app():
    app = create_app("testing")
    app.config["GHOSTWRITER_URL"] = "http://ghostwriter.test"
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def whoami_ok(monkeypatch):
    monkeypatch.setattr(
        GhostwriterClient,
        "whoami",
        lambda self: {"username": "tester", "role": "manager",
                      "expires": "2027-01-01 00:00:00+00:00"},
    )


def test_onboarding_page_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Ghostwriter API Token" in resp.data


def test_invalid_token_rejected(client):
    resp = client.post("/", data={"token": "not-a-token", "csrf_token": "test"})
    assert resp.status_code == 200
    assert b"does not look like a Ghostwriter API token" in resp.data


def test_gwat_token_validated_via_whoami(client, whoami_ok):
    resp = client.post("/", data={"token": GWAT_TOKEN, "csrf_token": "test"})
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]


def test_jwt_token_still_accepted(client, whoami_ok):
    resp = client.post("/", data={"token": JWT_TOKEN, "csrf_token": "test"})
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]


def test_rejected_token_shows_server_error(client, monkeypatch):
    def _raise(self):
        raise GhostwriterError("Ghostwriter rejected the token.")
    monkeypatch.setattr(GhostwriterClient, "whoami", _raise)
    resp = client.post("/", data={"token": GWAT_TOKEN, "csrf_token": "test"})
    assert resp.status_code == 200
    assert b"Ghostwriter rejected the token" in resp.data


def test_token_without_gw_url_configured(client, app):
    app.config["GHOSTWRITER_URL"] = ""
    resp = client.post("/", data={"token": GWAT_TOKEN, "csrf_token": "test"})
    assert resp.status_code == 200
    assert b"GHOSTWRITER_URL is not configured" in resp.data


def test_token_create_link_uses_public_url(client, app):
    app.config["GHOSTWRITER_PUBLIC_URL"] = "https://gw.public.example"
    resp = client.get("/")
    assert b"https://gw.public.example/api/token/create" in resp.data


def test_dashboard_requires_token(client):
    resp = client.get("/dashboard/")
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_logout_clears_session(client, whoami_ok):
    client.post("/", data={"token": GWAT_TOKEN, "csrf_token": "test"})
    resp = client.get("/logout")
    assert resp.status_code == 302
    # After logout, dashboard should redirect back to onboarding
    resp2 = client.get("/dashboard/")
    assert resp2.status_code == 302


def test_session_cookie_expires_at_token_expiry(client, whoami_ok):
    resp = client.post("/", data={"token": GWAT_TOKEN, "csrf_token": "test"})
    cookie = resp.headers.get("Set-Cookie", "")
    assert "Expires=" in cookie and ("2026" in cookie or "2027" in cookie)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1798761600, 1798761600),                       # login mutation: unix int
        ("1798761600", 1798761600),                     # numeric string
        ("2027-01-01 00:00:00+00:00", 1798761600),      # whoami, API-token path
        ("2027-01-01T00:00:00", 1798761600),            # whoami, JWT path (naive → UTC)
        ("Never", None),
        ("never", None),
        (None, None),
        ("garbage", None),
        ("", None),
    ],
)
def test_parse_expires(value, expected):
    assert parse_expires(value) == expected
