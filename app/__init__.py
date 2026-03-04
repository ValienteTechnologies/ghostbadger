import os
from datetime import datetime, timedelta, timezone

from flask import Flask
from flask.sessions import SecureCookieSessionInterface

from .config import config
from .extensions import csrf


class _JwtAwareSessionInterface(SecureCookieSessionInterface):
    """Set the session cookie to expire at the JWT exp, falling back to the app default."""

    def get_expiration_time(self, app, session):
        exp = session.get("gw_token_exp")
        if exp and session.permanent:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
        return super().get_expiration_time(app, session)

    def save_session(self, app, session, response):
        exp = session.get("gw_token_exp")
        if not (exp and session.permanent):
            return super().save_session(app, session, response)
        # Flask's save_session sets max_age from app.permanent_session_lifetime,
        # ignoring get_expiration_time. Temporarily override it so both
        # max_age and expires reflect the JWT exp.
        delta = max(
            datetime.fromtimestamp(exp, tz=timezone.utc) - datetime.now(timezone.utc),
            timedelta(0),
        )
        original = app.permanent_session_lifetime
        app.permanent_session_lifetime = delta
        try:
            super().save_session(app, session, response)
        finally:
            app.permanent_session_lifetime = original


def create_app(config_name: str | None = None) -> Flask:
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    app = Flask(__name__)
    app.config.from_object(config[config_name])
    app.session_interface = _JwtAwareSessionInterface()

    # Extensions
    csrf.init_app(app)

    # Blueprints
    from .onboarding import bp as onboarding_bp
    app.register_blueprint(onboarding_bp)

    from .dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    return app
