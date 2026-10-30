"""Pure validation tests: stage 1 structure, stage 2 semantics and model building."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest

from automata.models.json_estructura import parse_json_text
from automata.models.tipos import AFD, AFN, NFALambda, TipoAutomata
from automata.models.validacion import (
    ValidationIssue,
    build_automaton,
    validate_semantics,
    validate_structure,
)


# --- helpers ---------------------------------------------------------------


def _afd_raw() -> dict[str, object]:
    """A minimal well-formed AFD document."""
    return {
        "tipo": "AFD",
        "estados": ["q0", "q1"],
        "alfabeto": ["a", "b"],
        "inicial": "q0",
        "finales": ["q1"],
        "transiciones": {
            "q0": {"a": "q1", "b": "q0"},
            "q1": {"a": "q1", "b": "q0"},
        },
    }


def _afn_raw() -> dict[str, object]:
    """A minimal well-formed AFN document."""
    return {
        "tipo": "AFN",
        "estados": ["q0", "q1"],
        "alfabeto": ["a", "b"],
        "inicial": "q0",
        "finales": ["q1"],
        "transiciones": {
            "q0": {"a": ["q0", "q1"], "b": ["q0"]},
            "q1": {"a": ["q1"]},
        },
    }


def _afn_lambda_raw() -> dict[str, object]:
    """A minimal well-formed AFN-λ document (λ only as a transition key)."""
    return {
        "tipo": "AFN-λ",
        "estados": ["q0", "q1"],
        "alfabeto": ["a", "b"],
        "inicial": "q0",
        "finales": ["q1"],
        "transiciones": {
            "q0": {"a": ["q1"], "λ": ["q1"]},
            "q1": {"b": ["q1"]},
        },
    }


def _without(raw: Mapping[str, object], key: str) -> dict[str, object]:
    copy = dict(raw)
    del copy[key]
    return copy


def _codes(issues: tuple[ValidationIssue, ...]) -> tuple[str, ...]:
    return tuple(issue.code for issue in issues)


def _fields(issues: tuple[ValidationIssue, ...]) -> tuple[str | None, ...]:
    return tuple(issue.field for issue in issues)


def _tipo_of(raw: Mapping[str, object]) -> TipoAutomata:
    return TipoAutomata(raw["tipo"])


def _structure(raw: object) -> tuple[ValidationIssue, ...]:
    return validate_structure(raw)


# --- T07: stage 1 (structure) ---------------------------------------------


def test_validate_v01():
    """V01: a missing `tipo` yields MISSING_TIPO in stage 1."""
    issues = _structure(_without(_afd_raw(), "tipo"))

    assert len(issues) == 1
    issue = issues[0]
    assert issue.code == "MISSING_TIPO"
    assert issue.message == "Falta el campo obligatorio 'tipo'."
    assert issue.field == "tipo"
    assert issue.stage == 1


@pytest.mark.parametrize("tipo", ["DFA", "", 5, None])
def test_validate_v02(tipo):
    """V02: an unknown or non-string `tipo` yields INVALID_TIPO."""
    raw = _afd_raw()
    raw["tipo"] = tipo
    issues = _structure(raw)

    assert _codes(issues) == ("INVALID_TIPO",)
    issue = issues[0]
    assert issue.stage == 1
    assert issue.field == "tipo"
    assert "<tipo>" not in issue.message
    assert "usá 'AFD', 'AFN' o 'AFN-λ'" in issue.message


def test_validate_v03():
    """V03: each missing required field yields MISSING_FIELD for that field."""
    raw = _without(_afd_raw(), "alfabeto")
    issues = _structure(raw)

    assert _codes(issues) == ("MISSING_FIELD",)
    assert issues[0].field == "alfabeto"
    assert issues[0].message == "Falta el campo obligatorio 'alfabeto'."
    assert issues[0].stage == 1


def test_validate_v04():
    """V04: wrong JSON types are reported per container and per indexed element."""
    raw = _afd_raw()
    raw["estados"] = "q0"
    issues = _structure(raw)

    assert _codes(issues) == ("INVALID_FIELD_TYPE",)
    assert issues[0].field == "estados"
    assert issues[0].message == "El campo 'estados' debe ser de tipo lista."
    assert issues[0].stage == 1

    raw = _afd_raw()
    raw["estados"] = ["q0", 5]
    issues = _structure(raw)

    assert _codes(issues) == ("INVALID_FIELD_TYPE",)
    assert issues[0].field == "estados[1]"
    assert issues[0].message == "El campo 'estados[1]' debe ser de tipo string."

    raw = _afd_raw()
    raw["inicial"] = 3
    issues = _structure(raw)

    assert _codes(issues) == ("INVALID_FIELD_TYPE",)
    assert issues[0].field == "inicial"
    assert issues[0].message == "El campo 'inicial' debe ser de tipo string."

    raw = _afd_raw()
    raw["transiciones"] = []
    issues = _structure(raw)

    assert _codes(issues) == ("INVALID_FIELD_TYPE",)
    assert issues[0].field == "transiciones"
    assert issues[0].message == "El campo 'transiciones' debe ser de tipo objeto."


def test_validate_v05():
    """V05: every alphabet entry must be a one-character string."""
    raw = _afd_raw()
    raw["alfabeto"] = ["a", "ab"]
    issues = _structure(raw)

    assert _codes(issues) == ("INVALID_ALPHABET_SYMBOL",)
    assert issues[0].field == "alfabeto[1]"
    assert (
        issues[0].message
        == "El símbolo 'ab' del alfabeto debe tener exactamente 1 carácter."
    )
    assert issues[0].stage == 1


def test_validate_v06_duplicates():
    """V06: duplicates are detected in estados, alfabeto, finales and AFN targets."""
    raw = _afd_raw()
    raw["estados"] = ["q0", "q1", "q0"]
    issues = _structure(raw)
    assert _codes(issues) == ("DUPLICATE_ELEMENT",)
    assert issues[0].field == "estados"
    assert issues[0].message == "El valor 'q0' está duplicado en 'estados'."

    raw = _afd_raw()
    raw["alfabeto"] = ["a", "b", "a"]
    issues = _structure(raw)
    assert _codes(issues) == ("DUPLICATE_ELEMENT",)
    assert issues[0].field == "alfabeto"
    assert issues[0].message == "El valor 'a' está duplicado en 'alfabeto'."

    raw = _afd_raw()
    raw["finales"] = ["q1", "q1"]
    issues = _structure(raw)
    assert _codes(issues) == ("DUPLICATE_ELEMENT",)
    assert issues[0].field == "finales"
    assert issues[0].message == "El valor 'q1' está duplicado en 'finales'."

    raw = _afn_raw()
    raw["transiciones"] = {
        "q0": {"a": ["q0", "q1", "q0"], "b": ["q0"]},
        "q1": {"a": ["q1"]},
    }
    issues = _structure(raw)
    assert _codes(issues) == ("DUPLICATE_ELEMENT",)
    assert issues[0].field == "transiciones['q0']['a']"
    assert (
        issues[0].message
        == "El valor 'q0' está duplicado en 'transiciones['q0']['a']'."
    )
    assert issues[0].stage == 1


def test_validate_v06_duplicate_afn_lambda_destination():
    """V06 also applies to AFN-λ destination lists, including λ transitions."""
    raw = _afn_lambda_raw()
    raw["transiciones"] = {
        "q0": {"a": ["q1"], "λ": ["q1", "q1"]},
        "q1": {"b": ["q1"]},
    }

    issues = _structure(raw)

    assert _codes(issues) == ("DUPLICATE_ELEMENT",)
    assert issues[0].field == "transiciones['q0']['λ']"
    assert (
        issues[0].message
        == "El valor 'q1' está duplicado en 'transiciones['q0']['λ']'."
    )
    assert issues[0].stage == 1


def test_validate_v06_not_applied_to_afd_list():
    """V06 destination-list duplicates are AFN/AFN-λ only; AFD lists reach V15."""
    raw = _afd_raw()
    raw["transiciones"] = {"q0": {"a": ["q1"], "b": "q0"}, "q1": {"a": "q1"}}

    assert _structure(raw) == ()

    semantics = validate_semantics(raw, TipoAutomata.AFD)
    assert _codes(semantics) == ("INVALID_AFD_TARGET",)
    assert semantics[0].field == "transiciones['q0']['a']"


def test_validate_v07():
    """V07: an empty `estados` list is rejected."""
    raw = _afd_raw()
    raw["estados"] = []
    issues = _structure(raw)

    assert _codes(issues) == ("EMPTY_STATES",)
    assert issues[0].field == "estados"
    assert issues[0].message == "La lista 'estados' no puede estar vacía."
    assert issues[0].stage == 1


def test_validate_v05_exact_length():
    """V05 requires exactly one character; empty and two-character symbols fail."""
    raw = _afd_raw()
    raw["alfabeto"] = ["a", "ab", ""]
    issues = _structure(raw)

    assert _codes(issues) == ("INVALID_ALPHABET_SYMBOL", "INVALID_ALPHABET_SYMBOL")
    assert _fields(issues) == ("alfabeto[1]", "alfabeto[2]")
    assert (
        issues[1].message
        == "El símbolo '' del alfabeto debe tener exactamente 1 carácter."
    )

    raw = _afd_raw()
    raw["alfabeto"] = ["A"]
    raw["transiciones"] = {"q0": {"A": "q1"}, "q1": {"A": "q1"}}
    assert _structure(raw) == ()

    # λ satisfies V05 (one character); V17 rejects it in stage 2.
    raw = _afd_raw()
    raw["alfabeto"] = ["a", "λ"]
    assert _codes(_structure(raw)) == ()


def test_validation_accumulates_stage1():
    """R5: stage 1 accumulates every issue in the design §8.5 fixed order."""
    raw = {
        "tipo": "AFD",
        "estados": [],
        "alfabeto": ["a", "ab"],
        "finales": ["q1", "q1"],
        "transiciones": {},
    }

    issues = _structure(raw)

    assert _codes(issues) == (
        "EMPTY_STATES",
        "INVALID_ALPHABET_SYMBOL",
        "MISSING_FIELD",
        "DUPLICATE_ELEMENT",
    )
    assert _fields(issues) == ("estados", "alfabeto[1]", "inicial", "finales")
    assert all(issue.stage == 1 for issue in issues)


def test_validate_invalid_root():
    """Extension: a non-object root yields INVALID_ROOT and returns immediately."""
    issues = _structure([])

    assert len(issues) == 1
    issue = issues[0]
    assert issue.code == "INVALID_ROOT"
    assert issue.message == "El documento JSON debe ser un objeto."
    assert issue.field is None
    assert issue.stage == 1


# --- T08: stage 2 (semantics) ---------------------------------------------


def test_validate_v08():
    """V08: the initial state must belong to `estados`."""
    raw = _afd_raw()
    raw["inicial"] = "q9"

    issues = validate_semantics(raw, TipoAutomata.AFD)

    assert _codes(issues) == ("INITIAL_NOT_IN_STATES",)
    assert issues[0].field == "inicial"
    assert issues[0].stage == 2
    assert issues[0].message == "El estado inicial 'q9' no pertenece a 'estados'."


def test_validate_v09():
    """V09: every final state must belong to `estados`."""
    raw = _afd_raw()
    raw["finales"] = ["q1", "q9"]

    issues = validate_semantics(raw, TipoAutomata.AFD)

    assert _codes(issues) == ("FINAL_NOT_IN_STATES",)
    assert issues[0].field == "finales[1]"
    assert issues[0].stage == 2
    assert issues[0].message == "El estado final 'q9' no pertenece a 'estados'."


def test_validate_v10():
    """V10: an empty alphabet is rejected."""
    raw = _afd_raw()
    raw["alfabeto"] = []
    raw["transiciones"] = {}

    issues = validate_semantics(raw, TipoAutomata.AFD)

    assert _codes(issues) == ("EMPTY_ALPHABET",)
    assert issues[0].field == "alfabeto"
    assert issues[0].message == "El alfabeto no puede estar vacío."


def test_validate_v11():
    """V11: every transition origin must belong to `estados`."""
    raw = _afd_raw()
    raw["transiciones"] = {
        "q0": {"a": "q1", "b": "q0"},
        "q1": {"a": "q1", "b": "q0"},
        "q9": {"a": "q0"},
    }

    issues = validate_semantics(raw, TipoAutomata.AFD)

    assert _codes(issues) == ("UNKNOWN_TRANSITION_STATE",)
    assert issues[0].field == "transiciones['q9']"
    assert (
        issues[0].message
        == "El estado 'q9' de 'transiciones' no pertenece a 'estados'."
    )


def test_validate_v12():
    """V12: AFD targets and AFN list elements must belong to `estados`."""
    raw = _afd_raw()
    raw["transiciones"] = {"q0": {"a": "q9", "b": "q0"}, "q1": {"a": "q1"}}
    issues = validate_semantics(raw, TipoAutomata.AFD)

    assert _codes(issues) == ("UNKNOWN_DESTINATION_STATE",)
    assert issues[0].field == "transiciones['q0']['a']"
    assert issues[0].message == "El estado destino 'q9' no pertenece a 'estados'."

    raw = _afn_raw()
    raw["transiciones"] = {
        "q0": {"a": ["q0", "q9"], "b": ["q0"]},
        "q1": {"a": ["q1"]},
    }
    issues = validate_semantics(raw, TipoAutomata.AFN)

    assert _codes(issues) == ("UNKNOWN_DESTINATION_STATE",)
    assert issues[0].field == "transiciones['q0']['a'][1]"


def test_validate_v13():
    """V13: a non-λ transition symbol outside the alphabet is rejected."""
    raw = _afd_raw()
    raw["transiciones"] = {
        "q0": {"a": "q1", "b": "q0", "z": "q1"},
        "q1": {"a": "q1", "b": "q0"},
    }

    issues = validate_semantics(raw, TipoAutomata.AFD)

    assert _codes(issues) == ("SYMBOL_NOT_IN_ALPHABET",)
    assert issues[0].field == "transiciones['q0']['z']"
    assert issues[0].message == "El símbolo 'z' no pertenece al alfabeto."


def test_validate_v14():
    """V14: λ is forbidden as an AFD transition symbol."""
    raw = _afd_raw()
    raw["transiciones"] = {
        "q0": {"a": "q1", "b": "q0", "λ": "q1"},
        "q1": {"a": "q1", "b": "q0"},
    }

    issues = validate_semantics(raw, TipoAutomata.AFD)

    assert _codes(issues) == ("LAMBDA_FORBIDDEN",)
    assert issues[0].field == "transiciones['q0']['λ']"
    assert (
        issues[0].message
        == "El símbolo 'λ' no está permitido en las transiciones de un AFD."
    )


def test_validate_v15():
    """V15: an AFD target must be exactly a state string."""
    raw = _afd_raw()
    raw["transiciones"] = {"q0": {"a": ["q1"], "b": "q0"}, "q1": {"a": "q1"}}

    issues = validate_semantics(raw, TipoAutomata.AFD)

    assert _codes(issues) == ("INVALID_AFD_TARGET",)
    assert issues[0].field == "transiciones['q0']['a']"
    assert (
        issues[0].message
        == "Cada transición de un AFD debe apuntar a un único estado."
    )


@pytest.mark.parametrize("target", [["q1"], None, 3, {"estado": "q1"}])
def test_validate_v15_afd_target_strict(target):
    """V15 is strict: lists, null, numbers and objects are rejected, no V12."""
    raw = _afd_raw()
    raw["transiciones"] = {"q0": {"a": target, "b": "q0"}, "q1": {"a": "q1"}}

    issues = validate_semantics(raw, TipoAutomata.AFD)

    assert _codes(issues) == ("INVALID_AFD_TARGET",)
    assert issues[0].field == "transiciones['q0']['a']"
    assert "UNKNOWN_DESTINATION_STATE" not in _codes(issues)


def test_validate_v16():
    """V16: the first duplicate `(estado, símbolo)` pair is reported."""
    raw = parse_json_text(
        '{"tipo": "AFN-λ", "estados": ["q0", "q1"], "alfabeto": ["a", "b"],'
        ' "inicial": "q0", "finales": ["q1"], "transiciones": {'
        ' "q0": {"a": ["q1"], "λ": ["q1"], "λ": ["q0"]},'
        ' "q1": {"b": ["q1"]}}}'
    ).value

    issues = validate_semantics(cast(Mapping[str, object], raw), TipoAutomata.AFN_LAMBDA)

    assert _codes(issues) == ("DUPLICATE_TRANSITION",)
    assert issues[0].field == "transiciones['q0']['λ']"
    assert issues[0].message == "Transición duplicada para el par ('q0', 'λ')."


def test_validate_v16_duplicate_transition():
    """V16 applies to AFD, AFN and AFN-λ using the raw occurrence pairs."""
    afd_raw = parse_json_text(
        '{"tipo": "AFD", "estados": ["q0", "q1"], "alfabeto": ["a", "b"],'
        ' "inicial": "q0", "finales": ["q1"], "transiciones": {'
        ' "q0": {"a": "q1", "b": "q0"},'
        ' "q1": {"a": "q1", "b": "q0", "a": "q0"}}}'
    ).value
    issues = validate_semantics(cast(Mapping[str, object], afd_raw), TipoAutomata.AFD)
    assert _codes(issues) == ("DUPLICATE_TRANSITION",)
    assert issues[0].field == "transiciones['q1']['a']"
    assert issues[0].message == "Transición duplicada para el par ('q1', 'a')."

    afn_raw = parse_json_text(
        '{"tipo": "AFN", "estados": ["q0", "q1"], "alfabeto": ["a", "b"],'
        ' "inicial": "q0", "finales": ["q1"], "transiciones": {'
        ' "q0": {"a": ["q1"], "b": ["q0"], "a": ["q0"]},'
        ' "q1": {"a": ["q1"]}}}'
    ).value
    issues = validate_semantics(cast(Mapping[str, object], afn_raw), TipoAutomata.AFN)
    assert _codes(issues) == ("DUPLICATE_TRANSITION",)
    assert issues[0].field == "transiciones['q0']['a']"

    lambda_raw = parse_json_text(
        '{"tipo": "AFN-λ", "estados": ["q0", "q1"], "alfabeto": ["a", "b"],'
        ' "inicial": "q0", "finales": ["q1"], "transiciones": {'
        ' "q0": {"a": ["q1"], "λ": ["q1"], "λ": ["q0"]},'
        ' "q1": {"b": ["q1"]}}}'
    ).value
    issues = validate_semantics(
        cast(Mapping[str, object], lambda_raw), TipoAutomata.AFN_LAMBDA
    )
    assert _codes(issues) == ("DUPLICATE_TRANSITION",)
    assert issues[0].field == "transiciones['q0']['λ']"


def test_validate_v17():
    """V17: λ can never belong to the alphabet of any automaton type."""
    raw = _afd_raw()
    raw["alfabeto"] = ["a", "λ"]
    raw["transiciones"] = {"q0": {"a": "q1"}, "q1": {"a": "q1"}}

    issues = validate_semantics(raw, TipoAutomata.AFD)

    assert _codes(issues) == ("LAMBDA_IN_ALPHABET",)
    assert issues[0].field == "alfabeto[1]"
    assert issues[0].message == "El símbolo 'λ' no puede formar parte del alfabeto."


def test_validate_v17_lambda_alphabet():
    """V17 fires in AFN and AFN-λ too, independently of transition symbols."""
    for raw, tipo in (
        (_afn_raw(), TipoAutomata.AFN),
        (_afn_lambda_raw(), TipoAutomata.AFN_LAMBDA),
    ):
        raw["alfabeto"] = ["a", "b", "λ"]
        issues = validate_semantics(raw, tipo)

        assert _codes(issues) == ("LAMBDA_IN_ALPHABET",)
        assert issues[0].field == "alfabeto[2]"
        assert "SYMBOL_NOT_IN_ALPHABET" not in _codes(issues)


def test_validate_v18():
    """V18: an AFN target must be a list of states."""
    raw = _afn_raw()
    raw["transiciones"] = {"q0": {"a": "q1", "b": ["q0"]}, "q1": {"a": ["q1"]}}

    issues = validate_semantics(raw, TipoAutomata.AFN)

    assert _codes(issues) == ("INVALID_AFN_TARGET",)
    assert issues[0].field == "transiciones['q0']['a']"
    assert (
        issues[0].message
        == "Cada transición de un AFN debe apuntar a una lista de estados."
    )


@pytest.mark.parametrize("target", ["q1", None, 3, {"estado": "q1"}])
def test_validate_v18_afn_target_shape(target):
    """V18 rejects non-list targets and skips V12 for the invalid shape."""
    raw = _afn_raw()
    raw["transiciones"] = {"q0": {"a": target, "b": ["q0"]}, "q1": {"a": ["q1"]}}

    issues = validate_semantics(raw, TipoAutomata.AFN)

    assert _codes(issues) == ("INVALID_AFN_TARGET",)
    assert issues[0].field == "transiciones['q0']['a']"

    lambda_raw = _afn_lambda_raw()
    lambda_raw["transiciones"]["q0"]["a"] = target
    issues = validate_semantics(lambda_raw, TipoAutomata.AFN_LAMBDA)
    assert _codes(issues) == ("INVALID_AFN_TARGET",)


def test_validate_v18_empty_list_is_valid():
    """V18: an empty destination list means "no transition" and is valid."""
    raw = _afn_raw()
    raw["transiciones"] = {"q0": {"a": [], "b": ["q0"]}, "q1": {"a": ["q1"]}}

    assert validate_semantics(raw, TipoAutomata.AFN) == ()


def test_validate_v13_lambda_afn():
    """λ as an AFN transition symbol is owned by V13 when V17/V14 do not apply."""
    raw = _afn_raw()
    raw["transiciones"] = {
        "q0": {"a": ["q1"], "b": ["q0"], "λ": ["q1"]},
        "q1": {"a": ["q1"]},
    }

    issues = validate_semantics(raw, TipoAutomata.AFN)

    assert _codes(issues) == ("SYMBOL_NOT_IN_ALPHABET",)
    assert issues[0].field == "transiciones['q0']['λ']"
    assert issues[0].message == "El símbolo 'λ' no pertenece al alfabeto."


def test_validate_v14_lambda_afd():
    """λ as an AFD transition symbol is owned by V14, never duplicated by V13."""
    raw = _afd_raw()
    raw["transiciones"] = {
        "q0": {"a": "q1", "b": "q0", "λ": "q1"},
        "q1": {"a": "q1", "b": "q0"},
    }

    issues = validate_semantics(raw, TipoAutomata.AFD)

    assert _codes(issues) == ("LAMBDA_FORBIDDEN",)
    assert "SYMBOL_NOT_IN_ALPHABET" not in _codes(issues)


def test_lambda_precedence_no_double_report():
    """V17/V14 own λ reports; V13 skips λ and AFN-λ λ transitions are valid."""
    raw = _afd_raw()
    raw["alfabeto"] = ["a", "λ"]
    raw["transiciones"] = {
        "q0": {"a": "q1", "λ": "q1"},
        "q1": {"a": "q1"},
    }
    issues = validate_semantics(raw, TipoAutomata.AFD)
    assert _codes(issues) == ("LAMBDA_IN_ALPHABET", "LAMBDA_FORBIDDEN")
    assert "SYMBOL_NOT_IN_ALPHABET" not in _codes(issues)

    raw = _afn_raw()
    raw["alfabeto"] = ["a", "λ"]
    raw["transiciones"] = {
        "q0": {"a": ["q1"], "λ": ["q1"]},
        "q1": {"a": ["q1"]},
    }
    issues = validate_semantics(raw, TipoAutomata.AFN)
    assert _codes(issues) == ("LAMBDA_IN_ALPHABET",)

    assert validate_semantics(_afn_lambda_raw(), TipoAutomata.AFN_LAMBDA) == ()


# --- T09: build_automaton --------------------------------------------------


def test_build_automaton_afd():
    """T09: a validated AFD document becomes a frozen AFD model."""
    automaton = build_automaton(_afd_raw())

    assert isinstance(automaton, AFD)
    assert automaton.tipo is TipoAutomata.AFD
    assert automaton.estados == ("q0", "q1")
    assert automaton.alfabeto == ("a", "b")
    assert automaton.inicial == "q0"
    assert automaton.finales == frozenset({"q1"})
    assert tuple(automaton.transiciones) == ("q0", "q1")
    assert automaton.destino("q0", "a") == "q1"
    assert automaton.destino("q1", "b") == "q0"
    assert automaton.transiciones["q1"]["b"] == "q0"


def test_build_automaton_afn_empty_list_to_tuple():
    """T09: AFN destination lists become tuples; empty list becomes ()."""
    raw = _afn_raw()
    raw["transiciones"]["q1"]["b"] = []

    automaton = build_automaton(raw)

    assert isinstance(automaton, AFN)
    assert automaton.tipo is TipoAutomata.AFN
    assert automaton.transiciones["q0"]["a"] == ("q0", "q1")
    assert automaton.transiciones["q1"]["b"] == ()
    assert isinstance(automaton.transiciones["q1"]["b"], tuple)


def test_build_automaton_afn_lambda_keeps_lambda():
    """T09: AFN-λ keeps λ as a transition symbol and out of the alphabet."""
    automaton = build_automaton(_afn_lambda_raw())

    assert isinstance(automaton, NFALambda)
    assert automaton.tipo is TipoAutomata.AFN_LAMBDA
    assert automaton.transiciones["q0"]["λ"] == ("q1",)
    assert "λ" not in automaton.alfabeto


def test_unknown_top_level_fields_ignored():
    """O5: unknown top-level keys are ignored by validation and construction."""
    raw = _afd_raw()
    raw["version"] = 2
    raw["autor"] = "ejemplo"

    assert validate_structure(raw) == ()
    assert validate_semantics(raw, TipoAutomata.AFD) == ()

    automaton = build_automaton(raw)

    assert isinstance(automaton, AFD)
    assert not hasattr(automaton, "version")
    assert not hasattr(automaton, "autor")
