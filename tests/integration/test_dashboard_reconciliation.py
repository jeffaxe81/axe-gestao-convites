"""Cross-report invariants for family invitations and operational metrics.

Use only fictional families. Marking a manual send or declaring interest must
never count as confirmed attendance. A response edit must be reflected in all
administrative views and both CSV exports without exposing bearer tokens.
"""
import csv
import io

from tests.integration.test_organizer_api import client, login
from tests.integration.test_public_api import store


def _csv_rows(response):
    assert response.status_code == 200
    assert response.data.startswith(b"\xef\xbb\xbf")
    assert "no-store" in response.headers["Cache-Control"]
    return list(csv.reader(io.StringIO(response.data.decode("utf-8-sig")),
                           delimiter=";"))


def _import_fictional_families(client, csrf):
    content = (
        "familia;responsavel;telefone;adultos;criancas_0_5;criancas_6_12\r\n"
        "familia-alfa;Pessoa Alfa;11999990001;1;1;0\r\n"
        "familia-beta;Pessoa Beta;11999990002;1;0;1\r\n"
        "familia-gama;Pessoa Gama;11999990003;2;0;0\r\n"
    )
    result = client.post("/api/admin/guest-list-import",
                         data=content.encode("utf-8"),
                         content_type="text/csv",
                         headers={"X-CSRF-Token": csrf})
    assert result.status_code == 200
    assert result.json["imported"] == 3
    return {row["key"]: row for row in
            client.get("/api/admin/invitations").json["families"]}


def _answer(client, store, family, *, attending, participants):
    token = store.invitation_token(family["id"])
    response = client.post(
        f"/api/invitations/{family['id']}/response",
        headers={"Authorization": "Bearer " + token},
        json={"contact_name": family["name"], "attending": attending,
              "participants": participants})
    assert response.status_code == 200
    return response.json


def _edit(client, receipt, *, attending, participants):
    response = client.put(
        "/api/rsvps/" + receipt["id"],
        headers={"Authorization": "Bearer " + receipt["edit_token"]},
        json={"revision": receipt["revision"], "contact_name": "Pessoa Editada",
              "attending": attending, "participants": participants})
    assert response.status_code == 200
    return response.json


def _assert_reconciled(client, *, expected_counts, expected_roster,
                       expected_followup, expected_planning):
    dashboard = client.get("/api/admin/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json["counts"] == expected_counts
    overview = client.get("/api/admin/invitations")
    assert overview.status_code == 200
    assert overview.json["counts"] == expected_roster
    roster = overview.json["families"]
    assert expected_roster["total"] == len(roster)
    assert expected_roster["total"] == sum(
        expected_roster[key] for key in ("pending", "confirmed", "declined"))
    assert expected_roster["total"] == (expected_roster["sent"] +
                                       expected_roster["not_sent"])
    assert expected_roster["confirmed"] == len(dashboard.json["confirmed"])
    assert expected_roster["declined"] == len(dashboard.json["declined"])

    guest_summary = client.get("/api/admin/guest-list-summary")
    assert guest_summary.status_code == 200
    assert guest_summary.json["families"] == expected_roster["total"]
    assert guest_summary.json["pending"] == expected_roster["pending"]

    followup = _csv_rows(client.get("/api/admin/invitation-followup.csv"))
    assert len(followup) == 1 + expected_roster["total"]
    assert {row[0]: (row[3], row[4], row[6]) for row in followup[1:]} == expected_followup
    assert "/convite#" not in str(followup)
    assert "edit_token" not in str(followup)
    assert sum(row[4] == "Sim" for row in followup[1:]) == expected_roster["sent"]
    assert sum(row[6] == "Sim" for row in followup[1:]) == expected_roster["interested"]

    attendance = _csv_rows(client.get("/api/admin/export.csv"))
    confirmed_people = sum(len(f["participants"]) for f in dashboard.json["confirmed"])
    assert len(attendance) - 1 == confirmed_people + expected_roster["declined"]
    assert sum(row[0] == "Recusou" for row in attendance[1:]) == expected_roster["declined"]
    assert sum(row[0] == "Confirmado" for row in attendance[1:]) == confirmed_people

    planning = _csv_rows(client.get("/api/admin/planning.csv"))
    assert dict(planning[1:]) == expected_planning


def test_dashboard_csv_and_invitation_status_reconcile_after_edits(client, store):
    csrf = login(client).json["csrf_token"]
    families = _import_fictional_families(client, csrf)
    alfa = families["familia-alfa"]
    beta = families["familia-beta"]
    gamma = families["familia-gama"]

    # A manual send and an explicit interest do not create a confirmation.
    for family in (alfa, beta):
        result = client.put(f"/api/admin/invitations/{family['id']}/sent",
                            headers={"X-CSRF-Token": csrf}, json={"sent": True})
        assert result.status_code == 200
    interest = client.post(f"/api/invitations/{gamma['id']}/interest",
                           headers={"Authorization": "Bearer " +
                                    store.invitation_token(gamma["id"])})
    assert interest.status_code == 200
    assert client.get("/api/admin/dashboard").json["counts"]["total"] == 0

    adult = {"name": "Adulto Ficticio", "kind": "OVER_12", "age_years": None}
    child_five = {"name": "Crianca Cinco", "kind": "CHILD", "age_years": 5}
    child_six = {"name": "Crianca Seis", "kind": "CHILD", "age_years": 6}
    alfa_receipt = _answer(client, store, alfa, attending=True,
                           participants=[adult, child_five])
    beta_receipt = _answer(client, store, beta, attending=False, participants=[])
    original_planning = {
        "Famílias confirmadas": "1",
        "Famílias que recusaram": "1",
        "Participantes confirmados": "2",
        "Pessoas para buffet": "1",
        "Crianças até 5 anos": "1",
        "Crianças de 6 a 12 anos": "0",
        "Crianças até 12 anos / lembrancinhas": "1",
        "Pessoas acima de 12 anos": "1",
        "Limite interno de buffet": "40",
        "Limite interno atingido": "Não",
    }
    _assert_reconciled(
        client,
        expected_counts={"total": 2, "buffet": 1, "children_0_5": 1,
                         "children_0_12": 1, "over_12": 1},
        expected_roster={"total": 3, "pending": 1, "confirmed": 1,
                         "declined": 1, "sent": 2, "not_sent": 1, "interested": 1},
        expected_followup={
            "familia-alfa": ("CONFIRMADO", "Sim", "Nao"),
            "familia-beta": ("RECUSADO", "Sim", "Nao"),
            "familia-gama": ("PENDENTE", "Nao", "Sim"),
        },
        expected_planning=original_planning,
    )

    # Reverse attendance states through authorized edits, preserving send/interest.
    _edit(client, alfa_receipt, attending=False, participants=[])
    _edit(client, beta_receipt, attending=True, participants=[adult, child_six])
    undone = client.put(f"/api/admin/invitations/{beta['id']}/sent",
                        headers={"X-CSRF-Token": csrf}, json={"sent": False})
    assert undone.status_code == 200
    edited_planning = {
        **original_planning,
        "Pessoas para buffet": "2",
        "Crianças até 5 anos": "0",
        "Crianças de 6 a 12 anos": "1",
    }
    _assert_reconciled(
        client,
        expected_counts={"total": 2, "buffet": 2, "children_0_5": 0,
                         "children_0_12": 1, "over_12": 1},
        expected_roster={"total": 3, "pending": 1, "confirmed": 1,
                         "declined": 1, "sent": 1, "not_sent": 2, "interested": 1},
        expected_followup={
            "familia-alfa": ("RECUSADO", "Sim", "Nao"),
            "familia-beta": ("CONFIRMADO", "Nao", "Nao"),
            "familia-gama": ("PENDENTE", "Nao", "Sim"),
        },
        expected_planning=edited_planning,
    )

    assert client.post("/api/auth/logout",
                       headers={"X-CSRF-Token": csrf}).status_code == 200
    for path in ("/api/admin/dashboard", "/api/admin/invitations",
                 "/api/admin/guest-list-summary", "/api/admin/export.csv",
                 "/api/admin/planning.csv", "/api/admin/invitation-followup.csv"):
        assert client.get(path).status_code == 401
