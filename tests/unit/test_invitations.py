"""Regression tests for pre-invitation import and one-time RSVP binding."""
import hashlib
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.domain import validate_rsvp
from app.invitations import (
    InvitationImportError, InvitationStore, ParsedGuest, parse_guest_csv,
)
from app.models import Base, EventSettings, Family, Invitation
from app.rsvp import AccessDenied, RsvpStore
from app.organizer import public_invitation_origin
from app.domain import InputError


SECRET = "test-secret-with-at-least-32-characters"


@pytest.fixture
def stores():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    yield factory, InvitationStore(factory, SECRET), RsvpStore(factory, SECRET)
    engine.dispose()


def test_parse_utf8_csv_with_bom_and_semicolon():
    raw = (
        "\ufeffNome da família;Responsável;WhatsApp;Convidados\n"
        "Família Silva;João Silva;+55 (48) 99999-1111;4\n"
    ).encode("utf-8")
    rows = parse_guest_csv(raw)
    assert rows == [ParsedGuest("Família Silva", "João Silva", "5548999991111", 4)]


@pytest.mark.parametrize("raw", [
    b"",
    b"Nome,Responsavel,Telefone,Quantidade\nA,B,5548999999999,2\n",
    "Nome da família,Responsável,WhatsApp,Convidados\nA,B,telefone,2\n".encode(),
    "Nome da família,Responsável,WhatsApp,Convidados\nA,B,5548999999999,0\n".encode(),
    "Nome da família,Responsável,WhatsApp,Convidados\nA,B,5548999999999,2,extra\n".encode(),
])
def test_reject_invalid_csv(raw):
    with pytest.raises(InvitationImportError):
        parse_guest_csv(raw)


def test_import_stores_only_hash_and_resolves_token(stores):
    _factory, invitations, _rsvps = stores
    rows = [ParsedGuest("Família Silva", "João Silva", "5548999991111", 4)]
    issued = invitations.import_rows(rows)
    assert len(issued) == 1
    with invitations.session_factory() as session:
        assert session.scalar(select(Family)) is None
    token = issued[0]["token"]
    assert invitations.resolve_token(token)["contact_name"] == "João Silva"
    with invitations.session_factory() as session:
        record = session.scalar(select(Invitation))
        assert record.token_hash != token
        assert record.token_hash == invitations._hash_token(token)


def test_rsvp_consumes_invitation_and_blocks_second_family(stores):
    factory, invitations, rsvps = stores
    issued = invitations.import_rows([
        ParsedGuest("Família Silva", "João Silva", "5548999991111", 4)
    ])
    token = issued[0]["token"]
    payload = validate_rsvp({
        "contact_name": "João Silva",
        "attending": True,
        "participants": [{"name": "João Silva", "kind": "OVER_12", "age_years": None}],
    })
    receipt = rsvps.create(payload, "submission-key-first-0001",
                           datetime.now(timezone.utc), invitation_token=token)
    with factory() as session:
        record = session.scalar(select(Invitation))
        assert record.linked_family_id == receipt.id
        assert record.status == "CONFIRMED"
    with pytest.raises(AccessDenied):
        rsvps.create(payload, "submission-key-second-0002",
                      datetime.now(timezone.utc), invitation_token=token)


def test_mark_sent_and_revoke(stores):
    _factory, invitations, _rsvps = stores
    issued = invitations.import_rows([
        ParsedGuest("Família Souza", "Maria Souza", "5548999992222", 3)
    ])
    invitation_id, token = issued[0]["id"], issued[0]["token"]
    invitations.mark_sent(invitation_id)
    assert invitations.list_invitations()[0]["status"] == "SENT"
    invitations.revoke(invitation_id)
    assert invitations.resolve_token(token) is None
    assert invitations.list_invitations()[0]["status"] == "REVOKED"



def test_invitation_status_tracks_later_rsvp_edit(stores):
    factory, invitations, rsvps = stores
    issued = invitations.import_rows([
        ParsedGuest("Família Oliveira", "Pedro Oliveira", "5548999993333", 2)
    ])
    token = issued[0]["token"]
    accepted = validate_rsvp({
        "contact_name": "Pedro Oliveira", "attending": True,
        "participants": [{"name": "Pedro Oliveira", "kind": "OVER_12", "age_years": None}],
    })
    receipt = rsvps.create(accepted, "submission-key-edit-0001",
                           datetime.now(timezone.utc), invitation_token=token)
    with factory.begin() as session:
        session.add(EventSettings(id=1, venue=None, edit_deadline_utc=None, buffet_limit=40))
    declined = validate_rsvp({
        "contact_name": "Pedro Oliveira", "attending": False, "participants": [],
    })
    rsvps.update(receipt.id, receipt.edit_token, 1, declined, datetime.now(timezone.utc))
    assert invitations.list_invitations()[0]["status"] == "DECLINED"
    with pytest.raises(InvitationImportError, match="já utilizado"):
        invitations.revoke(issued[0]["id"])



@pytest.mark.parametrize("raw", [
    "",
    "ftp://example.com",
    "https://",
    "https://user:pass@example.com",
    "https://example.com/path?query=1",
    "https://example.com/#fragment",
])
def test_public_invitation_origin_rejects_invalid_configuration(monkeypatch, raw):
    monkeypatch.setenv("APP_PUBLIC_URL", raw)
    with pytest.raises(InputError):
        public_invitation_origin()


@pytest.mark.parametrize("raw, expected", [
    ("https://isadora2anos.org", "https://isadora2anos.org"),
    ("https://isadora2anos.org/", "https://isadora2anos.org"),
    ("http://localhost:5000/", "http://localhost:5000"),
])
def test_public_invitation_origin_normalizes_valid_configuration(monkeypatch, raw, expected):
    monkeypatch.setenv("APP_PUBLIC_URL", raw)
    assert public_invitation_origin() == expected
