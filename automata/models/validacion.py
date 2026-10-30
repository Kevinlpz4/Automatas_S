"""Two-stage pure validation and model construction for automaton JSON documents.

Stage 1 inspects structure and JSON types and accumulates every issue. Stage 2
inspects semantics and only runs once stage 1 is clean. Both stages are pure:
they never raise and never perform I/O.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from automata.models.json_estructura import JsonObject
from automata.models.tipos import AFD, AFN, NFALambda, Automaton, TipoAutomata

# --- issue codes -----------------------------------------------------------

INVALID_ROOT = "INVALID_ROOT"
MISSING_TIPO = "MISSING_TIPO"
INVALID_TIPO = "INVALID_TIPO"
MISSING_FIELD = "MISSING_FIELD"
INVALID_FIELD_TYPE = "INVALID_FIELD_TYPE"
INVALID_ALPHABET_SYMBOL = "INVALID_ALPHABET_SYMBOL"
DUPLICATE_ELEMENT = "DUPLICATE_ELEMENT"
EMPTY_STATES = "EMPTY_STATES"
INITIAL_NOT_IN_STATES = "INITIAL_NOT_IN_STATES"
FINAL_NOT_IN_STATES = "FINAL_NOT_IN_STATES"
EMPTY_ALPHABET = "EMPTY_ALPHABET"
UNKNOWN_TRANSITION_STATE = "UNKNOWN_TRANSITION_STATE"
UNKNOWN_DESTINATION_STATE = "UNKNOWN_DESTINATION_STATE"
SYMBOL_NOT_IN_ALPHABET = "SYMBOL_NOT_IN_ALPHABET"
LAMBDA_FORBIDDEN = "LAMBDA_FORBIDDEN"
INVALID_AFD_TARGET = "INVALID_AFD_TARGET"
DUPLICATE_TRANSITION = "DUPLICATE_TRANSITION"
LAMBDA_IN_ALPHABET = "LAMBDA_IN_ALPHABET"
INVALID_AFN_TARGET = "INVALID_AFN_TARGET"

LAMBDA = "λ"
STAGE_STRUCTURE = 1
STAGE_SEMANTICS = 2

REQUIRED_FIELDS = ("estados", "alfabeto", "inicial", "finales", "transiciones")
VALID_TIPO_VALUES = tuple(tipo.value for tipo in TipoAutomata)

_TYPE_LIST = "lista"
_TYPE_STRING = "string"
_TYPE_OBJECT = "objeto"

_MISSING = object()


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A single validation defect with a stable code and Spanish message."""

    code: str
    message: str
    field: str | None
    stage: int


# --- rendering helpers -----------------------------------------------------


def _plain(value: object) -> object:
    """Convert JSON metadata wrappers to builtin values for rendering."""
    if isinstance(value, JsonObject):
        return value.to_plain()
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _render(value: object) -> str:
    """Render any JSON value inside a message without ever raising."""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(
            _plain(value),
            ensure_ascii=False,
            sort_keys=True,
            default=repr,
        )
    except (TypeError, ValueError):
        return repr(value)


def _issue(code: str, message: str, field: str | None) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, field=field, stage=STAGE_STRUCTURE)


def _semantic_issue(code: str, message: str, field: str | None) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, field=field, stage=STAGE_SEMANTICS)


# --- equality-only helpers -------------------------------------------------


def _repeats(values: Sequence[object]) -> list[object]:
    """Return each value that appears more than once, in first-repeat order.

    Equality scans are used instead of hashing so unhashable JSON values
    (objects, arrays) can never crash the scan.
    """
    repeated: list[object] = []
    for index, value in enumerate(values):
        if any(value == previous for previous in values[:index]):
            if not any(value == known for known in repeated):
                repeated.append(value)
    return repeated


def _pairs_of(node: object) -> tuple[tuple[object, object], ...]:
    """Return every raw key/value occurrence of a JSON object node."""
    if isinstance(node, JsonObject):
        return node.pairs
    if isinstance(node, Mapping):
        return tuple(node.items())
    return ()


# --- stage 1: structure ----------------------------------------------------


def validate_structure(raw: object) -> tuple[ValidationIssue, ...]:
    """Validate structure and JSON types, accumulating every issue (V01–V07)."""
    if not isinstance(raw, Mapping):
        return (
            _issue(
                INVALID_ROOT,
                "El documento JSON debe ser un objeto.",
                None,
            ),
        )

    issues: list[ValidationIssue] = []

    tipo_value = raw.get("tipo", _MISSING)
    tipo: TipoAutomata | None = None
    if tipo_value is _MISSING:
        issues.append(
            _issue(
                MISSING_TIPO,
                "Falta el campo obligatorio 'tipo'.",
                "tipo",
            )
        )
    elif isinstance(tipo_value, str) and tipo_value in VALID_TIPO_VALUES:
        tipo = TipoAutomata(tipo_value)
    else:
        issues.append(
            _issue(
                INVALID_TIPO,
                f"El tipo '{_render(tipo_value)}' no es válido; "
                "usá 'AFD', 'AFN' o 'AFN-λ'.",
                "tipo",
            )
        )

    estados = raw.get("estados", _MISSING)
    alfabeto = raw.get("alfabeto", _MISSING)
    inicial = raw.get("inicial", _MISSING)
    finales = raw.get("finales", _MISSING)
    transiciones = raw.get("transiciones", _MISSING)

    issues.extend(_validate_estados(estados))
    issues.extend(_validate_alfabeto(alfabeto))
    issues.extend(_validate_inicial(inicial))
    issues.extend(_validate_finales(finales))
    issues.extend(_validate_transiciones(transiciones, tipo))

    return tuple(issues)


def _validate_estados(value: object) -> list[ValidationIssue]:
    if value is _MISSING:
        return [_missing_field("estados")]
    if not isinstance(value, list):
        return [_invalid_type("estados", _TYPE_LIST)]

    issues: list[ValidationIssue] = [
        _invalid_type(f"estados[{index}]", _TYPE_STRING)
        for index, element in enumerate(value)
        if not isinstance(element, str)
    ]
    if not value:
        issues.append(
            _issue(
                EMPTY_STATES,
                "La lista 'estados' no puede estar vacía.",
                "estados",
            )
        )
    issues.extend(_duplicate_issues(value, "estados"))
    return issues


def _validate_alfabeto(value: object) -> list[ValidationIssue]:
    if value is _MISSING:
        return [_missing_field("alfabeto")]
    if not isinstance(value, list):
        return [_invalid_type("alfabeto", _TYPE_LIST)]

    issues: list[ValidationIssue] = [
        _issue(
            INVALID_ALPHABET_SYMBOL,
            f"El símbolo '{_render(element)}' del alfabeto debe tener "
            "exactamente 1 carácter.",
            f"alfabeto[{index}]",
        )
        for index, element in enumerate(value)
        if not isinstance(element, str) or len(element) != 1
    ]
    issues.extend(_duplicate_issues(value, "alfabeto"))
    return issues


def _validate_inicial(value: object) -> list[ValidationIssue]:
    if value is _MISSING:
        return [_missing_field("inicial")]
    if not isinstance(value, str):
        return [_invalid_type("inicial", _TYPE_STRING)]
    return []


def _validate_finales(value: object) -> list[ValidationIssue]:
    if value is _MISSING:
        return [_missing_field("finales")]
    if not isinstance(value, list):
        return [_invalid_type("finales", _TYPE_LIST)]

    issues: list[ValidationIssue] = [
        _invalid_type(f"finales[{index}]", _TYPE_STRING)
        for index, element in enumerate(value)
        if not isinstance(element, str)
    ]
    issues.extend(_duplicate_issues(value, "finales"))
    return issues


def _validate_transiciones(
    value: object,
    tipo: TipoAutomata | None,
) -> list[ValidationIssue]:
    if value is _MISSING:
        return [_missing_field("transiciones")]
    if not isinstance(value, Mapping):
        return [_invalid_type("transiciones", _TYPE_OBJECT)]

    issues: list[ValidationIssue] = []
    for origen, destinos in value.items():
        if not isinstance(destinos, Mapping):
            issues.append(_invalid_type(f"transiciones[{origen!r}]", _TYPE_OBJECT))
            continue
        # Destination-list duplicates are AFN/AFN-λ only (design §5.3). An AFD
        # list target is V15's job in stage 2.
        if tipo not in (TipoAutomata.AFN, TipoAutomata.AFN_LAMBDA):
            continue
        for simbolo, destino in destinos.items():
            if not isinstance(destino, list):
                continue
            issues.extend(
                _duplicate_issues(
                    destino,
                    f"transiciones[{origen!r}][{simbolo!r}]",
                )
            )
    return issues


def _missing_field(field: str) -> ValidationIssue:
    return _issue(
        MISSING_FIELD,
        f"Falta el campo obligatorio '{field}'.",
        field,
    )


def _invalid_type(field: str, expected: str) -> ValidationIssue:
    return _issue(
        INVALID_FIELD_TYPE,
        f"El campo '{field}' debe ser de tipo {expected}.",
        field,
    )


def _duplicate_issues(values: Sequence[object], field: str) -> list[ValidationIssue]:
    return [
        _issue(
            DUPLICATE_ELEMENT,
            f"El valor '{_render(value)}' está duplicado en '{field}'.",
            field,
        )
        for value in _repeats(values)
    ]


# --- stage 2: semantics ----------------------------------------------------


def validate_semantics(
    raw: Mapping[str, object],
    tipo: TipoAutomata,
) -> tuple[ValidationIssue, ...]:
    """Validate semantics, accumulating every issue (V08–V18).

    Preconditions are guaranteed by stage 1 success. The fixed order is:
    V08, V09, V10, V11, V17, V14, then V15/V18 → V12 → V13 per transition,
    and V16 last so every occurrence is counted from the raw pairs.
    """
    issues: list[ValidationIssue] = []
    estados = cast(list[str], raw["estados"])
    alfabeto = cast(list[str], raw["alfabeto"])
    inicial = cast(str, raw["inicial"])
    finales = cast(list[str], raw["finales"])
    transiciones = cast(Mapping[str, Mapping[str, object]], raw["transiciones"])

    if inicial not in estados:
        issues.append(
            _semantic_issue(
                INITIAL_NOT_IN_STATES,
                f"El estado inicial '{_render(inicial)}' no pertenece a 'estados'.",
                "inicial",
            )
        )

    for index, final in enumerate(finales):
        if final not in estados:
            issues.append(
                _semantic_issue(
                    FINAL_NOT_IN_STATES,
                    f"El estado final '{_render(final)}' no pertenece a 'estados'.",
                    f"finales[{index}]",
                )
            )

    if not alfabeto:
        issues.append(
            _semantic_issue(
                EMPTY_ALPHABET,
                "El alfabeto no puede estar vacío.",
                "alfabeto",
            )
        )

    for origen in transiciones:
        if origen not in estados:
            issues.append(
                _semantic_issue(
                    UNKNOWN_TRANSITION_STATE,
                    f"El estado '{_render(origen)}' de 'transiciones' "
                    "no pertenece a 'estados'.",
                    f"transiciones[{origen!r}]",
                )
            )

    for index, simbolo in enumerate(alfabeto):
        if simbolo == LAMBDA:
            issues.append(
                _semantic_issue(
                    LAMBDA_IN_ALPHABET,
                    "El símbolo 'λ' no puede formar parte del alfabeto.",
                    f"alfabeto[{index}]",
                )
            )

    if tipo is TipoAutomata.AFD:
        for origen, simbolos in transiciones.items():
            if LAMBDA in simbolos:
                issues.append(
                    _semantic_issue(
                        LAMBDA_FORBIDDEN,
                        "El símbolo 'λ' no está permitido en las transiciones de un AFD.",
                        f"transiciones[{origen!r}]['λ']",
                    )
                )

    for origen, simbolos in transiciones.items():
        for simbolo, destino in simbolos.items():
            field = f"transiciones[{origen!r}][{simbolo!r}]"
            issues.extend(_validate_target(tipo, destino, estados, field))
            if not _lambda_exempt(tipo, simbolo, alfabeto) and simbolo not in alfabeto:
                issues.append(
                    _semantic_issue(
                        SYMBOL_NOT_IN_ALPHABET,
                        f"El símbolo '{_render(simbolo)}' no pertenece al alfabeto.",
                        field,
                    )
                )

    issues.extend(_duplicate_transition_issues(transiciones))
    return tuple(issues)


def _validate_target(
    tipo: TipoAutomata,
    destino: object,
    estados: Sequence[object],
    field: str,
) -> list[ValidationIssue]:
    """Apply V15/V18 shape checks then V12 membership checks for one target."""
    if tipo is TipoAutomata.AFD:
        if not isinstance(destino, str):
            return [
                _semantic_issue(
                    INVALID_AFD_TARGET,
                    "Cada transición de un AFD debe apuntar a un único estado.",
                    field,
                )
            ]
        return _destination_membership(destino, estados, field)

    if not isinstance(destino, list):
        return [
            _semantic_issue(
                INVALID_AFN_TARGET,
                "Cada transición de un AFN debe apuntar a una lista de estados.",
                field,
            )
        ]

    issues: list[ValidationIssue] = []
    for index, element in enumerate(destino):
        issues.extend(_destination_membership(element, estados, f"{field}[{index}]"))
    return issues


def _destination_membership(
    destino: object,
    estados: Sequence[object],
    field: str,
) -> list[ValidationIssue]:
    if destino in estados:
        return []
    return [
        _semantic_issue(
            UNKNOWN_DESTINATION_STATE,
            f"El estado destino '{_render(destino)}' no pertenece a 'estados'.",
            field,
        )
    ]


def _lambda_exempt(tipo: TipoAutomata, simbolo: object, alfabeto: Sequence[object]) -> bool:
    """V13 never reports λ when V17/V14 own it or when λ is a valid NFALambda key."""
    if simbolo != LAMBDA:
        return False
    return (
        tipo is TipoAutomata.AFD
        or tipo is TipoAutomata.AFN_LAMBDA
        or LAMBDA in alfabeto
    )


def _duplicate_transition_issues(
    transiciones: Mapping[str, object],
) -> list[ValidationIssue]:
    """V16: report one issue for every extra `(estado, símbolo)` occurrence."""
    issues: list[ValidationIssue] = []
    seen: list[tuple[object, object]] = []
    for origen, simbolos in _pairs_of(transiciones):
        if not isinstance(simbolos, Mapping):
            continue
        for simbolo, _destino in _pairs_of(simbolos):
            pair = (origen, simbolo)
            if any(pair == previous for previous in seen):
                issues.append(
                    _semantic_issue(
                        DUPLICATE_TRANSITION,
                        f"Transición duplicada para el par "
                        f"('{_render(origen)}', '{_render(simbolo)}').",
                        f"transiciones[{origen!r}][{simbolo!r}]",
                    )
                )
            seen.append(pair)
    return issues


# --- model construction ----------------------------------------------------


def build_automaton(raw: Mapping[str, object]) -> Automaton:
    """Build a frozen model from a document that already passed both stages.

    Only known top-level keys are read, so unknown fields are ignored (O5).
    Insertion order is preserved and AFN destination lists become tuples.
    """
    tipo = TipoAutomata(cast(str, raw["tipo"]))
    estados = tuple(cast(Iterable[str], raw["estados"]))
    alfabeto = tuple(cast(Iterable[str], raw["alfabeto"]))
    inicial = cast(str, raw["inicial"])
    finales = frozenset(cast(Iterable[str], raw["finales"]))
    raw_transiciones = cast(Mapping[str, Mapping[str, object]], raw["transiciones"])

    if tipo is TipoAutomata.AFD:
        transiciones_afd = {
            origen: {
                simbolo: cast(str, destino)
                for simbolo, destino in simbolos.items()
            }
            for origen, simbolos in raw_transiciones.items()
        }
        return AFD(
            estados=estados,
            alfabeto=alfabeto,
            inicial=inicial,
            finales=finales,
            transiciones=transiciones_afd,
        )

    transiciones_afn = {
        origen: {
            simbolo: tuple(cast(Iterable[str], destino))
            for simbolo, destino in simbolos.items()
        }
        for origen, simbolos in raw_transiciones.items()
    }
    model = AFN if tipo is TipoAutomata.AFN else NFALambda
    return model(
        estados=estados,
        alfabeto=alfabeto,
        inicial=inicial,
        finales=finales,
        transiciones=transiciones_afn,
    )
