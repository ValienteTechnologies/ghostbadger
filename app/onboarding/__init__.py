from flask import Blueprint

bp = Blueprint("onboarding", __name__, url_prefix="/")

from . import routes  # noqa: E402, F401
