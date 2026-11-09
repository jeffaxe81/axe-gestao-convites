"""Transações de RSVP, proteção de link e consultas internas do organizador."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain import Counts, InputError, ParticipantInput, RsvpInput, can_edit, count_participants
from app.models import AuditEvent, EventSettings, Family, Participant, InvitedFamily


class IdempotencyConflict(Exception):
    pass


class RevisionConflict(Exception):
    pass


class AccessDenied(Exception):
    pass


class EditClosed(Exception):
    pass


@dataclass(frozen=True)
class RsvpReceipt:
    id: str
    revision: int
    edit_token: str
    attending: bool


def _utc_naive(dt: datetime) -> datetime:
    if not isinstance(dt, datetime) or dt.utcoffset() is None:
        raise ValueError('Informe data e horário com fuso.')
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _to_aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc) if dt else None


def _participant_dict(person: Participant) -> dict:
    return {'name': person.name, 'kind': person.kind, 'age_years': person.age_years}


def _input_bytes(data: RsvpInput) -> bytes:
    return json.dumps(asdict(data), ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def _family_public(family: Family) -> dict:
    return {'id': family.id, 'contact_name': family.contact_name,
            'attending': family.attending, 'revision': family.revision,
            'participants': [_participant_dict(p) for p in family.participants]}


class RsvpStore:
    def __init__(self, session_factory: Callable[[], Session], token_secret: str):
        if len(token_secret) < 16:
            raise ValueError('TOKEN_SECRET deve ter no mínimo 16 caracteres.')
        self.session_factory = session_factory
        self._secret = token_secret.encode('utf-8')

    def _edit_token(self, key: str) -> str:
        return hmac.new(self._secret, ('edit:v1:' + key).encode(), sha256).hexdigest()

    def _key_hash(self, key: str) -> str:
        return hmac.new(self._secret, ('submission:v1:' + key).encode(), sha256).hexdigest()

    @staticmethod
    def _receipt(family: Family, token: str) -> RsvpReceipt:
        return RsvpReceipt(family.id, family.revision, token, family.attending)

    def _existing(self, session: Session, key_hash: str, payload_hash: str, token: str) -> RsvpReceipt | None:
        family = session.scalar(select(Family).where(Family.submission_key_hash == key_hash))
        if family is None:
            return None
        if not hmac.compare_digest(family.payload_hash, payload_hash):
            raise IdempotencyConflict('Chave de envio reutilizada com dados diferentes.')
        return self._receipt(family, token)

    def create(self, data: RsvpInput, submission_key: str, now_utc: datetime) -> RsvpReceipt:
        recorded_at = _utc_naive(now_utc)
        if not isinstance(data, RsvpInput) or not isinstance(submission_key, str) or not (16 <= len(submission_key) <= 160):
            raise InputError('Envio inválido ou chave de idempotência ausente.')
        key_hash = self._key_hash(submission_key)
        token = self._edit_token(submission_key)
        digest = sha256(_input_bytes(data)).hexdigest()
        try:
            with self.session_factory.begin() as session:
                existing = self._existing(session, key_hash, digest, token)
                if existing:
                    return existing
                family = Family(id=str(uuid.uuid4()), contact_name=data.contact_name,
                                attending=data.attending, revision=1,
                                submission_key_hash=key_hash, payload_hash=digest,
                                edit_token_hash=sha256(token.encode()).hexdigest())
                session.add(family)
                session.flush()
                family.participants = [Participant(position=pos, name=p.name,
                    kind=p.kind, age_years=p.age_years) for pos, p in enumerate(data.participants)]
                session.flush()
                session.add(AuditEvent(event_kind='RSVP_CREATED' if data.attending else 'RSVP_DECLINED',
                                       occurred_at_utc=recorded_at))
                receipt = self._receipt(family, token)
            return receipt
        except IntegrityError:
            # Concurrent duplicate submission: uniqueness decides the winner.
            with self.session_factory() as session:
                existing = self._existing(session, key_hash, digest, token)
                if existing:
                    return existing
            raise

    def import_invited_families(self, records: list[dict]) -> dict:
        """Atomic idempotent import; changed existing keys cause rollback."""
        if not records or len(records) > 500:
            raise InputError('Quantidade de famílias inválida.')
        added = 0
        with self.session_factory.begin() as session:
            # Serialize imports against this event, avoiding concurrent duplicate races.
            settings = session.scalar(select(EventSettings).where(EventSettings.id == 1).with_for_update())
            if settings is None:
                raise RuntimeError('Configuração da festa não inicializada.')
            existing = {row.external_key: row for row in session.scalars(select(InvitedFamily)).all()}
            for row in records:
                key = row['key']
                values = (row['name'], row['phone'], row['adults'], row['young'], row['older'])
                old = existing.get(key)
                if old is not None:
                    current = (old.contact_name, old.phone, old.adults,
                               old.children_0_5, old.children_6_12)
                    if current != values:
                        raise InputError('Uma família já cadastrada possui dados diferentes. Corrija o arquivo antes de importar.')
                    continue
                session.add(InvitedFamily(
                    id=str(uuid.uuid4()), external_key=key, contact_name=row['name'],
                    phone=row['phone'], adults=row['adults'],
                    children_0_5=row['young'], children_6_12=row['older'], status='PENDING'
                ))
                added += 1
            session.flush()
        return {'imported': added, 'existing_unchanged': len(records) - added, 'total_in_file': len(records)}

    def invited_family_summary(self) -> dict:
        with self.session_factory() as session:
            records = session.scalars(select(InvitedFamily).order_by(InvitedFamily.external_key)).all()
            return {'families': len(records),
                    'pending': sum(row.status == 'PENDING' for row in records),
                    'adults': sum(row.adults for row in records),
                    'children_0_5': sum(row.children_0_5 for row in records),
                    'children_6_12': sum(row.children_6_12 for row in records)}

    def _authorized(self, session: Session, family_id: str, edit_token: str, lock: bool = False) -> Family:
        if not isinstance(edit_token, str) or len(edit_token) != 64:
            raise AccessDenied('Acesso não autorizado.')
        query = select(Family).where(Family.id == family_id)
        if lock:
            query = query.with_for_update()
        family = session.scalar(query)
        if family is None or not hmac.compare_digest(family.edit_token_hash,
                                                       sha256(edit_token.encode()).hexdigest()):
            raise AccessDenied('Acesso não autorizado.')
        return family

    def get_own(self, family_id: str, edit_token: str) -> dict:
        with self.session_factory() as session:
            family = self._authorized(session, family_id, edit_token)
            settings = session.get(EventSettings, 1)
            if settings is None:
                raise RuntimeError('Configuração do evento não inicializada.')
            return {**_family_public(family), 'venue': settings.venue or 'Local a confirmar',
                    'edit_deadline_utc': _to_aware(settings.edit_deadline_utc),
                    'can_edit': can_edit(datetime.now(timezone.utc), _to_aware(settings.edit_deadline_utc))}

    def update(self, family_id: str, edit_token: str, expected_revision: int,
               data: RsvpInput, now_utc: datetime | Callable[[], datetime]) -> RsvpReceipt:
        if type(expected_revision) is not int or expected_revision <= 0 or not isinstance(data, RsvpInput):
            raise InputError('Revisão ou resposta inválida.')
        with self.session_factory.begin() as session:
            settings = session.scalar(select(EventSettings).where(EventSettings.id == 1).with_for_update())
            if settings is None:
                raise RuntimeError('Configuração do evento não inicializada.')
            family = self._authorized(session, family_id, edit_token, lock=True)
            # HTTP requests provide a clock: lock waits must not freeze the cutoff check.
            decision_time = now_utc() if callable(now_utc) else now_utc
            if not can_edit(decision_time, _to_aware(settings.edit_deadline_utc)):
                raise EditClosed('Prazo de edição encerrado.')
            if family.revision != expected_revision:
                raise RevisionConflict('Os dados foram alterados em outra aba.')
            family.contact_name = data.contact_name
            family.attending = data.attending
            family.revision += 1
            family.participants.clear()
            session.flush()
            family.participants.extend(
                Participant(position=pos, name=p.name, kind=p.kind, age_years=p.age_years)
                for pos, p in enumerate(data.participants))
            session.flush()
            session.add(AuditEvent(event_kind='RSVP_UPDATED',
                                   occurred_at_utc=_utc_naive(decision_time)))
            receipt = self._receipt(family, edit_token)
        return receipt

    def configure(self, venue: str | None, deadline_utc: datetime | None, now_utc: datetime) -> None:
        recorded_at = _utc_naive(now_utc)
        if venue is not None and (not isinstance(venue, str) or len(venue) > 240):
            raise InputError('Local inválido.')
        deadline = _utc_naive(deadline_utc) if deadline_utc is not None else None
        with self.session_factory.begin() as session:
            settings = session.scalar(select(EventSettings).where(EventSettings.id == 1).with_for_update())
            if settings is None:
                raise RuntimeError('Configuração do evento não inicializada.')
            normalized_venue = venue.strip() if venue else None
            changed = (settings.venue != normalized_venue or settings.edit_deadline_utc != deadline)
            settings.venue = normalized_venue
            settings.edit_deadline_utc = deadline
            if changed:
                session.add(AuditEvent(event_kind='SETTINGS_CHANGED',
                                       occurred_at_utc=recorded_at))

    def recent_activity(self, limit: int = 50) -> list[dict]:
        """Retorna somente tipo e horário, sem nomes, identificadores ou segredos."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('O histórico permite de 1 a 100 eventos.')
        with self.session_factory() as session:
            entries = session.scalars(
                select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
            ).all()
            return [
                {'kind': event.event_kind,
                 'occurred_at_utc': _to_aware(event.occurred_at_utc).isoformat()}
                for event in entries
            ]

    def settings(self) -> dict:
        with self.session_factory() as session:
            row = session.get(EventSettings, 1)
            if row is None:
                raise RuntimeError('Configuração do evento não inicializada.')
            return {'venue': row.venue, 'edit_deadline_utc': _to_aware(row.edit_deadline_utc),
                    'buffet_limit': row.buffet_limit}

    def summary(self) -> dict:
        with self.session_factory() as session:
            settings = session.get(EventSettings, 1)
            if settings is None:
                raise RuntimeError('Configuração do evento não inicializada.')
            confirmed: list[dict] = []
            declined: list[dict] = []
            children: list[dict] = []
            aggregate = Counts(0, 0, 0, 0, 0)
            for family in session.scalars(select(Family).order_by(Family.contact_name, Family.id)).all():
                record = _family_public(family)
                if not family.attending:
                    declined.append(record)
                    continue
                confirmed.append(record)
                people = [ParticipantInput(p.name, p.kind, p.age_years) for p in family.participants]
                count = count_participants(people)
                aggregate = Counts(*(a + b for a, b in zip(asdict(aggregate).values(), asdict(count).values())))
                for p in family.participants:
                    if p.kind == 'CHILD':
                        children.append({'name': p.name, 'age_years': p.age_years, 'family_id': family.id})
            return {'counts': aggregate, 'confirmed': confirmed, 'declined': declined,
                    'souvenir_children': children, 'buffet_limit': settings.buffet_limit,
                    'buffet_limit_reached': aggregate.buffet >= settings.buffet_limit}
