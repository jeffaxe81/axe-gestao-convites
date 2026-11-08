"""Calendar, metadata privacy, indexing restrictions and planning metrics."""
import csv
from datetime import datetime, timezone
import io

from tests.integration.test_public_api import store
from tests.integration.test_organizer_api import client, login


def test_calendar_event_is_downloadable_and_correct_timezone(client):
    result = client.get("/evento.ics")
    assert result.status_code == 200
    assert result.mimetype == "text/calendar"
    assert "attachment" in result.headers["Content-Disposition"]
    assert "no-store" in result.headers["Cache-Control"]
    contents = result.get_data(as_text=True)
    assert contents.startswith("BEGIN:VCALENDAR\r\n")
    assert "BEGIN:VEVENT\r\n" in contents
    assert "DTSTART:20261213T180000Z\r\n" in contents
    assert "LOCATION:Local a confirmar\r\n" in contents
    assert "END:VCALENDAR\r\n" in contents
    assert "token" not in contents.lower()
    assert "participants" not in contents.lower()


def test_calendar_venue_escapes_untrusted_newlines(client, store):
    store.configure("Salão; Flores, Rua X\nBEGIN:VEVENT\nACCESS:PRIVATE",
                    None, datetime.now(timezone.utc))
    calendar = client.get("/evento.ics").get_data(as_text=True)
    assert "LOCATION:Salão\\; Flores\\, Rua X\\nBEGIN:VEVENT\\nACCESS:PRIVATE" in calendar
    assert calendar.count("\r\nBEGIN:VEVENT\r\n") == 1
    assert "ACCESS:PRIVATE" not in calendar.split("\r\n")


def test_robots_policy_and_noindex_headers(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "User-agent: *\nDisallow: /\n"
    for path in ("/", "/editar", "/api/event", "/health/live", "/evento.ics"):
        checked = client.get(path)
        assert "noindex" in checked.headers["X-Robots-Tag"]
        assert "nofollow" in checked.headers["X-Robots-Tag"]
        assert checked.headers["Cross-Origin-Opener-Policy"] == "same-origin"


def test_planning_csv_includes_age_six_to_twelve_without_names(client):
    from tests.integration.test_public_api import invitation, send
    send(client, invitation("Ana"))
    assert login(client).status_code == 200
    result = client.get("/api/admin/planning.csv")
    rows = list(csv.reader(io.StringIO(result.data.decode("utf-8-sig")), delimiter=";"))
    summary = dict(rows[1:])
    assert summary["Crianças de 6 a 12 anos"] == "1"
    assert summary["Crianças até 5 anos"] == "1"
    assert summary["Crianças até 12 anos / lembrancinhas"] == "2"
    assert "Ana" not in result.get_data(as_text=True)
