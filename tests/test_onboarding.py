import pytest

from app import create_app


@pytest.fixture()
def app():
    app = create_app("testing")
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def test_onboarding_page_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Ghostwriter JWT Token" in resp.data


def test_invalid_token_rejected(client):
    resp = client.post("/", data={"token": "not-a-jwt", "csrf_token": "test"})
    assert resp.status_code == 200
    assert b"valid JWT" in resp.data


def test_valid_token_redirects(client):
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    resp = client.post("/", data={"token": token, "csrf_token": "test"})
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]


def test_dashboard_requires_token(client):
    resp = client.get("/dashboard/")
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_logout_clears_session(client):
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    client.post("/", data={"token": token, "csrf_token": "test"})
    resp = client.get("/logout")
    assert resp.status_code == 302
    # After logout, dashboard should redirect back to onboarding
    resp2 = client.get("/dashboard/")
    assert resp2.status_code == 302
