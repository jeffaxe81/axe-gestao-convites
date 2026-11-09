"""Opt-in engagement is distinct from passive reads, manual dispatch and RSVP."""
from sqlalchemy import select
from app.guest_list import template_csv
from app.models import InvitationInterest, AuditEvent
from tests.integration.test_public_api import store
from tests.integration.test_organizer_api import client, login


def _invitation(client, store):
    csrf = login(client).json["csrf_token"]
    imported = client.post("/api/admin/guest-list-import",
        data=template_csv().encode("utf-8"), content_type="text/csv",
        headers={"X-CSRF-Token": csrf})
    assert imported.status_code == 200
    invitation_id = client.get("/api/admin/invitations").json["families"][0]["id"]
    return invitation_id, store.invitation_token(invitation_id)


def test_interest_requires_explicit_click_and_does_not_confirm_attendance(client, store):
    invitation_id, token = _invitation(client, store)
    url = "/api/invitations/" + invitation_id
    assert client.get(url, headers={"Authorization": "Bearer " + token}).json["interested"] is False
    assert store.invitation_overview()["counts"]["interested"] == 0
    assert client.post(url + "/interest").status_code == 401
    assert client.post(url + "/interest", headers={"Authorization": "Bearer invalid"}).status_code == 401
    first = client.post(url + "/interest", headers={"Authorization": "Bearer " + token})
    assert first.status_code == 200 and first.json == {"interested": True}
    again = client.post(url + "/interest", headers={"Authorization": "Bearer " + token})
    assert again.status_code == 200 and again.json == first.json
    assert client.get(url, headers={"Authorization": "Bearer " + token}).json["interested"] is True
    overview = store.invitation_overview()
    assert overview["counts"]["interested"] == 1
    assert overview["counts"]["pending"] == 1
    assert overview["counts"]["confirmed"] == 0
    assert overview["counts"]["sent"] == 0
    assert overview["families"][0]["interested"] is True
    assert overview["families"][0]["interested_at_utc"]
    assert store.summary()["counts"].total == 0
    with store.session_factory() as session:
        assert len(session.scalars(select(InvitationInterest)).all()) == 1
        assert [event.event_kind for event in session.scalars(select(AuditEvent)).all()] == [
            "INVITATION_INTEREST"
        ]


def test_opening_or_refreshing_invitation_does_not_register_interest(client, store):
    """Passive page loads and invitation reads cannot masquerade as an opt-in."""
    invitation_id, token = _invitation(client, store)
    url = "/api/invitations/" + invitation_id
    auth = {"Authorization": "Bearer " + token}
    for _ in range(3):
        assert client.get("/convite").status_code == 200
        response = client.get(url, headers=auth)
        assert response.status_code == 200
        assert response.json["interested"] is False
    overview = store.invitation_overview()
    assert overview["counts"]["interested"] == 0
    assert overview["families"][0]["interested"] is False
    with store.session_factory() as session:
        assert session.scalars(select(InvitationInterest)).all() == []
        assert session.scalars(select(AuditEvent)).all() == []
