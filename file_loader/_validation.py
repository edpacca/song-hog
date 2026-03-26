import ipaddress
import re
import socket
import unicodedata
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlparse

# ------------------------------------------------------------------
# Protocol — used to type-hint config parameters without importing
# ServiceConfig (which would create a circular dependency).
# ------------------------------------------------------------------

class _ConfigProtocol(Protocol):
    input_url_base: str
    expected_host: str
    scheme: str
    max_url_length: int
    file_id_re: re.Pattern[str]


# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

_INVALID_URL_ERROR = "Invalid URL"

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # loopback
    ipaddress.ip_network("10.0.0.0/8"),        # private
    ipaddress.ip_network("172.16.0.0/12"),     # private
    ipaddress.ip_network("192.168.0.0/16"),    # private
    ipaddress.ip_network("169.254.0.0/16"),    # link-local / cloud metadata
    ipaddress.ip_network("100.64.0.0/10"),     # shared address space (RFC 6598)
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]

# Default file ID allowlist used when no config is supplied (backward compat).
_DEFAULT_FILE_ID_RE = re.compile(r"^[a-zA-Z0-9\-]+$")


# ------------------------------------------------------------------
# SSRF prevention
# ------------------------------------------------------------------

def _resolves_to_private_ip(hostname: str) -> bool:
    """Return True if any resolved address for hostname is in a blocked range."""
    try:
        results = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return True  # unresolvable — treat as blocked
    for result in results:
        addr = result[4][0]
        try:
            ip = ipaddress.ip_address(addr)
            if any(ip in net for net in _BLOCKED_NETWORKS):
                return True
        except ValueError:
            return True  # unparseable address — treat as blocked
    return False


# ------------------------------------------------------------------
# URL validation
# ------------------------------------------------------------------

def validate_url(config: _ConfigProtocol, url: str) -> None:
    """
    Validate that url is a well-formed URL for the given service config.
    Raises ValueError(_INVALID_URL_ERROR) on any failure.
    Fail-fast: no attempt is made to repair malformed input.
    """
    # 1. Length cap
    if len(url) > config.max_url_length:
        raise ValueError(_INVALID_URL_ERROR)

    # 2. Parse — reject if urlparse cannot produce a usable result
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError()
    except Exception:
        raise ValueError(_INVALID_URL_ERROR)

    # 3. Scheme allowlist
    if parsed.scheme != config.scheme:
        raise ValueError(_INVALID_URL_ERROR)

    # 4. Host must match exactly (no subdomains, no IP literals)
    if parsed.netloc != config.expected_host:
        raise ValueError(_INVALID_URL_ERROR)

    # 5. Directory traversal — check raw path and all decoded forms
    raw_path = parsed.path
    decoded_once = unquote(raw_path)
    decoded_twice = unquote(decoded_once)
    for path_form in (raw_path, decoded_once, decoded_twice):
        if ".." in path_form or "//" in path_form:
            raise ValueError(_INVALID_URL_ERROR)

    # 6. Path must contain a non-empty ID segment
    if not raw_path.lstrip("/"):
        raise ValueError(_INVALID_URL_ERROR)

    # 7. SSRF — block any URL whose hostname resolves to a private/internal IP
    if _resolves_to_private_ip(parsed.hostname):
        raise ValueError(_INVALID_URL_ERROR)


# ------------------------------------------------------------------
# ID extraction
# ------------------------------------------------------------------

def extract_file_id(
    base_url: str,
    url: str,
    *,
    file_id_re: re.Pattern = _DEFAULT_FILE_ID_RE,
) -> str:
    """
    Extract and validate the file ID from a service URL.

    The two-argument form (base_url, url) is the backward-compatible signature
    used by existing tests.  Callers that have a ServiceConfig should pass
    file_id_re=config.file_id_re to use the service-specific allowlist.

    Raises ValueError(_INVALID_URL_ERROR) on any failure.
    """
    parts = url.split(base_url)
    if len(parts) < 2 or not parts[1]:
        raise ValueError(_INVALID_URL_ERROR)

    raw_id = parts[1].split("?")[0]

    # Normalise unicode to collapse homoglyphs before the allowlist check
    normalised = unicodedata.normalize("NFKC", raw_id)

    # Strict allowlist — % is not in the set, so %2F, %252F etc. are all rejected
    if not file_id_re.match(normalised):
        raise ValueError(_INVALID_URL_ERROR)

    return normalised


# ------------------------------------------------------------------
# Filename sanitisation
# ------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    """Strip path components and replace non-safe characters with underscores."""
    name = Path(name).name  # strip any directory traversal
    return re.sub(r"[^\w\-.]", "_", name)
