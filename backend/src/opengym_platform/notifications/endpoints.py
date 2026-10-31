"""Subscription URL checks; no DNS lookup or outbound connection at registration."""

import ipaddress
import os
import socket
from urllib.parse import urlsplit


def private_address(value):
    address = ipaddress.ip_address(value)
    for entry in os.environ.get("ALLOWED_PRIVATE_IPS", "").replace(",", " ").split():
        try:
            if "-" in entry:
                low, high = (ipaddress.ip_address(part) for part in entry.split("-", 1))
                if (
                    address.version == low.version == high.version
                    and low <= address <= high
                ):
                    return False
            elif address in ipaddress.ip_network(entry, strict=False):
                return False
        except ValueError:
            continue
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return private_address(address.ipv4_mapped)
    if address.version == 6:
        return (
            address in ipaddress.ip_network("fc00::/7")
            or address in ipaddress.ip_network("fe80::/10")
            or int(address) <= 1
        )
    return any(
        address in ipaddress.ip_network(block)
        for block in (
            "0.0.0.0/8",
            "10.0.0.0/8",
            "127.0.0.0/8",
            "169.254.0.0/16",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "192.0.0.0/16",
            "100.64.0.0/10",
            "224.0.0.0/3",
        )
    )


def endpoint_error(raw):
    try:
        url = urlsplit(raw)
        if (
            not url.hostname
            or url.port == 0
            or any(c.isspace() or ord(c) < 32 for c in raw)
            or "\\" in raw
        ):
            return "endpoint is not a valid URL"
        if url.scheme != "https":
            return "endpoint must be an https:// URL"
        if url.username or url.password:
            return "endpoint must not carry credentials"
        host = url.hostname
        if "%" in host:
            return "endpoint is not a valid URL"
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            try:
                literal = ipaddress.ip_address(socket.inet_aton(host))
            except OSError:
                return None
        if private_address(literal):
            return "endpoint must not point at a private address"
    except (ValueError, UnicodeError):
        return "endpoint is not a valid URL"
    return None
