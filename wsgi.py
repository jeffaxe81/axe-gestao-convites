"""Gunicorn entrypoint. Schema migration runs before the web server in Docker."""
from app import create_app

app = create_app()
