"""Reject iCalendar line injection while keeping escaped user newlines."""
from datetime import datetime, timezone
from app.calendar import ics_text, calendar_ics


def test_text_preserves_newlines_as_rfc5545_escapes_not_actual_lines():
    value = "Salão; Flores, Rua X\nBEGIN:VEVENT\nACCESS:PRIVATE"
    result = ics_text(value)
    assert result == r"Salão\; Flores\, Rua X\nBEGIN:VEVENT\nACCESS:PRIVATE"
    assert "\n" not in result
    assert "\r" not in result


def test_calendar_has_only_one_event_despite_untrusted_venue_newlines():
    venue = "Auditado\r\nBEGIN:VEVENT\r\nX-HIJACK:1"
    event = calendar_ics("Aniversário", datetime(2026, 12, 13, 15, tzinfo=timezone.utc), venue).decode("utf-8")
    assert event.count("\r\nBEGIN:VEVENT\r\n") == 1
    assert r"Auditado\nBEGIN:VEVENT\nX-HIJACK:1" in event
    assert "\r\nX-HIJACK:1" not in event
