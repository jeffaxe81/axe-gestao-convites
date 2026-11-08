"""Real Flask + SQLAlchemy integration load on synthetic guests, not production.

Contrasts genuine API responses, DB history and independently recomputed totals.
The billion-scale native model suite is deliberately separate.
"""
from datetime import datetime, timezone
from uuid import NAMESPACE_DNS, uuid5

from sqlalchemy import func, select

from app.models import AuditEvent
from tests.integration.test_public_api import bearer, client, store


def fake_family(index):
    name = "Pessoa sintética " + str(index)
    attending = index % 5 != 0
    ages = (0, 5, 6, 12)
    participants = []
    if attending:
        participants.append({"name": name, "kind": "OVER_12", "age_years": None})
        participants.append({
            "name": "Criança sintética " + str(index),
            "kind": "CHILD", "age_years": ages[index % len(ages)]
        })
        if index % 3 == 0:
            participants.append({
                "name": "Acompanhante sintético " + str(index),
                "kind": "OVER_12", "age_years": None
            })
    return {"contact_name": name, "attending": attending, "participants": participants}


def oracle_expected(responses):
    confirmed = declined = total = buffet = young = children = over = 0
    for family in responses.values():
        if not family["attending"]:
            assert family["participants"] == []
            declined += 1
            continue
        confirmed += 1
        for person in family["participants"]:
            total += 1
            if person["kind"] == "OVER_12":
                over += 1
                buffet += 1
            else:
                age = person["age_years"]
                assert 0 <= age <= 12
                children += 1
                if age <= 5:
                    young += 1
                else:
                    buffet += 1
    return {
        "total": total, "buffet": buffet,
        "children_0_5": young, "children_0_12": children,
        "over_12": over,
    }, confirmed, declined


def test_160_synthetic_families_duplicated_revised_and_counted(client, store):
    saved = {}
    replies = {}
    created = retried = conflicts = edits = stale = 0
    for index in range(160):
        payload = fake_family(index)
        key = str(uuid5(NAMESPACE_DNS, "isadora-guest-load-" + str(index)))
        headers = {"Idempotency-Key": key}
        first = client.post("/api/rsvps", json=payload, headers=headers)
        assert first.status_code == 201, (index, first.json)
        created += 1
        assert set(first.json) == {"id", "revision", "edit_token", "attending"}
        retry = client.post("/api/rsvps", json=payload, headers=headers)
        assert retry.status_code == 200 and retry.json == first.json
        retried += 1
        if index % 11 == 0:
            other = {**payload, "contact_name": "Tentativa de chave reutilizada",
                     "participants": [dict(p) for p in payload["participants"]]}
            if other["participants"]:
                other["participants"][0]["name"] = other["contact_name"]
            invalid_replay = client.post("/api/rsvps", json=other, headers=headers)
            assert invalid_replay.status_code == 409, (index, invalid_replay.json)
            conflicts += 1
        saved[index] = payload
        replies[index] = first.json
        if index % 17 == 0:
            lookup = client.get("/api/rsvps/" + first.json["id"],
                                headers=bearer(first.json["edit_token"]))
            assert lookup.status_code == 200
            assert lookup.json["contact_name"] == payload["contact_name"]
            assert client.get("/api/rsvps/" + first.json["id"]).status_code == 401

    for index in range(0, 160, 3):
        first = replies[index]
        previous = saved[index]
        changed_attending = not previous["attending"]
        update = {
            "contact_name": previous["contact_name"],
            "attending": changed_attending,
            "participants": (fake_family(index + 1)["participants"]
                             if changed_attending else []),
        }
        # If this family starts as declined, make its first participant match
        # the contact name. The API enforces this invariant.
        if update["participants"]:
            update["participants"][0]["name"] = update["contact_name"]
        path = "/api/rsvps/" + first["id"]
        headers = bearer(first["edit_token"])
        change = client.put(path, json={"revision": 1, **update}, headers=headers)
        assert change.status_code == 200, (index, change.json)
        assert change.json["id"] == first["id"]
        assert change.json["revision"] == 2
        edits += 1
        previous_revision = client.put(path, json={"revision": 1, **update}, headers=headers)
        assert previous_revision.status_code == 409
        stale += 1
        saved[index] = update

    expected, confirmed, declined = oracle_expected(saved)
    summary = store.summary()
    assert vars(summary["counts"]) == expected
    assert len(summary["confirmed"]) == confirmed
    assert len(summary["declined"]) == declined
    assert len(summary["souvenir_children"]) == expected["children_0_12"]
    assert summary["buffet_limit_reached"] == (expected["buffet"] >= 40)
    assert summary["buffet_limit"] == 40
    with store.session_factory() as session:
        history_rows = session.scalar(select(func.count()).select_from(AuditEvent))
    assert history_rows == created + edits
    assert (created, retried, conflicts, edits, stale) == (160, 160, 15, 54, 54)
    assert client.get("/api/admin/dashboard").status_code == 401
    assert "buffet" not in str(client.get("/api/event").json).lower()
