"""Importação administrativa e links individuais de convite."""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Invitation


REQUIRED_HEADERS = ("Nome da família", "Responsável", "WhatsApp", "Convidados")
MAX_CSV_BYTES = 1_000_000
MAX_ROWS = 500


@dataclass(frozen=True)
class ParsedGuest:
    family_name: str
    contact_name: str
    whatsapp: str
    expected_guests: int


class InvitationImportError(ValueError):
    pass


def parse_guest_csv(raw: bytes) -> list[ParsedGuest]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_CSV_BYTES:
        raise InvitationImportError("Arquivo vazio ou maior que 1 MB.")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvitationImportError("Salve a planilha como CSV UTF-8.") from exc
    sample = content[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(content, newline=""), dialect=dialect)
    if tuple((h or "").strip() for h in (reader.fieldnames or ())) != REQUIRED_HEADERS:
        raise InvitationImportError("Cabeçalho inválido. Use: " + ", ".join(REQUIRED_HEADERS))
    rows: list[ParsedGuest] = []
    seen_phones: set[str] = set()
    for line, row in enumerate(reader, start=2):
        if len(rows) >= MAX_ROWS:
            raise InvitationImportError("O limite é de 500 famílias por importação.")
        if not row or all(not (v or "").strip() for v in row.values() if isinstance(v, str)):
            continue
        if None in row or any(row.get(key) is None for key in REQUIRED_HEADERS):
            raise InvitationImportError(f"Linha {line}: quantidade de colunas inválida.")
        family = " ".join((row.get(REQUIRED_HEADERS[0]) or "").split())
        contact = " ".join((row.get(REQUIRED_HEADERS[1]) or "").split())
        raw_phone = (row.get(REQUIRED_HEADERS[2]) or "").strip()
        if any(not (ch in "0123456789" or ch in "+ ().-") for ch in raw_phone):
            raise InvitationImportError(f"Linha {line}: WhatsApp contém caracteres inválidos.")
        phone = "".join(ch for ch in raw_phone if ch in "0123456789")
        guests_raw = (row.get(REQUIRED_HEADERS[3]) or "").strip()
        if not family or len(family) > 160:
            raise InvitationImportError(f"Linha {line}: nome da família inválido.")
        if not contact or len(contact) > 160:
            raise InvitationImportError(f"Linha {line}: responsável inválido.")
        if not (len(phone) in (12, 13) and phone.startswith("55")):
            raise InvitationImportError(f"Linha {line}: WhatsApp deve conter país, DDD e número.")
        if phone in seen_phones:
            raise InvitationImportError(f"Linha {line}: WhatsApp duplicado no arquivo.")
        if not guests_raw.isascii() or not guests_raw.isdigit() or not 1 <= int(guests_raw) <= 100:
            raise InvitationImportError(f"Linha {line}: convidados deve ser um inteiro entre 1 e 100.")
        seen_phones.add(phone)
        rows.append(ParsedGuest(family, contact, phone, int(guests_raw)))
    if not rows:
        raise InvitationImportError("Nenhuma família válida encontrada.")
    return rows


class InvitationStore:
    def __init__(self, session_factory: Callable[[], Session], token_secret: str):
        if not isinstance(token_secret, str) or len(token_secret) < 32:
            raise ValueError("TOKEN_SECRET deve ter ao menos 32 caracteres.")
        self.session_factory = session_factory
        self._secret = token_secret.encode("utf-8")

    def _hash_token(self, token: str) -> str:
        return hmac.new(self._secret, ("invitation:v1:" + token).encode(), hashlib.sha256).hexdigest()

    def import_rows(self, rows: list[ParsedGuest], now: datetime | None = None) -> list[dict]:
        if not rows or len(rows) > MAX_ROWS:
            raise InvitationImportError("Lote de importação inválido.")
        created = datetime.now(timezone.utc) if now is None else now
        if created.utcoffset() is None:
            raise ValueError("Data de criação precisa conter fuso horário.")
        issued: list[dict] = []
        with self.session_factory.begin() as session:
            existing_phones = set(session.scalars(
                select(Invitation.whatsapp).where(Invitation.revoked_at_utc.is_(None))
            ).all())
            incoming = [item.whatsapp for item in rows]
            if len(set(incoming)) != len(incoming) or any(phone in existing_phones for phone in incoming):
                raise InvitationImportError("Há WhatsApp repetido nesta planilha ou já cadastrado.")
            for item in rows:
                token = secrets.token_urlsafe(32)
                invitation_id = str(uuid.uuid4())
                session.add(Invitation(
                    id=invitation_id, family_name=item.family_name,
                    contact_name=item.contact_name, whatsapp=item.whatsapp,
                    expected_guests=item.expected_guests,
                    token_hash=self._hash_token(token), status="LINK_GENERATED",
                    created_at_utc=created.astimezone(timezone.utc).replace(tzinfo=None)))
                # Token puro é devolvido uma única vez; somente o hash fica no banco.
                issued.append({"id": invitation_id, "family_name": item.family_name,
                               "contact_name": item.contact_name, "whatsapp": item.whatsapp,
                               "expected_guests": item.expected_guests, "token": token})
            session.add(AuditEvent(event_kind="INVITATIONS_IMPORTED",
                                   occurred_at_utc=created.astimezone(timezone.utc).replace(tzinfo=None)))
        return issued

    def list_invitations(self, limit: int = 500) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("Limite inválido.")
        with self.session_factory() as session:
            entries = session.scalars(select(Invitation).order_by(Invitation.created_at_utc.desc()).limit(limit)).all()
            return [{
                "id": item.id, "family_name": item.family_name,
                "contact_name": item.contact_name, "whatsapp": item.whatsapp,
                "expected_guests": item.expected_guests, "status": item.status,
                "created_at_utc": item.created_at_utc.replace(tzinfo=timezone.utc).isoformat(),
                "sent_at_utc": item.sent_at_utc.replace(tzinfo=timezone.utc).isoformat() if item.sent_at_utc else None,
                "linked_family_id": item.linked_family_id,
            } for item in entries]

    def resolve_token(self, token: str) -> dict | None:
        if not isinstance(token, str) or not 30 <= len(token) <= 100:
            return None
        digest = self._hash_token(token)
        with self.session_factory() as session:
            item = session.scalar(select(Invitation).where(Invitation.token_hash == digest))
            if item is None or item.revoked_at_utc is not None:
                return None
            return {"id": item.id, "family_name": item.family_name,
                    "contact_name": item.contact_name, "expected_guests": item.expected_guests,
                    "status": item.status}

    def mark_sent(self, invitation_id: str, now: datetime | None = None) -> None:
        moment = datetime.now(timezone.utc) if now is None else now
        if moment.utcoffset() is None:
            raise ValueError("Data precisa conter fuso horário.")
        with self.session_factory.begin() as session:
            item = session.get(Invitation, invitation_id, with_for_update=True)
            if item is None or item.revoked_at_utc is not None:
                raise InvitationImportError("Convite não encontrado ou revogado.")
            if item.status == "LINK_GENERATED":
                item.status = "SENT"
                item.sent_at_utc = moment.astimezone(timezone.utc).replace(tzinfo=None)
            session.add(AuditEvent(event_kind="INVITATION_MARKED_SENT",
                                   occurred_at_utc=moment.astimezone(timezone.utc).replace(tzinfo=None)))

    def revoke(self, invitation_id: str, now: datetime | None = None) -> None:
        moment = datetime.now(timezone.utc) if now is None else now
        if moment.utcoffset() is None:
            raise ValueError("Data precisa conter fuso horário.")
        with self.session_factory.begin() as session:
            item = session.get(Invitation, invitation_id, with_for_update=True)
            if item is None:
                raise InvitationImportError("Convite não encontrado.")
            item.revoked_at_utc = moment.astimezone(timezone.utc).replace(tzinfo=None)
            item.status = "REVOKED"
            session.add(AuditEvent(event_kind="INVITATION_REVOKED",
                                   occurred_at_utc=moment.astimezone(timezone.utc).replace(tzinfo=None)))
