"""Calendário público do evento, sem dados pessoais de convidados."""
from datetime import datetime, timezone
import re


def ics_text(value):
    """Escapa dados de campo de texto em iCalendar (RFC 5545)."""
    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    return clean.replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n") \
        .replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def calendar_ics(name, starts_at, venue):
    when = starts_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # No attendee, phone, password, edit token or private identifier in output.
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Isadora//Convites//PT-BR",
        "CALSCALE:GREGORIAN", "BEGIN:VEVENT",
        "UID:isadora-dois-anos-20261213@convites",
        "DTSTAMP:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "DTSTART:" + when,
        "SUMMARY:" + ics_text(name),
        "LOCATION:" + ics_text(venue),
        "DESCRIPTION:Convite para celebrar os 2 aninhos da Isadora.",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")
