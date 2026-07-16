from flask import current_app, flash, redirect, render_template, request, session, url_for

from ..auth import clear_token, validate_token_format
from ..ghostwriter import GhostwriterClient, GhostwriterError, parse_expires
from . import bp


def _store_token(token: str, exp) -> None:
    session.permanent = True
    session["gw_token"] = token
    if exp is not None:
        session["gw_token_exp"] = int(exp) if not isinstance(exp, int) else exp


@bp.route("/", methods=["GET", "POST"])
def index():
    if session.get("gw_token"):
        return redirect(url_for("dashboard.index"))

    error = None
    mode = "password"  # which form tab to show on error

    if request.method == "POST":
        gw_url      = current_app.config.get("GHOSTWRITER_URL", "").rstrip("/")
        verify_ssl  = current_app.config["GHOSTWRITER_VERIFY_SSL"]
        cf_id       = current_app.config["GHOSTWRITER_CF_CLIENT_ID"]
        cf_secret   = current_app.config["GHOSTWRITER_CF_CLIENT_SECRET"]

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        token    = request.form.get("token", "").strip()

        if username or password:
            # Username/password login via the Ghostwriter login mutation
            mode = "password"
            if not username or not password:
                error = "Username and password are required."
            elif not gw_url:
                error = "GHOSTWRITER_URL is not configured on this server."
            else:
                try:
                    tok, exp = GhostwriterClient.login(
                        base_url=gw_url,
                        username=username,
                        password=password,
                        verify_ssl=verify_ssl,
                        cf_client_id=cf_id,
                        cf_client_secret=cf_secret,
                    )
                    _store_token(tok, exp)
                    flash("Connected to Ghostwriter successfully.", "success")
                    return redirect(url_for("dashboard.index"))
                except GhostwriterError as exc:
                    error = str(exc)
        else:
            # Paste an API token (gwat_... since Ghostwriter 7.0, or a JWT).
            # The token is opaque, so expiry must come from the server: whoami
            # both proves the token works and reports when it expires.
            mode = "token"
            token = token.strip()
            valid, error = validate_token_format(token)
            if valid and not gw_url:
                error = "GHOSTWRITER_URL is not configured on this server."
            elif valid:
                try:
                    client = GhostwriterClient(
                        base_url=gw_url,
                        token=token,
                        verify_ssl=verify_ssl,
                        cf_client_id=cf_id,
                        cf_client_secret=cf_secret,
                    )
                    info = client.whoami()
                    _store_token(token, parse_expires(info.get("expires")))
                    username = info.get("username", "")
                    flash(f"Connected to Ghostwriter as {username}." if username
                          else "Connected to Ghostwriter successfully.", "success")
                    return redirect(url_for("dashboard.index"))
                except GhostwriterError as exc:
                    error = str(exc)

    gw_url = current_app.config.get("GHOSTWRITER_URL", "").rstrip("/")
    token_create_url = f"{gw_url}/api/token/create" if gw_url else None
    return render_template("onboarding/index.html", error=error, mode=mode, token_create_url=token_create_url)


@bp.route("/logout")
def logout():
    clear_token()
    flash("Session cleared.", "info")
    return redirect(url_for("onboarding.index"))
