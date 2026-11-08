"""Prepare disposable CI credentials; NEVER execute against a real deployment."""
import os
from pathlib import Path
import secrets
from werkzeug.security import generate_password_hash

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Este script só deve executar no GitHub Actions.")
target = Path(".env")
if target.exists():
    raise SystemExit("Arquivo .env já existe; não será sobrescrito.")

values = {
    "MYSQL_DATABASE": "isadora_ci_smoke",
    "MYSQL_USER": "isadora_ci",
    "MYSQL_PASSWORD": secrets.token_urlsafe(30),
    "MYSQL_ROOT_PASSWORD": secrets.token_urlsafe(30),
    "TOKEN_SECRET": secrets.token_urlsafe(48),
    "SESSION_SECRET": secrets.token_urlsafe(48),
    "ORGANIZER_USERNAME": "organizador",
    "APP_PUBLIC_URL": "http://127.0.0.1:8080",
}
lines = [key + "=" + value for key, value in values.items()]
# Docker Compose .env: single quotes protect the dollar characters of scrypt hash.
lines.append("ORGANIZER_PASSWORD_HASH='" +
             generate_password_hash("ci-only-smoke-pass-1234") + "'")
target.write_text("\n".join(lines) + "\n", encoding="utf-8")
target.chmod(0o600)
print("Prepared disposable Docker Compose smoke-test environment.")
