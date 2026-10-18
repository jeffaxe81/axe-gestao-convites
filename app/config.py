"""Dados públicos estáveis do evento. Local configurável em banco na release 1."""
from datetime import datetime
from zoneinfo import ZoneInfo

EVENT_NAME = "Aniversário de 2 anos da Isadora"
EVENT_STARTS_AT = datetime(2026, 12, 13, 15, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
EVENT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_VENUE = "Local a confirmar"
BUFFET_LIMIT = 40  # restrito à área de organizadores
