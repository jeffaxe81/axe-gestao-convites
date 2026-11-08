"""Normalização rígida da origem da aplicação, inclusive no runtime.

A checagem manual de preflight não basta: um .env editado depois deve ser
rejeitado ao iniciar, antes de aceitar sessões/convites.
"""
import ipaddress
import re
from urllib.parse import urlsplit

HOSTNAME = re.compile(
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z"
)
RESERVED = (".local", ".internal", ".test", ".example", ".invalid", ".localhost")
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
LOCAL_PORT = 8080


def configured_origin(value: str) -> tuple[str, str]:
    """Retorna (esquema, hostname) ou falha com erro sem imprimir a URL."""
    try:
        if not isinstance(value, str) or not value:
            raise ValueError()
        parsed = urlsplit(value)
        host = parsed.hostname
        if not host or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError()
        if parsed.path not in ("", "/"):
            raise ValueError()
        if parsed.scheme == "http":
            if host not in LOCAL_HOSTS or parsed.port != LOCAL_PORT:
                raise ValueError()
        elif parsed.scheme == "https":
            if parsed.port is not None or not HOSTNAME.fullmatch(host) or host.endswith(RESERVED):
                raise ValueError()
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError()
        else:
            raise ValueError()
        return parsed.scheme, host
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "APP_PUBLIC_URL inválida: use domínio HTTPS sem porta ou "
            "http://127.0.0.1:8080 somente no host local."
        ) from None
