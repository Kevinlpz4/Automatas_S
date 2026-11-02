"""Raw-text automaton loader sharing the frozen phase-1 pipeline.

This service accepts already-decoded ``str`` text and never performs file I/O.
It mirrors :class:`automata.services.cargador.JsonAutomatonLoader` exactly:
parse, stage-1 structure validation, stage-2 semantics only when stage 1 is
clean, then model construction.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from automata.models.errores import (
    DomainError,
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


class MalformedJsonTextError(MalformedJsonError):
    """Malformed JSON received as decoded text instead of from a file.

    Subclasses :class:`MalformedJsonError` so existing API error handling can
    catch it, but carries no filesystem path and a pathless Spanish message.
    """

    def __init__(self) -> None:
        self.path: None = None
        DomainError.__init__(self, "El texto no contiene un JSON válido.")


class JsonAutomatonTextLoader:
    """Load an automaton definition from already-decoded JSON text."""

    def load_text(self, text: str) -> Automaton:
        """Parse and validate ``text``, returning a frozen model."""
        parsed = self._parse_json(text)

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
    def _parse_json(text: str) -> ParsedJson:
        """Parse JSON text, mapping syntax failures to a pathless domain error."""
        try:
            return parse_json_text(text)
        except json.JSONDecodeError:
            raise MalformedJsonTextError() from None
