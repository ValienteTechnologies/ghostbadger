"""WSGI entry point — used by gunicorn / uWSGI in production."""
from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

application = create_app()
