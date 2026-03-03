from flask import render_template

from ..auth import require_token
from . import bp


@bp.route("/")
@require_token
def index():
    return render_template("dashboard/index.html")
