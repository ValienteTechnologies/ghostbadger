import base64
import json
import re
from functools import wraps

from flask import redirect, session, url_for


_JWT_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


def validate_jwt_format(token: str) -> tuple[bool, str]:
    """Return (is_valid, error_message). Checks structure only — not signature."""
    token = token.strip()
    if not token:
        return False, "Token cannot be empty."
    if not _JWT_RE.match(token):
        return False, "Token does not appear to be a valid JWT (expected header.payload.signature)."

    try:
        header_b64 = token.split(".")[0]
        # Add padding if needed
        header_b64 += "=" * (-len(header_b64) % 4)
        header = json.loads(base64.urlsafe_b64decode(header_b64))
        if header.get("typ", "").upper() != "JWT":
            return False, "Token header does not indicate a JWT type."
    except Exception:
        return False, "Token header could not be decoded."

    return True, ""


def require_token(f):
    """Redirect to onboarding if no Ghostwriter token is stored in the session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("gw_token"):
            return redirect(url_for("onboarding.index"))
        return f(*args, **kwargs)
    return decorated


def clear_token():
    session.pop("gw_token", None)
