import socket

import pytest

from app.services.net_guard import validate_public_https


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/hook",
        "https://127.0.0.1/hook",
        "https://169.254.169.254/latest",
        "https://localhost/hook",
        "https://10.1.1.1/hook",
    ],
)
def test_rejects_non_public_webhook(url: str):
    with pytest.raises(ValueError):
        validate_public_https(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@example.com/hook",
        "https://example.com:8443/hook",
        "https://db.internal/hook",
        "https://printer.local/hook",
    ],
)
def test_rejects_userinfo_port_and_local_suffixes(url: str):
    with pytest.raises(ValueError):
        validate_public_https(url)


def test_accepts_public_host(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", port or 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    assert validate_public_https("https://example.com/hook") == "https://example.com/hook"


def test_rejects_mixed_public_and_private_answers(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", port or 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", port or 443)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ValueError):
        validate_public_https("https://example.com/hook")
