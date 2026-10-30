"""Domain error hierarchy with stable codes and Spanish messages.

Every error carries a `code` and a human-readable `message`; `str(error)`
returns only the message so presentation layers can render diagnostics without
leaking native exceptions or tracebacks.
"""

from __future__ import annotations

from pathlib import Path

from automata.models.validacion import ValidationIssue


class DomainError(Exception):
    """Base class for every expected, user-facing failure in the domain."""

    code: str

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidAutomatonDefinition(DomainError):
    """The JSON document parsed correctly but failed domain validation."""

    code = "INVALID_AUTOMATON_DEFINITION"

    def __init__(self, errors: tuple[ValidationIssue, ...]) -> None:
        self.errors = tuple(errors)
        super().__init__("La definición del autómata no es válida.")


class AutomatonFileNotFoundError(DomainError):
    """The requested automaton file does not exist."""

    code = "AUTOMATON_FILE_NOT_FOUND"

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"No se encontró el archivo '{path}'.")


class AutomatonFileReadError(DomainError):
    """The automaton file exists but could not be read as UTF-8 text."""

    code = "AUTOMATON_FILE_READ_ERROR"

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"No se pudo leer el archivo '{path}'.")


class MalformedJsonError(DomainError):
    """The automaton file does not contain valid JSON."""

    code = "MALFORMED_JSON"

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"El archivo '{path}' no contiene un JSON válido.")
