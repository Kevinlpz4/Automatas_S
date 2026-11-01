"""Stable API V-code mapping for phase-1 validation issues.

The map is immutable and contains exactly V01-V18. ``INVALID_ROOT`` is kept
symbolic and passes through ``api_codigo`` unchanged, as does any future code.
API messages are never duplicated here: ``api_error`` reuses the exact Spanish
message carried by the phase-1 ``ValidationIssue``.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping

from automata.models.validacion import (
    DUPLICATE_ELEMENT,
    DUPLICATE_TRANSITION,
    EMPTY_ALPHABET,
    EMPTY_STATES,
    FINAL_NOT_IN_STATES,
    INITIAL_NOT_IN_STATES,
    INVALID_AFD_TARGET,
    INVALID_AFN_TARGET,
    INVALID_ALPHABET_SYMBOL,
    INVALID_FIELD_TYPE,
    INVALID_TIPO,
    LAMBDA_FORBIDDEN,
    LAMBDA_IN_ALPHABET,
    MISSING_FIELD,
    MISSING_TIPO,
    SYMBOL_NOT_IN_ALPHABET,
    UNKNOWN_DESTINATION_STATE,
    UNKNOWN_TRANSITION_STATE,
    ValidationIssue,
)

V_CODE_MAP: Final[Mapping[str, str]] = MappingProxyType(
    {
        MISSING_TIPO: "V01",
        INVALID_TIPO: "V02",
        MISSING_FIELD: "V03",
        INVALID_FIELD_TYPE: "V04",
        INVALID_ALPHABET_SYMBOL: "V05",
        DUPLICATE_ELEMENT: "V06",
        EMPTY_STATES: "V07",
        INITIAL_NOT_IN_STATES: "V08",
        FINAL_NOT_IN_STATES: "V09",
        EMPTY_ALPHABET: "V10",
        UNKNOWN_TRANSITION_STATE: "V11",
        UNKNOWN_DESTINATION_STATE: "V12",
        SYMBOL_NOT_IN_ALPHABET: "V13",
        LAMBDA_FORBIDDEN: "V14",
        INVALID_AFD_TARGET: "V15",
        DUPLICATE_TRANSITION: "V16",
        LAMBDA_IN_ALPHABET: "V17",
        INVALID_AFN_TARGET: "V18",
    }
)


def api_codigo(code: str) -> str:
    """Return the API V-code for a phase-1 issue code."""
    return V_CODE_MAP.get(code, code)


def api_error(issue: ValidationIssue) -> dict[str, str]:
    """Build one API error item without copying or rewriting its message."""
    return {"codigo": api_codigo(issue.code), "mensaje": issue.message}
