"""Guest pages must be phone-first and contain no private organizer data."""
from app import create_app
from tests.integration.test_public_api import store


def test_guest_page_is_public_and_contains_rsvp_form(store):
    app = create_app({"TESTING": True, "RSVP_STORE": store, "API_RATE_LIMIT": 0})
    response = app.test_client().get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Isadora" in html
    assert 'id="rsvp-form"' in html
    assert 'name="attendance"' in html
    assert 'id="participants"' in html
    assert 'id="review"' in html
    assert 'id="success"' in html


def test_edit_page_is_available_without_token_in_server_url(store):
    app = create_app({"TESTING": True, "RSVP_STORE": store, "API_RATE_LIMIT": 0})
    response = app.test_client().get("/editar")
    assert response.status_code == 200
    assert 'id="rsvp-form"' in response.get_data(as_text=True)


def test_public_assets_never_expose_buffet_rules(store):
    app = create_app({"TESTING": True, "RSVP_STORE": store, "API_RATE_LIMIT": 0})
    client = app.test_client()
    for path in ("/", "/editar", "/static/guest.js", "/static/site.css"):
        response = client.get(path)
        assert response.status_code == 200
        data = response.get_data(as_text=True).lower()
        assert "buffet_limit" not in data
        assert "limite de 40" not in data
        assert "critério de cobrança" not in data
