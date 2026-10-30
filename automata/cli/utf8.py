"""UTF-8 console stream configuration for the presentation layer."""

from __future__ import annotations

from typing import TextIO


def configure_utf8(stream: TextIO) -> None:
    """Reconfigure ``stream`` to UTF-8 when it exposes ``reconfigure``.

    Real console streams (``sys.stdout``) support ``reconfigure``; in-memory
    streams such as ``io.StringIO`` do not, so the helper is a safe no-op there.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
