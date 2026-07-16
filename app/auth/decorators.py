import re
import time
from functools import wraps

from flask import jsonify, redirect, request, session, url_for


# Legacy Ghostwriter JWTs (header.payload.signature) — still issued by the
# login mutation and accepted by older Ghostwriter versions.
_JWT_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")

# Ghostwriter 7.x API tokens: gwat_ (user) / gwst_ (service), a 16-char hex
# identifier, then a urlsafe-base64 secret which may itself contain _ and -.
_GW_TOKEN_RE = re.compile(r"^gw[as]t_[0-9a-f]{16}_[A-Za-z0-9_-]{20,}$")


def validate_token_format(token: str) -> tuple[bool, str]:
    """Cheap client-side sanity check for a pasted Ghostwriter token.

    Accepts 7.x API tokens (gwat_/gwst_) and legacy JWTs. This only filters
    obvious garbage — the token is authoritatively validated against the
    Ghostwriter server afterwards."""
    token = token.strip()
    if not token:
        return False, "Token cannot be empty."
    if _GW_TOKEN_RE.match(token) or _JWT_RE.match(token):
        return True, ""
    return False, (
        "Token does not look like a Ghostwriter API token "
        "(expected gwat_... or a JWT)."
    )


def require_token(f):
    """Redirect to onboarding if no token in session or the token expiry has passed.
    API routes (paths containing /api/) receive a JSON 401 instead of a redirect."""
    @wraps(f)
    def decorated(*args, **kwargs):
        missing = not session.get("gw_token")
        if not missing:
            exp = session.get("gw_token_exp")
            if exp is not None and time.time() > exp:
                clear_token()
                missing = True

        if missing:
            if "/api/" in request.path:
                return jsonify({"error": "session_expired"}), 401
            return redirect(url_for("onboarding.index"))
        return f(*args, **kwargs)
    return decorated


def clear_token():
    session.pop("gw_token", None)
    session.pop("gw_token_exp", None)
