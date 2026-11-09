"""Manual dispatch is not a WhatsApp delivery receipt or an RSVP."""
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from app.guest_list import template_csv
from app.models import InvitationDispatch, AuditEvent
from tests.integration.test_public_api import store
from tests.integration.test_organizer_api import client, login


def _setup(client):
    csrf = login(client).json["csrf_token"]
    response = client.post("/api/admin/guest-list-import",
        data=template_csv().encode("utf-8"), content_type="text/csv",
        headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    roster = client.get("/api/admin/invitations").json
    return csrf, roster["families"][0]["id"]


def test_manual_dispatch_is_reversible_idempotent_and_separate_from_rsvp(client, store):
    csrf, invitation_id = _setup(client)
    url = "/api/admin/invitations/" + invitation_id + "/sent"
    headers = {"X-CSRF-Token": csrf}
    initial = store.invitation_overview()
    assert initial["counts"] == {
        "total": 1, "pending": 1, "confirmed": 0, "declined": 0,
        "sent": 0, "not_sent": 1
    }
    first = client.put(url, json={"sent": True}, headers=headers)
    assert first.status_code == 200
    assert first.json["sent"] is True
    assert datetime.fromisoformat(first.json["sent_at_utc"]).tzinfo is not None
    second = client.put(url, json={"sent": True}, headers=headers)
    assert second.status_code == 200 and second.json == first.json
    current = client.get("/api/admin/invitations").json
    assert current["counts"] == {
        "total": 1, "pending": 1, "confirmed": 0, "declined": 0,
        "sent": 1, "not_sent": 0
    }
    assert current["families"][0]["status"] == "PENDENTE"
    assert current["families"][0]["sent_at_utc"] == first.json["sent_at_utc"]
    assert store.summary()["counts"].total == 0
    with store.session_factory() as session:
        assert len(session.scalars(select(InvitationDispatch)).all()) == 1
        assert [e.event_kind for e in session.scalars(
            select(AuditEvent).order_by(AuditEvent.id)).all()] == ["INVITATION_SENT_MARKED"]
    undone = client.put(url, json={"sent": False}, headers=headers)
    assert undone.status_code == 200
    assert undone.json == {"sent": False, "sent_at_utc": None}
    undone_again = client.put(url, json={"sent": False}, headers=headers)
    assert undone_again.json == undone.json
    with store.session_factory() as session:
        assert len(session.scalars(select(InvitationDispatch)).all()) == 0
        assert [e.event_kind for e in session.scalars(
            select(AuditEvent).order_by(AuditEvent.id)).all()] == [
                "INVITATION_SENT_MARKED", "INVITATION_SENT_UNMARKED"]
    assert store.invitation_overview()["counts"]["not_sent"] == 1
    assert store.summary()["counts"].total == 0


def test_manual_dispatch_rejects_unauthorized_csrf_and_invalid_requests(client):
    path = "/api/admin/invitations/00000000-0000-0000-0000-000000000000/sent"
    assert client.put(path, json={"sent": True}).status_code == 401
    csrf, real_id = _setup(client)
    url = "/api/admin/invitations/" + real_id + "/sent"
    assert client.put(url, json={"sent": True}).status_code == 403
    assert client.put(url, json={"sent": True}, headers={"X-CSRF-Token": "invalid"}).status_code == 403
    headers = {"X-CSRF-Token": csrf}
    for invalid in ({"sent": 1}, {"sent": "true"}, {"sent": None},
                    {}, {"sent": True, "delivered": True}):
        assert client.put(url, json=invalid, headers=headers).status_code == 422
    assert client.put(path, json={"sent": True}, headers=headers).status_code == 422
    assert client.put("/api/admin/invitations/not-a-uuid/sent",
                      json={"sent": True}, headers=headers).status_code == 422
    assert client.put(url, json={"sent": True}, headers=headers).status_code == 200
    # The manual-send flag cannot be altered by guests or from a public RSVP.
    logout = client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert client.put(url, json={"sent": False}, headers=headers).status_code == 401


def test_dispatch_survives_an_independent_decline(client, store):
    csrf, invitation_id = _setup(client)
    url = "/api/admin/invitations/" + invitation_id + "/sent"
    assert client.put(url, json={"sent": True},
                      headers={"X-CSRF-Token": csrf}).status_code == 200
    secret = store.invitation_token(invitation_id)
    refusal = client.post("/api/invitations/" + invitation_id + "/response",
        headers={"Authorization": "Bearer " + secret},
        json={"contact_name": "Maria Silva", "attending": False, "participants": []})
    assert refusal.status_code == 200
    overview = store.invitation_overview()
    assert overview["counts"] == {
        "total": 1, "pending": 0, "confirmed": 0, "declined": 1,
        "sent": 1, "not_sent": 0
    }
    assert overview["families"][0]["sent"] is True
    assert store.summary()["counts"].total == 0
