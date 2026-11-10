"""Regressões: verificação somente de leitura da versão visual publicada."""
from pathlib import Path

import pytest

from scripts import check_deployed_assets as checker


def fixture_root(tmp_path):
    static = tmp_path / "app" / "static"
    static.mkdir(parents=True)
    files = {}
    for filename in checker.ASSETS:
        data = ("versao-testada-" + filename).encode("utf-8")
        (static / filename).write_bytes(data)
        files[filename] = data
    return tmp_path, files


def test_assets_match_and_only_read_public_paths(monkeypatch, tmp_path):
    root, files = fixture_root(tmp_path)
    calls = []

    def fake_fetch(origin, host, path):
        calls.append((origin, host, path))
        return 200, {}, files[Path(path).name]

    monkeypatch.setattr(checker, "fetch", fake_fetch)
    result = checker.inspect("https://isadora2anos.org", root)
    assert result == {
        "status": "PASS", "read_only": True,
        "checked_assets": 4, "files": list(checker.ASSETS),
        "backend_version_verified": False,
    }
    assert calls == [
        ("https://isadora2anos.org", "isadora2anos.org", "/static/" + name)
        for name in checker.ASSETS
    ]


def test_asset_mismatch_fails_closed(monkeypatch, tmp_path):
    root, files = fixture_root(tmp_path)

    def fake_fetch(_origin, _host, path):
        name = Path(path).name
        return 200, {}, b"outro deploy" if name == "admin.js" else files[name]

    monkeypatch.setattr(checker, "fetch", fake_fetch)
    with pytest.raises(RuntimeError, match="Versão diferente de admin.js"):
        checker.inspect("https://isadora2anos.org", root)


def test_http_error_fails_closed(monkeypatch, tmp_path):
    root, files = fixture_root(tmp_path)

    def fake_fetch(_origin, _host, path):
        name = Path(path).name
        return (404 if name == "guest.js" else 200), {}, files[name]

    monkeypatch.setattr(checker, "fetch", fake_fetch)
    with pytest.raises(RuntimeError, match="guest.js \\(HTTP 404\\)"):
        checker.inspect("https://isadora2anos.org", root)


def test_missing_local_asset_fails_before_comparison(monkeypatch, tmp_path):
    root, _ = fixture_root(tmp_path)
    (root / "app" / "static" / "site.css").unlink()
    monkeypatch.setattr(checker, "fetch", lambda *_args: pytest.fail("Network accessed"))
    with pytest.raises(RuntimeError, match="Arquivo local ausente"):
        checker.inspect("https://isadora2anos.org", root)


def test_symlink_is_rejected(monkeypatch, tmp_path):
    root, _ = fixture_root(tmp_path)
    local = root / "app" / "static" / "site.css"
    outside = tmp_path / "outside"
    outside.write_text("outside")
    local.unlink()
    local.symlink_to(outside)
    monkeypatch.setattr(checker, "fetch", lambda *_args: pytest.fail("Network accessed"))
    with pytest.raises(RuntimeError, match="Arquivo local ausente ou inseguro"):
        checker.inspect("https://isadora2anos.org", root)


@pytest.mark.parametrize("origin", [
    "http://isadora2anos.org", "http://localhost:8080",
    "https://isadora2anos.org/convite", "https://isadora2anos.org/#segredo",
    "https://usuario:senha@isadora2anos.org", "https://isadora2anos.org:8443",
])
def test_reject_insecure_or_non_root_origins(origin):
    with pytest.raises(ValueError):
        checker.inspect(origin)


def test_cli_report_does_not_claim_backend_verified(monkeypatch, capsys):
    monkeypatch.setattr(checker, "inspect", lambda url: {
        "status": "PASS", "read_only": True,
        "checked_assets": 4, "files": list(checker.ASSETS),
        "backend_version_verified": False,
    })
    assert checker.main(["--url", "https://isadora2anos.org", "--json"]) == 0
    output = capsys.readouterr().out
    assert '"backend_version_verified": false' in output
    assert '"read_only": true' in output
    assert "token" not in output.lower()


def test_cli_fail_report_is_nonzero(monkeypatch, capsys):
    def fail(_url):
        raise RuntimeError("Versão diferente de admin.js")
    monkeypatch.setattr(checker, "inspect", fail)
    assert checker.main(["--url", "https://isadora2anos.org", "--json"]) == 1
    assert '"status": "FAIL"' in capsys.readouterr().out
