"""Verify health, idempotency and persisted data across Docker Compose recreation."""
import json
import subprocess
import urllib.request
from http.cookiejar import CookieJar
from uuid import uuid4

BASE = "http://127.0.0.1:8080"


def call(opener, method, path, body=None, headers=None):
    req_headers = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data,
                                     headers=req_headers, method=method)
    with opener.open(request, timeout=20) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main():
    plain = urllib.request.build_opener()
    cookies = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(CookieJar())
    )
    status, health = call(plain, "GET", "/health/ready")
    assert status == 200 and health["status"] == "ready"
    status, event = call(plain, "GET", "/api/event")
    assert event["venue"] == "Local a confirmar"

    payload = {
        "contact_name": "Convidado CI",
        "attending": True,
        "participants": [
            {"name": "Convidado CI", "kind": "OVER_12", "age_years": None},
            {"name": "Criança CI", "kind": "CHILD", "age_years": 5},
        ],
    }
    headers = {"Idempotency-Key": str(uuid4())}
    created_status, first = call(plain, "POST", "/api/rsvps", payload, headers)
    repeated_status, repeated = call(plain, "POST", "/api/rsvps", payload, headers)
    assert created_status == 201 and repeated_status == 200
    assert first == repeated

    _, prelogin = call(cookies, "GET", "/api/auth/csrf")
    login_status, logged = call(
        cookies, "POST", "/api/auth/login",
        {"username": "organizador", "password": "ci-only-smoke-pass-1234"},
        {"X-CSRF-Token": prelogin["csrf_token"]},
    )
    assert login_status == 200
    token = logged["csrf_token"]
    _, report = call(cookies, "GET", "/api/admin/dashboard")
    assert report["counts"]["total"] == 2
    assert report["counts"]["buffet"] == 1
    assert report["counts"]["children_0_12"] == 1
    settings_status, _ = call(cookies, "PUT", "/api/admin/settings",
                              {"venue": "Salão de testes CI", "edit_deadline_utc": None},
                              {"X-CSRF-Token": token})
    assert settings_status == 200

    # Force-recreate BOTH services. Named MySQL volume must survive.
    subprocess.run(["docker", "compose", "up", "-d", "--force-recreate", "--wait"],
                   check=True)
    _, restored = call(plain, "GET", "/api/rsvps/" + first["id"],
                       headers={"Authorization": "Bearer " + first["edit_token"]})
    assert restored["contact_name"] == "Convidado CI"
    assert restored["revision"] == 1
    assert len(restored["participants"]) == 2
    _, new_event = call(plain, "GET", "/api/event")
    assert new_event["venue"] == "Salão de testes CI"
    _, new_summary = call(cookies, "GET", "/api/admin/dashboard")
    assert new_summary["counts"] == report["counts"]
    print("PASS: idempotency, RSVP token, MySQL volume and event settings survive recreation.")


if __name__ == "__main__":
    main()
