"""The shape of an origin: the one parser behind ``--allow-origin`` and the check of a request's ``Origin`` header."""

import re

_ORIGIN = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.\-]*)://"
    r"(?P<host>[A-Za-z0-9._~\-]+|\[[0-9A-Fa-f:.]+\])"
    r"(?::(?P<port>[0-9]{1,5}))?"
)
_MAX_PORT = 65535


def normalize_origin(value: str) -> str | None:
    """Return the canonical form of ``value``, or ``None`` when it is not exactly ``scheme://host[:port]``.

    The scheme and the host are lower-cased; nothing else is changed. ``*``, ``null``, a path, a trailing slash,
    a user name and a port above 65535 are not origins.
    """
    match = _ORIGIN.fullmatch(value)
    if match is None:
        return None
    port = match.group("port")
    if port is not None and int(port) > _MAX_PORT:
        return None
    suffix = "" if port is None else f":{port}"
    return f"{match.group('scheme').lower()}://{match.group('host').lower()}{suffix}"


__all__ = ["normalize_origin"]
