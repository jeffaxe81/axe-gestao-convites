"""The Compose persistence smoke is deliberately forbidden off GitHub Actions."""
import pytest

from scripts import check_persistence


def test_disposable_persistence_smoke_never_runs_outside_ci(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    def network_forbidden(*_args, **_kwargs):
        pytest.fail("Nenhum HTTP ou Docker pode executar fora da CI.")
    monkeypatch.setattr(check_persistence.urllib.request, "build_opener", network_forbidden)
    monkeypatch.setattr(check_persistence.subprocess, "run", network_forbidden)
    with pytest.raises(SystemExit, match="BLOQUEADO"):
        check_persistence.main()
