"""WSGI entry point — used by gunicorn / uWSGI in production."""
import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

_app = create_app()

# When APPLICATION_ROOT is set (e.g. /ghostbadger), mount the app at that
# subpath so it can be served behind a reverse proxy at a non-root URL.
# DispatcherMiddleware sets SCRIPT_NAME in the WSGI environ, which Flask
# uses for url_for() and session cookie path automatically.
_root = os.environ.get("APPLICATION_ROOT", "").rstrip("/")
if _root:
    from werkzeug.middleware.dispatcher import DispatcherMiddleware
    from werkzeug.wrappers import Response

    application = DispatcherMiddleware(
        Response("Not Found", status=404),
        {_root: _app},
    )
else:
    application = _app
