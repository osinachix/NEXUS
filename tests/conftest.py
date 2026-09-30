import ipaddress as _ipaddress
import socket as _socket
import sys
from pathlib import Path

import pytest

# Allow `import main` from tests/ regardless of the working directory pytest
# is invoked from. main.py lives at the repo root, not in an installed
# package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tool_policy  # noqa: E402  (import after sys.path fix-up above)


@pytest.fixture
def fake_dns(monkeypatch):
    """Deterministic, offline-safe stand-in for DNS resolution used by
    tool_policy's SSRF check. Real DNS lookups would make the security test
    suite depend on network access and be non-deterministic; this fixture
    lets tests declare exactly what a hostname "resolves" to.

    Usage: fake_dns({"example.com": ["93.184.216.34"]})
    A hostname with no configured record raises socket.gaierror, matching
    real getaddrinfo's behavior for an unresolvable name -- EXCEPT that an
    already-literal IP address (e.g. "127.0.0.1", "::1") always resolves to
    itself without needing a registered record, exactly like real
    getaddrinfo (which parses a literal IP locally, no network query).
    """

    def _configure(hosts_to_ips: dict[str, list[str]]):
        def _getaddrinfo(host, *args, **kwargs):
            try:
                _ipaddress.ip_address(host)
                ips = [host]
            except ValueError:
                if host not in hosts_to_ips:
                    raise _socket.gaierror(f"no fake DNS record for {host!r}")
                ips = hosts_to_ips[host]
            results = []
            for ip in ips:
                family = _socket.AF_INET6 if ":" in ip else _socket.AF_INET
                sockaddr = (ip, 0, 0, 0) if family == _socket.AF_INET6 else (ip, 0)
                results.append((family, _socket.SOCK_STREAM, 6, "", sockaddr))
            return results

        monkeypatch.setattr(tool_policy.socket, "getaddrinfo", _getaddrinfo)

    return _configure
