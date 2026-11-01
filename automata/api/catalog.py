"""Bundled example catalog for the API.

Only the four whitelisted fixtures are exposed. Names are checked before any
filesystem access, and file text is decoded from raw bytes so line endings and
spaces are preserved exactly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "ejemplos"
WHITELIST: tuple[str, ...] = (
    "afd_ejemplo.json",
    "afd_incompleto.json",
    "afn_ejemplo.json",
    "afn_lambda_ejemplo.json",
)


class ExampleNotFoundError(Exception):
    """Raised when an example is missing or outside the whitelist."""

    codigo = "EJEMPLO_NO_ENCONTRADO"

    def __init__(self, nombre: str) -> None:
        self.nombre = nombre
        self.mensaje = f"No se encontró el ejemplo '{nombre}'."
        super().__init__(self.mensaje)


@dataclass(frozen=True, slots=True)
class ExampleEntry:
    """One catalog item: filename plus the type declared in its JSON content."""

    nombre: str
    tipo: str


class ExampleCatalog:
    """Read the bundled examples through an explicit whitelist."""

    def __init__(
        self,
        directory: Path = EXAMPLES_DIR,
        whitelist: tuple[str, ...] = WHITELIST,
    ) -> None:
        self._directory = directory
        self._whitelist = tuple(whitelist)

    def list_examples(self) -> tuple[ExampleEntry, ...]:
        """Return the whitelisted examples sorted by filename."""
        entries: list[ExampleEntry] = []
        for nombre in sorted(self._whitelist):
            text = self._read_whitelisted(nombre)
            payload = json.loads(text)
            entries.append(
                ExampleEntry(
                    nombre=nombre,
                    tipo=str(payload["tipo"]),
                )
            )
        return tuple(entries)

    def read(self, nombre: str) -> str:
        """Return the exact UTF-8 text for a whitelisted example."""
        return self._read_whitelisted(nombre)

    def _read_whitelisted(self, nombre: str) -> str:
        if nombre not in self._whitelist:
            raise ExampleNotFoundError(nombre)
        if "/" in nombre or "\\" in nombre or ".." in nombre:
            raise ExampleNotFoundError(nombre)

        candidate = (self._directory / nombre).resolve()
        if candidate.parent != self._directory.resolve():
            raise ExampleNotFoundError(nombre)

        try:
            return candidate.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            raise ExampleNotFoundError(nombre) from None
