"""Regras puras de confirmação de presença para o aniversário da Isadora.

Nenhuma regra interna de buffet deve ser exposta na API pública.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Sequence


class InputError(ValueError):
    """Dados de confirmação inválidos."""


@dataclass(frozen=True)
class ParticipantInput:
    name: str
    kind: Literal["CHILD", "OVER_12"]
    age_years: int | None = None


@dataclass(frozen=True)
class RsvpInput:
    contact_name: str
    attending: bool
    participants: tuple[ParticipantInput, ...]


@dataclass(frozen=True)
class Counts:
    total: int
    buffet: int
    children_0_5: int
    children_0_12: int
    over_12: int


def _name(raw: object) -> str:
    if not isinstance(raw, str):
        raise InputError("Informe um nome válido.")
    normalized = " ".join(raw.split())
    if not normalized or len(normalized) > 160:
        raise InputError("O nome deve ter de 1 a 160 caracteres.")
    return normalized


def _participant(raw: object) -> ParticipantInput:
    if not isinstance(raw, dict) or set(raw) - {"name", "kind", "age_years"}:
        raise InputError("Dados de participante inválidos.")
    name = _name(raw.get("name"))
    kind = raw.get("kind")
    age = raw.get("age_years")
    if kind == "CHILD":
        if type(age) is not int or not (0 <= age <= 12):
            raise InputError("Para criança, informe idade inteira entre 0 e 12.")
    elif kind == "OVER_12":
        if age is not None:
            raise InputError("Não informe idade para pessoas acima de 12 anos.")
    else:
        raise InputError("A faixa etária informada não é válida.")
    return ParticipantInput(name, kind, age)


def validate_rsvp(payload: object) -> RsvpInput:
    """Valida o contrato do convidado sem deduplicar homônimos.

    A posição 0 dos participantes é sempre o convidado principal.
    """
    if not isinstance(payload, dict) or set(payload) != {"contact_name", "attending", "participants"}:
        raise InputError("Confirmação deve incluir nome, presença e participantes.")
    contact = _name(payload["contact_name"])
    attending = payload["attending"]
    raw_participants = payload["participants"]
    if type(attending) is not bool or not isinstance(raw_participants, list):
        raise InputError("Presença ou participantes inválidos.")
    if len(raw_participants) > 100:
        raise InputError("Uma resposta pode conter até 100 participantes.")
    if not attending:
        if raw_participants:
            raise InputError("Recusas não podem incluir participantes.")
        return RsvpInput(contact, False, ())
    if not raw_participants:
        raise InputError("Inclua o convidado principal na confirmação.")
    participants = tuple(_participant(participant) for participant in raw_participants)
    if participants[0].name != contact:
        raise InputError("O primeiro participante deve ser o convidado principal.")
    return RsvpInput(contact, True, participants)


def count_participants(participants: Sequence[ParticipantInput]) -> Counts:
    """Calcula quantidades *somente* de participantes confirmados.

    Deve ser chamada apenas sobre uma resposta presente; recusas usam lista vazia.
    """
    total = len(participants)
    young = sum(person.kind == "CHILD" and person.age_years <= 5 for person in participants)
    children = sum(person.kind == "CHILD" for person in participants)
    over = sum(person.kind == "OVER_12" for person in participants)
    return Counts(total=total, buffet=total - young, children_0_5=young,
                  children_0_12=children, over_12=over)


def can_edit(now_utc: datetime, deadline_utc: datetime | None) -> bool:
    """A edição é válida antes (mas nunca no instante exato) do prazo."""
    if not isinstance(now_utc, datetime) or now_utc.utcoffset() is None:
        raise ValueError("Agora deve informar um instante com fuso horário.")
    if deadline_utc is None:
        return True
    if not isinstance(deadline_utc, datetime) or deadline_utc.utcoffset() is None:
        raise ValueError("Prazo deve informar um instante com fuso horário.")
    return now_utc < deadline_utc
