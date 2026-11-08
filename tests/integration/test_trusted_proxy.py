"""Allow proxy client IP only when an explicitly trusted reverse proxy is configured."""
from app import create_app
from tests.integration.test_public_api import store


def make_client(store, hops):
    app = create_app({
        "TESTING": True,
        "RSVP_STORE": store,
        "API_RATE_LIMIT": 1,
        "TRUSTED_PROXY_HOPS": hops,
        "SECRET_KEY": "proxy-test-session-secret",
    })
    return app.test_client()


def guest_request(client, ip):
    return client.get(
        "/api/rsvps/11111111-1111-4111-8111-111111111111",
        headers={"X-Forwarded-For": ip},
        environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
    )


def test_untrusted_forwarded_ip_header_cannot_bypass_rate_limit(store):
    client = make_client(store, 0)
    assert guest_request(client, "203.0.113.10").status_code == 401
    # Header is untrusted, so the request's actual remote address is still used.
    assert guest_request(client, "198.51.100.20").status_code == 429


def test_single_trusted_proxy_distinguishes_two_guests(store):
    client = make_client(store, 1)
    assert guest_request(client, "203.0.113.10").status_code == 401
    assert guest_request(client, "198.51.100.20").status_code == 401
    assert guest_request(client, "203.0.113.10").status_code == 429


def test_more_than_one_trusted_proxy_hop_is_rejected(store):
    try:
        make_client(store, 5)
    except (ValueError, RuntimeError):
        return
    raise AssertionError("Trusting five forwarding hops is not supported.")
