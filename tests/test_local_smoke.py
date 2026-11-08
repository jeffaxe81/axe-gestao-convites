"""Local acceptance checks are network-restricted and non-mutating."""
import json
from pathlib import Path
import subprocess
import sys
from urllib.request import Request

import pytest

from scripts.check_local import NoRedirect, inspect, local_origin
from tests.e2e.test_organizer import organizer_server


@pytest.mark.parametrize("invalid", [
    "https://127.0.0.1:8080", "http://192.168.1.1:8080",
    "http://example.org:8080", "http://localhost", "http://localhost:0",
    "http://127.0.0.1:8080/admin", "http://localhost:8080?token=secret",
    "http://user:pass@localhost:8080", "http://localhost:abc",
    "http://127.0.0.1:8080/#token", "http://[::1]:8080",
])
def test_local_smoke_rejects_non_local_or_unsafe_url(invalid):
    with pytest.raises(ValueError):
        local_origin(invalid)


def test_local_smoke_blocks_all_redirects():
    redirect = NoRedirect()
    request = Request("http://127.0.0.1:8080/")
    with pytest.raises(RuntimeError, match="Redirecionamento bloqueado"):
        redirect.redirect_request(request, None, 302, "Found", {},
                                  "https://outside.example.org/")


def test_local_smoke_reads_without_modifying_rsvp_data(organizer_server):
    base, store = organizer_server
    before = store.summary()
    result = inspect(base)
    assert result["status"] == "PASS"
    assert result["read_only"] is True
    assert result["rsvp_writes"] == 0
    assert len(result["checks"]) == 8
    assert set(result["checks"].values()) == {"PASS"}
    assert store.summary() == before


def test_local_smoke_cli_uses_only_loopback_and_json_report(organizer_server):
    base, _ = organizer_server
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_local.py"
    completed = subprocess.run([sys.executable, str(script), "--url", base, "--json"],
                               capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "PASS"
    assert result["rsvp_writes"] == 0
    assert "csrf_token" not in completed.stdout
    assert "João" not in completed.stdout
