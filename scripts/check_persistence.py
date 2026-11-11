"""CI-only: verify private-invitation RSVP survives Docker Compose recreation.

Mutates disposable test data and recreates containers. Never run on production.
"""
import json
import os
import subprocess
import urllib.request
from urllib.error import HTTPError
from urllib.parse import urlsplit
from http.cookiejar import CookieJar
from uuid import uuid4

BASE = "http://127.0.0.1:8080"


def call(opener, method, path, body=None, headers=None):
    req_headers = dict(headers or {})
    data = None
    if isinstance(body, bytes):
        data = body
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        BASE + path, data=data, headers=req_headers, method=method)
    with opener.open(request, timeout=20) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("BLOQUEADO: este teste recria serviços e escreve apenas em CI descartável.")

    plain = urllib.request.build_opener()
    cookies = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(CookieJar())
    )
    status, health = call(plain, "GET", "/health/ready")
    assert status == 200 and health["status"] == "ready"
    status, event = call(plain, "GET", "/api/event")
    assert status == 200 and event["venue"] == "Local a confirmar"

    payload = {
        "contact_name": "Convidado CI",
        "attending": True,
        "participants": [
            {"name": "Convidado CI", "kind": "OVER_12", "age_years": None},
            {"name": "Criança CI", "kind": "CHILD", "age_years": 5},
        ],
    }

    # Even an otherwise well-formed anonymous RSVP must be refused in the
    # production image, before creating a family or changing buffet counts.
    try:
        call(plain, "POST", "/api/rsvps", payload,
             {"Idempotency-Key": str(uuid4())})
    except HTTPError as exc:
        try:
            assert exc.code == 403
        finally:
            exc.close()
    else:
        raise AssertionError("RSVP anônimo foi aceito pela imagem de produção.")

    _, prelogin = call(cookies, "GET", "/api/auth/csrf")
    login_status, logged = call(
        cookies, "POST", "/api/auth/login",
        {"username": "organizador", "password": "ci-only-smoke-pass-1234"},
        {"X-CSRF-Token": prelogin["csrf_token"]},
    )
    assert login_status == 200
    csrf = logged["csrf_token"]

    # Create ONE fictitious preregistered family using the actual organizer
    # API, then retrieve its bearer token via the privileged one-family link.
    family_key = "ci-smoke-" + uuid4().hex[:16]
    csv_payload = (
        "familia;responsavel;telefone;adultos;criancas_0_5;criancas_6_12\r\n"
        + family_key + ";Convidado CI;;1;1;0\r\n"
    ).encode("utf-8")
    imported_status, imported = call(
        cookies, "POST", "/api/admin/guest-list-import", csv_payload,
        {"Content-Type": "text/csv", "X-CSRF-Token": csrf},
    )
    assert imported_status == 200 and imported["imported"] == 1
    _, overview = call(cookies, "GET", "/api/admin/invitations")
    matching = [x for x in overview["families"] if x["key"] == family_key]
    assert len(matching) == 1
    invited_id = matching[0]["id"]
    _, link = call(cookies, "GET", "/api/admin/invitations/" + invited_id + "/link")
    invite_url = urlsplit(link["url"])
    assert invite_url.path == "/convite"
    fragment = invite_url.fragment.split(".")
    assert len(fragment) == 2 and fragment[0] == invited_id and len(fragment[1]) == 64
    bearer = {"Authorization": "Bearer " + fragment[1]}

    created_status, first = call(
        plain, "POST", "/api/invitations/" + invited_id + "/response",
        payload, bearer,
    )
    repeated_status, repeated = call(
        plain, "POST", "/api/invitations/" + invited_id + "/response",
        payload, bearer,
    )
    assert created_status == 200 and repeated_status == 200 and first == repeated

    _, report = call(cookies, "GET", "/api/admin/dashboard")
    assert report["counts"]["total"] == 2
    assert report["counts"]["buffet"] == 1
    assert report["counts"]["children_0_12"] == 1
    settings_status, _ = call(
        cookies, "PUT", "/api/admin/settings",
        {"venue": "Salão de testes CI", "edit_deadline_utc": None},
        {"X-CSRF-Token": csrf},
    )
    assert settings_status == 200

    # CI-only: recreate BOTH disposable services. The named MySQL volume
    # must survive. Never run this against a real host or family records.
    subprocess.run(
        ["docker", "compose", "up", "-d", "--force-recreate", "--wait"],
        check=True,
    )
    _, own = call(plain, "GET", "/api/invitations/" + invited_id, headers=bearer)
    assert own["responded"] is True and own["receipt"] == first
    _, restored = call(
        plain, "GET", "/api/rsvps/" + first["id"],
        headers={"Authorization": "Bearer " + first["edit_token"]},
    )
    assert restored["contact_name"] == "Convidado CI"
    assert restored["revision"] == 1
    assert len(restored["participants"]) == 2
    _, new_event = call(plain, "GET", "/api/event")
    assert new_event["venue"] == "Salão de testes CI"
    _, new_summary = call(cookies, "GET", "/api/admin/dashboard")
    assert new_summary["counts"] == report["counts"]
    print("PASS: convite individual, idempotência, bloqueio anônimo, MySQL e configuração persistidos.")


if __name__ == "__main__":
    main()
