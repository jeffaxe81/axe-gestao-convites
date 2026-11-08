from datetime import datetime, timedelta, timezone

import pytest

from app.domain import (
    Counts,
    InputError,
    ParticipantInput,
    can_edit,
    count_participants,
    validate_rsvp,
)


def family(*ages):
    return [ParticipantInput(f"Criança {age}", "CHILD", age) for age in ages]


def test_age_boundaries_for_buffet_and_souvenirs():
    participants = family(0, 5, 6, 12) + [ParticipantInput("Pessoa 13+", "OVER_12", None)]
    assert count_participants(participants) == Counts(
        total=5, buffet=3, children_0_5=2, children_0_12=4, over_12=1
    )


def test_empty_party_has_all_zero_counts():
    assert count_participants([]) == Counts(0, 0, 0, 0, 0)


def test_deadline_open_without_limit_and_closed_at_exact_limit():
    limit = datetime(2026, 12, 5, 23, 59, tzinfo=timezone.utc)
    assert can_edit(limit - timedelta(microseconds=1), limit)
    assert not can_edit(limit, limit)
    assert not can_edit(limit + timedelta(microseconds=1), limit)
    assert can_edit(limit + timedelta(days=30), None)


def test_deadline_compares_instants_across_timezones():
    brasil = timezone(timedelta(hours=-3))
    local = datetime(2026, 12, 5, 20, 59, tzinfo=brasil)
    utc = datetime(2026, 12, 5, 23, 59, tzinfo=timezone.utc)
    assert not can_edit(local, utc)


def test_deadline_requires_aware_datetimes():
    with pytest.raises(ValueError):
        can_edit(datetime(2026, 12, 5), None)
    with pytest.raises(ValueError):
        can_edit(datetime.now(timezone.utc), datetime(2026, 12, 5))


def test_positive_response_contains_principal_once_and_companions():
    response = validate_rsvp({
        "contact_name": "  Ana   Maria  ",
        "attending": True,
        "participants": [
            {"name": "Ana Maria", "kind": "OVER_12", "age_years": None},
            {"name": "Iza", "kind": "CHILD", "age_years": 2},
        ],
    })
    assert response.contact_name == "Ana Maria"
    assert len(response.participants) == 2
    assert count_participants(response.participants) == Counts(2, 1, 1, 1, 1)


def test_negative_response_requires_name_and_no_participants():
    response = validate_rsvp({"contact_name": "João", "attending": False, "participants": []})
    assert response.attending is False
    assert response.participants == ()


@pytest.mark.parametrize("bad", [None, -1, 1.5, True, "6", 13])
def test_invalid_child_ages_are_rejected(bad):
    with pytest.raises(InputError):
        validate_rsvp({"contact_name": "C", "attending": True, "participants": [
            {"name": "C", "kind": "CHILD", "age_years": bad}
        ]})


@pytest.mark.parametrize("value", ["", " ", 9, "A" * 161])
def test_invalid_names_are_rejected(value):
    with pytest.raises(InputError):
        validate_rsvp({"contact_name": value, "attending": False, "participants": []})


def test_homonyms_and_html_are_kept_as_plain_strings():
    name = "<img src=x onerror=alert(1)>"
    response = validate_rsvp({"contact_name": name, "attending": True, "participants": [
        {"name": name, "kind": "OVER_12", "age_years": None},
        {"name": name, "kind": "OVER_12", "age_years": None},
    ]})
    assert len(response.participants) == 2
    assert response.participants[0].name == name


@pytest.mark.parametrize("payload", [
    {"contact_name": "A", "attending": True, "participants": []},
    {"contact_name": "A", "attending": False, "participants": [{"name": "A", "kind": "OVER_12"}]},
    {"contact_name": "A", "attending": 1, "participants": []},
    {"contact_name": "A", "attending": True, "participants": [{"name": "B", "kind": "OVER_12"}]},
    {"contact_name": "A", "attending": True, "participants": [{"name": "A", "kind": "OVER_12", "age_years": 14}]},
])
def test_inconsistent_response_is_rejected(payload):
    with pytest.raises(InputError):
        validate_rsvp(payload)


def test_more_than_one_hundred_participants_rejected():
    payload = {"contact_name": "A", "attending": True, "participants": [
        {"name": "A", "kind": "OVER_12"}
    ] * 101}
    with pytest.raises(InputError):
        validate_rsvp(payload)


def test_unexpected_field_is_rejected():
    with pytest.raises(InputError):
        validate_rsvp({"contact_name": "A", "attending": False, "participants": [], "buffet": 30})
