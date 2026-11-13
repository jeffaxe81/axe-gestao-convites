"""100.000 cenários unitários determinísticos, sem rede ou banco de dados.

Cada iteração executa uma validação independente e pelo menos uma asserção.
Não confundir com 100.000 testes pytest coletados ou com carga HTTP.
"""
from datetime import datetime, timedelta, timezone
import random

import pytest

from app.domain import (
    Counts, InputError, ParticipantInput, can_edit,
    count_participants, validate_rsvp,
)


def test_100000_deterministic_domain_cases():
    rng = random.Random(20261112)
    checked = 0
    epoch = datetime(2026, 12, 1, tzinfo=timezone.utc)

    # 25.000 confirmações válidas, incluindo normalização e participantes.
    for i in range(25_000):
        age = rng.randrange(13)
        contact = f"Convidado {i}"
        result = validate_rsvp({
            "contact_name": f"  {contact}  ",
            "attending": True,
            "participants": [
                {"name": contact, "kind": "OVER_12", "age_years": None},
                {"name": f"Criança {i}", "kind": "CHILD", "age_years": age},
            ],
        })
        assert result.contact_name == contact
        assert result.participants[1].age_years == age
        checked += 1

    # 25.000 contagens verificadas por fórmula independente.
    for _ in range(25_000):
        ages = [rng.randrange(13) for _ in range(rng.randrange(0, 16))]
        adults = rng.randrange(0, 16)
        people = [ParticipantInput("C", "CHILD", age) for age in ages]
        people += [ParticipantInput("A", "OVER_12", None) for _ in range(adults)]
        young = len([age for age in ages if age <= 5])
        assert count_participants(people) == Counts(
            total=len(ages) + adults,
            buffet=len(ages) + adults - young,
            children_0_5=young,
            children_0_12=len(ages),
            over_12=adults,
        )
        checked += 1

    # 25.000 limites temporais, inclusive igualdade exata.
    for _ in range(25_000):
        delta_us = rng.randrange(-1_000_000, 1_000_001)
        deadline = epoch + timedelta(days=rng.randrange(31))
        now = deadline + timedelta(microseconds=delta_us)
        assert can_edit(now, deadline) is (delta_us < 0)
        checked += 1

    # 25.000 idades inválidas, inclusive bool, float, str e limites.
    bad_ages = [None, -1, 13, True, False, 1.5, "5", [], {}]
    for i in range(25_000):
        age = bad_ages[i % len(bad_ages)]
        with pytest.raises(InputError):
            validate_rsvp({
                "contact_name": "Principal",
                "attending": True,
                "participants": [{"name": "Principal", "kind": "CHILD", "age_years": age}],
            })
        checked += 1

    assert checked == 100_000
