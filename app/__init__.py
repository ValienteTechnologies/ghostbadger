import os

from flask import Flask

from .config import config
from .extensions import csrf


def create_app(config_name: str | None = None) -> Flask:
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Extensions
    csrf.init_app(app)

    # Blueprints
    from .onboarding import bp as onboarding_bp
    app.register_blueprint(onboarding_bp)

    from .dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    return app
