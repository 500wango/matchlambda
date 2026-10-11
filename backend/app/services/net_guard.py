import asyncio
import ipaddress
import json
import socket
import ssl
from typing import Any, Dict, Optional
from urllib.parse import urlsplit


_BLOCKED_HOSTS = {
    "localhost",
    "metadata",
    "metadata.google.internal",
}


class PublicHttpResponse:
    def __init__(self, status_code: int, body: bytes):
        self.status_code = status_code
        self.content = body

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


def _split_public_https(url: str) -> tuple[str, str, int, str]:
    """Return hostname, pinned global IP, port and request target.

    The caller must connect to the pinned IP. Resolving the name again at
    request time would reopen a DNS-rebinding window.
    """
    parsed = urlsplit((url or "").strip())
    if parsed.username or parsed.password:
        raise ValueError("URL must not include userinfo.")
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if parsed.scheme != "https" or not host:
        raise ValueError("URL must use https and include a host.")
    port = parsed.port or 443
    if port != 443:
        raise ValueError("URL must use port 443.")
    if host in _BLOCKED_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError("Host is not public.")

    try:
        ipaddress.ip_address(host)
        addresses = [host]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError("Host did not resolve.") from exc
        addresses = []
        for info in infos:
            ip_text = info[4][0]
            if ip_text not in addresses:
                addresses.append(ip_text)

    if not addresses:
        raise ValueError("Host did not resolve.")

    pinned = None
    for raw_ip in addresses:
        ip = ipaddress.ip_address(raw_ip)
        if not ip.is_global:
            raise ValueError("Host resolves to a non-public address.")
        if pinned is None:
            pinned = raw_ip
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return host, pinned, port, path


def validate_public_https(url: str) -> str:
    """Accept only https URLs whose host resolves to public addresses."""
    _split_public_https(url)
    return (url or "").strip()


def _read_http_response(tls: ssl.SSLSocket, limit: int = 1_000_000) -> PublicHttpResponse:
    chunks = []
    size = 0
    while True:
        data = tls.recv(65536)
        if not data:
            break
        chunks.append(data)
        size += len(data)
        if size > limit:
            break
    raw = b"".join(chunks)
    head, _, body = raw.partition(b"\r\n\r\n")
    status_line = head.split(b"\r\n", 1)[0].decode("latin-1", errors="replace")
    parts = status_line.split(" ")
    status_code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return PublicHttpResponse(status_code, body[:8192])


def _sync_post_pinned(
    host: str,
    ip: str,
    port: int,
    path: str,
    body: bytes,
    timeout: float,
) -> PublicHttpResponse:
    context = ssl.create_default_context()
    sock = socket.create_connection((ip, port), timeout=timeout)
    tls = context.wrap_socket(sock, server_hostname=host)
    try:
        tls.settimeout(timeout)
        header = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "User-Agent: MatchLambda\r\n"
            "Accept: application/json\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        tls.sendall(header + body)
        return _read_http_response(tls)
    finally:
        tls.close()


async def post_public_https(
    url: str,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: float = 10.0,
) -> PublicHttpResponse:
    """POST JSON to a validated public https URL without following redirects.

    The TCP connection uses the IP checked in this call. TLS SNI stays the
    original hostname so the certificate still matches.
    """
    host, ip, port, path = _split_public_https(url)
    body = json.dumps(json_body or {}, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return await asyncio.to_thread(_sync_post_pinned, host, ip, port, path, body, timeout)
