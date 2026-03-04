import base64
import json
import re
import time
from functools import wraps

from flask import redirect, session, url_for


_JWT_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


def validate_jwt_format(token: str) -> tuple[bool, str, int | None]:
    """Return (is_valid, error_message, exp). Checks structure only — not signature.
    exp is the Unix timestamp from the payload, or None if absent."""
    token = token.strip()
    if not token:
        return False, "Token cannot be empty.", None
    if not _JWT_RE.match(token):
        return False, "Token does not appear to be a valid JWT (expected header.payload.signature).", None

    parts = token.split(".")

    try:
        header_b64 = parts[0] + "=" * (-len(parts[0]) % 4)
        header = json.loads(base64.urlsafe_b64decode(header_b64))
        if header.get("typ", "").upper() != "JWT":
            return False, "Token header does not indicate a JWT type.", None
    except Exception:
        return False, "Token header could not be decoded.", None

    exp = None
    try:
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")
        if exp is not None and time.time() > exp:
            return False, "Token has already expired.", None
    except Exception:
        pass  # exp stays None — payload exp is optional

    return True, "", exp


def require_token(f):
    """Redirect to onboarding if no token in session or the JWT exp has passed."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("gw_token"):
            return redirect(url_for("onboarding.index"))
        exp = session.get("gw_token_exp")
        if exp is not None and time.time() > exp:
            clear_token()
            return redirect(url_for("onboarding.index"))
        return f(*args, **kwargs)
    return decorated


def clear_token():
    session.pop("gw_token", None)
    session.pop("gw_token_exp", None)
