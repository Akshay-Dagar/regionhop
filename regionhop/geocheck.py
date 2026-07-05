"""Verify which country a SOCKS5 proxy exits from.

Uses a tiny built-in SOCKS5 client (no third-party deps, no `curl`) to fetch
ip-api.com through the tunnel and read back the country.
"""

from __future__ import annotations

import json
import socket
import struct

GEO_HOST = "ip-api.com"
GEO_PATH = "/json/?fields=country,countryCode,query"


class GeoError(Exception):
    """Raised when the exit country cannot be determined."""


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise GeoError("SOCKS5 connection closed unexpectedly.")
        buf += chunk
    return buf


def socks5_http_get(
    proxy_port: int,
    host: str,
    path: str,
    proxy_host: str = "127.0.0.1",
    timeout: float = 12.0,
) -> bytes:
    """Perform an HTTP/1.1 GET to host:80/path through a SOCKS5 proxy."""
    sock = socket.create_connection((proxy_host, proxy_port), timeout=timeout)
    try:
        sock.settimeout(timeout)
        # Greeting: SOCKS5, one method, "no authentication".
        sock.sendall(b"\x05\x01\x00")
        if _recv_exact(sock, 2) != b"\x05\x00":
            raise GeoError("SOCKS5 proxy rejected the no-auth handshake.")

        # CONNECT to host:80 by domain name.
        host_bytes = host.encode("idna")
        request = (
            b"\x05\x01\x00\x03" + bytes([len(host_bytes)]) + host_bytes + struct.pack(">H", 80)
        )
        sock.sendall(request)

        reply = _recv_exact(sock, 4)
        if reply[1] != 0x00:
            raise GeoError(f"SOCKS5 CONNECT failed (reply code {reply[1]}).")
        atyp = reply[3]
        if atyp == 0x01:  # IPv4
            _recv_exact(sock, 4)
        elif atyp == 0x03:  # domain
            length = _recv_exact(sock, 1)[0]
            _recv_exact(sock, length)
        elif atyp == 0x04:  # IPv6
            _recv_exact(sock, 16)
        _recv_exact(sock, 2)  # bound port

        http = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "User-Agent: regionhop\r\n"
            "Accept: application/json\r\n"
            "Connection: close\r\n\r\n"
        )
        sock.sendall(http.encode("ascii"))

        chunks: list[bytes] = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
        return b"".join(chunks)
    finally:
        sock.close()


def parse_ipapi_response(raw: bytes) -> dict:
    """Extract the JSON object from an HTTP response body."""
    _, _, body = raw.partition(b"\r\n\r\n")
    body = body.strip()
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        start = body.find(b"{")
        end = body.rfind(b"}")
        if start != -1 and end > start:
            return json.loads(body[start : end + 1])
        raise GeoError("Could not parse the geolocation response.") from None


def exit_country(proxy_port: int, timeout: float = 12.0) -> dict:
    """Return e.g. ``{"country": "Brazil", "countryCode": "BR", "query": "1.2.3.4"}``."""
    raw = socks5_http_get(proxy_port, GEO_HOST, GEO_PATH, timeout=timeout)
    return parse_ipapi_response(raw)
