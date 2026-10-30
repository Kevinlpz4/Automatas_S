"""JSON file loader for automaton definitions.

This is the only service allowed to perform file I/O. Every low-level failure
is mapped to a specific ``DomainError`` so presentation layers never see native
exceptions or tracebacks.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from automata.models.errores import (
    AutomatonFileNotFoundError,
    AutomatonFileReadError,
    InvalidAutomatonDefinition,
    MalformedJsonError,
)
from automata.models.json_estructura import ParsedJson, parse_json_text
from automata.models.tipos import Automaton, TipoAutomata
from automata.models.validacion import (
    build_automaton,
    validate_semantics,
    validate_structure,
)


class JsonAutomatonLoader:
    """Load an automaton definition from a UTF-8 JSON file."""

    def load(self, path: Path) -> Automaton:
        """Read, parse and validate ``path``, returning a frozen model."""
        text = self._read_text(path)
        parsed = self._parse_json(text, path)

        issues = validate_structure(parsed.value)
        if issues:
            raise InvalidAutomatonDefinition(tuple(issues))

        # Stage 1 guarantees an object root with a valid ``tipo`` discriminator.
        raw = cast(Mapping[str, object], parsed.value)
        tipo = TipoAutomata(cast(str, raw["tipo"]))

        issues = validate_semantics(raw, tipo)
        if issues:
            raise InvalidAutomatonDefinition(tuple(issues))

        return build_automaton(raw)

    @staticmethod
    def _read_text(path: Path) -> str:
        """Read UTF-8 text, mapping filesystem failures to domain errors."""
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise AutomatonFileNotFoundError(path) from None
        except (UnicodeDecodeError, OSError):
            raise AutomatonFileReadError(path) from None

    @staticmethod
    def _parse_json(text: str, path: Path) -> ParsedJson:
        """Parse JSON text, mapping syntax failures to a domain error."""
        try:
            return parse_json_text(text)
        except json.JSONDecodeError:
            raise MalformedJsonError(path) from None
