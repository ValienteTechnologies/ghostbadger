from flask import current_app, flash, redirect, render_template, request, session, url_for

from ..auth import clear_token, validate_jwt_format
from . import bp


@bp.route("/", methods=["GET", "POST"])
def index():
    if session.get("gw_token"):
        return redirect(url_for("dashboard.index"))

    error = None
    if request.method == "POST":
        token = request.form.get("token", "").strip()
        valid, error, exp = validate_jwt_format(token)
        if valid:
            session.permanent = True
            session["gw_token"] = token
            if exp is not None:
                session["gw_token_exp"] = exp
            flash("Connected to Ghostwriter successfully.", "success")
            return redirect(url_for("dashboard.index"))

    gw_url = current_app.config.get("GHOSTWRITER_URL", "").rstrip("/")
    token_create_url = f"{gw_url}/api/token/create" if gw_url else None
    return render_template("onboarding/index.html", error=error, token_create_url=token_create_url)


@bp.route("/logout")
def logout():
    clear_token()
    flash("Session cleared.", "info")
    return redirect(url_for("onboarding.index"))
