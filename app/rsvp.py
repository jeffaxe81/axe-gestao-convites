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
from app.models import AuditEvent, EventSettings, Family, Participant, InvitedFamily, InvitationResponse, InvitationDispatch, InvitationInterest


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

    def invitation_token(self, invitation_id: str) -> str:
        """Stable HMAC capability; plaintext links are not stored in the database."""
        return hmac.new(self._secret, ('invitation:v1:' + invitation_id).encode(), sha256).hexdigest()

    def _invitation_submission_key(self, invitation_id: str) -> str:
        # Cannot be preempted via the public /api/rsvps idempotency namespace.
        return hmac.new(self._secret,
                        ('invitation-submission:v1:' + invitation_id).encode(),
                        sha256).hexdigest()

    def _invitation(self, session: Session, invitation_id: str, token: str, lock=False) -> InvitedFamily:
        if (not isinstance(invitation_id, str) or not isinstance(token, str)
                or len(token) != 64 or any(c not in '0123456789abcdef' for c in token)):
            raise AccessDenied('Convite inválido.')
        expected = self.invitation_token(invitation_id)
        if not hmac.compare_digest(expected, token):
            raise AccessDenied('Convite inválido.')
        query = select(InvitedFamily).where(InvitedFamily.id == invitation_id)
        if lock:
            query = query.with_for_update()
        invited = session.scalar(query)
        if invited is None:
            raise AccessDenied('Convite inválido.')
        return invited

    def get_invitation(self, invitation_id: str, token: str) -> dict:
        with self.session_factory() as session:
            invited = self._invitation(session, invitation_id, token)
            mapping = session.get(InvitationResponse, invited.id)
            result = {
                'contact_name': invited.contact_name,
                'adults': invited.adults,
                'children_0_5': invited.children_0_5,
                'children_6_12': invited.children_6_12,
                'responded': mapping is not None,
                'interested': session.get(InvitationInterest, invited.id) is not None,
            }
            if mapping:
                family = session.get(Family, mapping.family_id)
                if family is None:
                    raise RuntimeError('Resposta da família indisponível.')
                result['receipt'] = asdict(self._receipt(
                    family, self._edit_token(self._invitation_submission_key(invited.id))))
            return result

    def express_invitation_interest(self, invitation_id: str, token: str,
                                    now_utc: datetime) -> dict:
        """An explicit visitor action, idempotent; no passive tracking or IP storage."""
        recorded_at = _utc_naive(now_utc)
        with self.session_factory.begin() as session:
            invited = self._invitation(session, invitation_id, token, lock=True)
            interest = session.get(InvitationInterest, invited.id)
            if interest is None:
                interest = InvitationInterest(invited_family_id=invited.id,
                                              expressed_at_utc=recorded_at)
                session.add(interest)
                session.add(AuditEvent(event_kind='INVITATION_INTEREST',
                                       occurred_at_utc=recorded_at))
            return {'interested': True}

    def invitation_roster(self) -> list[dict]:
        """Private organizer export source only; bearer tokens never enter public lists."""
        with self.session_factory() as session:
            invited_rows = session.scalars(select(InvitedFamily).order_by(InvitedFamily.external_key)).all()
            response_rows = {x.invited_family_id: x.family_id
                             for x in session.scalars(select(InvitationResponse)).all()}
            response_families = {x.id: x.attending for x in
                session.scalars(select(Family).where(Family.id.in_(response_rows.values()))).all()
            } if response_rows else {}
            output = []
            for invited in invited_rows:
                family_id = response_rows.get(invited.id)
                status = ('PENDENTE' if not family_id else
                          'CONFIRMADO' if response_families.get(family_id) else 'RECUSADO')
                output.append({'key': invited.external_key,
                               'name': invited.contact_name,
                               'phone': invited.phone,
                               'status': status,
                               'id': invited.id,
                               'token': self.invitation_token(invited.id)})
            return output

    def invitation_overview(self) -> dict:
        """Authenticated roster: RSVP state and manually asserted sending are distinct."""
        rows = self.invitation_roster()
        with self.session_factory() as session:
            sent_at = {entry.invited_family_id: entry.marked_at_utc
                       for entry in session.scalars(select(InvitationDispatch)).all()}
            interest_at = {entry.invited_family_id: entry.expressed_at_utc
                           for entry in session.scalars(select(InvitationInterest)).all()}
        families = [
            {**{key: row[key] for key in ('id', 'key', 'name', 'phone', 'status')},
             'interested': row['id'] in interest_at,
             'interested_at_utc': _to_aware(interest_at[row['id']]).isoformat() if row['id'] in interest_at else None,
             'sent': row['id'] in sent_at,
             'sent_at_utc': _to_aware(sent_at[row['id']]).isoformat()
             if row['id'] in sent_at else None}
            for row in rows
        ]
        return {
            'families': families,
            'counts': {
                'total': len(families),
                'pending': sum(row['status'] == 'PENDENTE' for row in families),
                'confirmed': sum(row['status'] == 'CONFIRMADO' for row in families),
                'declined': sum(row['status'] == 'RECUSADO' for row in families),
                'sent': sum(row['sent'] for row in families),
                'not_sent': sum(not row['sent'] for row in families),
                'interested': sum(row['interested'] for row in families),
            },
        }

    def mark_invitation_sent(self, invitation_id: str, sent: bool,
                             now_utc: datetime) -> dict:
        """Log an operator's manual assertion, never an inferred delivery status.

        Idempotent and reversible; the RSVP and invitation tokens are unaffected.
        """
        if type(sent) is not bool:
            raise InputError('Informe sent como verdadeiro ou falso.')
        try:
            parsed_id = str(uuid.UUID(invitation_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise InputError('Identificador da família inválido.') from exc
        marked_at = _utc_naive(now_utc)
        with self.session_factory.begin() as session:
            settings = session.scalar(
                select(EventSettings).where(EventSettings.id == 1).with_for_update())
            if settings is None:
                raise RuntimeError('Configuração da festa não inicializada.')
            if session.get(InvitedFamily, parsed_id) is None:
                raise InputError('Família não encontrada.')
            previous = session.get(InvitationDispatch, parsed_id)
            if sent and previous is None:
                previous = InvitationDispatch(
                    invited_family_id=parsed_id, marked_at_utc=marked_at)
                session.add(previous)
                session.add(AuditEvent(event_kind='INVITATION_SENT_MARKED',
                                       occurred_at_utc=marked_at))
                session.flush()
            elif not sent and previous is not None:
                session.delete(previous)
                session.add(AuditEvent(event_kind='INVITATION_SENT_UNMARKED',
                                       occurred_at_utc=marked_at))
                session.flush()
                previous = None
            return {'sent': previous is not None,
                    'sent_at_utc': (_to_aware(previous.marked_at_utc).isoformat()
                                    if previous else None)}

    def invitation_share_link(self, invitation_id: str, public_origin: str) -> str:
        """Return one link to an authenticated organizer; never list all tokens."""
        try:
            parsed_id = str(uuid.UUID(invitation_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise InputError('Identificador da família inválido.') from exc
        with self.session_factory() as session:
            invited = session.get(InvitedFamily, parsed_id)
            if invited is None:
                raise InputError('Família não encontrada.')
        return (public_origin.rstrip('/') + '/convite#' + parsed_id + '.' +
                self.invitation_token(parsed_id))

    def respond_to_invitation(self, invitation_id: str, token: str,
                              data: RsvpInput, now_utc: datetime) -> RsvpReceipt:
        if not isinstance(data, RsvpInput):
            raise InputError('Dados de confirmação inválidos.')
        recorded_at = _utc_naive(now_utc)
        # Deterministic idempotency: repeat of the same invite/response returns
        # the same editing capability, even after a lost HTTP reply.
        submission_key = self._invitation_submission_key(invitation_id)
        key_hash = self._key_hash(submission_key)
        edit_token = self._edit_token(submission_key)
        digest = sha256(_input_bytes(data)).hexdigest()
        with self.session_factory.begin() as session:
            invited = self._invitation(session, invitation_id, token, lock=True)
            existing = session.get(InvitationResponse, invited.id)
            if existing:
                family = session.get(Family, existing.family_id)
                if family is None or family.revision != 1 or not hmac.compare_digest(family.payload_hash, digest):
                    raise RevisionConflict('Esta família já respondeu. Use o link de edição.')
                return self._receipt(family, edit_token)
            family = Family(id=str(uuid.uuid4()), contact_name=data.contact_name,
                            attending=data.attending, revision=1,
                            submission_key_hash=key_hash, payload_hash=digest,
                            edit_token_hash=sha256(edit_token.encode()).hexdigest())
            session.add(family)
            session.flush()
            family.participants = [Participant(position=pos, name=p.name,
                kind=p.kind, age_years=p.age_years) for pos, p in enumerate(data.participants)]
            session.add(InvitationResponse(invited_family_id=invited.id, family_id=family.id))
            invited.status = 'CONFIRMED' if data.attending else 'DECLINED'
            session.add(AuditEvent(event_kind='RSVP_CREATED' if data.attending else 'RSVP_DECLINED',
                                   occurred_at_utc=recorded_at))
            session.flush()
            return self._receipt(family, edit_token)

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
            linked_invitation = session.scalar(
                select(InvitationResponse).where(InvitationResponse.family_id == family.id))
            if linked_invitation:
                invited = session.get(InvitedFamily, linked_invitation.invited_family_id)
                if invited:
                    invited.status = 'CONFIRMED' if data.attending else 'DECLINED'
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
