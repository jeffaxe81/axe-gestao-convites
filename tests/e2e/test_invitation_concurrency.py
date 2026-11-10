"""Regressão: leituras simultâneas de convites não compartilham conexão SQLite."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from tests.e2e.test_organizer import organizer_server


def test_parallel_organizer_invitation_reads_are_consistent(organizer_server):
    _base, store = organizer_server
    store.import_invited_families([{
        "key": "familia-concorrencia", "name": "Família Concorrência",
        "phone": "11999999999", "adults": 2, "young": 0, "older": 0,
    }])
    barrier = Barrier(8)

    def read_repeatedly(_index):
        barrier.wait(timeout=10)
        return [store.invitation_overview()["counts"] for _ in range(12)]

    with ThreadPoolExecutor(max_workers=8) as executor:
        snapshots = list(executor.map(read_repeatedly, range(8)))

    for batch in snapshots:
        for counts in batch:
            assert counts == {
                "total": 1, "pending": 1, "confirmed": 0, "declined": 0,
                "sent": 0, "not_sent": 1, "interested": 0,
            }
