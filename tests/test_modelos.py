"""Domain model tests: automata types, JSON metadata, trace and definition view."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from types import MappingProxyType

import pytest

from automata.models.errores import (
    AutomatonFileNotFoundError,
    AutomatonFileReadError,
    DomainError,
    InvalidAutomatonDefinition,
    MalformedJsonError,
)
from automata.models.json_estructura import (
    JsonObject,
    ParsedJson,
    parse_json_text,
)
from automata.models.tipos import AFD, AFN, NFALambda, TipoAutomata
from automata.models.traza import ReasonCode, SimulationResult, TraceStep
from automata.models.validacion import ValidationIssue
from automata.models.vista import AutomatonSummary, TransitionView


def _afd() -> AFD:
    return AFD(
        estados=("q0", "q1"),
        alfabeto=("a", "b"),
        inicial="q0",
        finales=frozenset({"q1"}),
        transiciones={"q0": {"a": "q1"}, "q1": {"a": "q1", "b": "q0"}},
    )


# --- T03: tipos.py ---------------------------------------------------------


def test_tipos_enum_values():
    """TipoAutomata exposes the three exact JSON type values as a string enum."""
    assert TipoAutomata.AFD.value == "AFD"
    assert TipoAutomata.AFN.value == "AFN"
    assert TipoAutomata.AFN_LAMBDA.value == "AFN-λ"
    assert [member.value for member in TipoAutomata] == ["AFD", "AFN", "AFN-λ"]
    assert TipoAutomata.AFD == "AFD"


def test_afd_domain_behavior():
    """AFD exposes its type plus final membership and transition lookup behavior."""
    afd = _afd()

    assert afd.tipo is TipoAutomata.AFD
    assert afd.es_final("q1") is True
    assert afd.es_final("q0") is False
    assert afd.destino("q0", "a") == "q1"
    assert afd.destino("q1", "b") == "q0"
    assert afd.destino("q0", "b") is None
    assert afd.destino("q1", "z") is None
    assert afd.destino("desconocido", "a") is None


def test_models_are_frozen_and_immutable():
    """Models reject field assignment and freeze both transition mapping levels."""
    afd = _afd()
    assert isinstance(afd.transiciones, MappingProxyType)
    assert isinstance(afd.transiciones["q0"], MappingProxyType)

    with pytest.raises(FrozenInstanceError):
        afd.inicial = "q1"  # type: ignore[misc]
    with pytest.raises(TypeError):
        afd.transiciones["q0"]["a"] = "q0"  # type: ignore[index]
    with pytest.raises(TypeError):
        afd.transiciones["q2"] = {}  # type: ignore[index]

    afn = AFN(
        estados=["q0"],
        alfabeto=["a"],
        inicial="q0",
        finales={"q0"},
        transiciones={"q0": {"a": []}},
    )
    assert afn.estados == ("q0",)
    assert afn.alfabeto == ("a",)
    assert afn.finales == frozenset({"q0"})
    assert isinstance(afn.transiciones, MappingProxyType)
    assert isinstance(afn.transiciones["q0"], MappingProxyType)

    with pytest.raises(FrozenInstanceError):
        afn.inicial = "q1"  # type: ignore[misc]
    with pytest.raises(TypeError):
        afn.transiciones["q0"]["a"] = ("q0",)  # type: ignore[index]

    nfa_lambda = NFALambda(
        estados=("q0",),
        alfabeto=("a",),
        inicial="q0",
        finales=frozenset(),
        transiciones={"q0": {"λ": ("q0",)}},
    )
    assert nfa_lambda.tipo is TipoAutomata.AFN_LAMBDA
    with pytest.raises(FrozenInstanceError):
        nfa_lambda.inicial = "q1"  # type: ignore[misc]


def test_afn_empty_destination_tuple():
    """An empty AFN destination list normalizes to an empty tuple (no transition)."""
    afn = AFN(
        estados=("q0", "q1", "q2"),
        alfabeto=("a", "b"),
        inicial="q0",
        finales=frozenset({"q2"}),
        transiciones={"q0": {"a": [], "b": ["q0", "q1"]}, "q2": {"b": []}},
    )

    assert afn.tipo is TipoAutomata.AFN
    assert afn.transiciones["q0"]["a"] == ()
    assert isinstance(afn.transiciones["q0"]["a"], tuple)
    assert afn.transiciones["q0"]["b"] == ("q0", "q1")
    assert afn.transiciones["q2"]["b"] == ()


# --- T04: json_estructura.py ----------------------------------------------


def test_json_object_pairs_and_duplicates():
    """JsonObject keeps raw occurrences, reports repeats and maps last-wins."""
    obj = JsonObject([("a", 1), ("b", 2), ("a", 3)])

    assert isinstance(obj, Mapping)
    assert obj.pairs == (("a", 1), ("b", 2), ("a", 3))
    assert obj.duplicates == ("a",)
    assert len(obj) == 2
    assert list(obj) == ["a", "b"]
    assert obj["a"] == 3
    assert obj["b"] == 2


def test_json_object_last_wins():
    """Every repeated key keeps all pairs while the collapsed view keeps the last."""
    obj = JsonObject([("k", "first"), ("k", "second"), ("k", "third")])

    assert obj.pairs == (("k", "first"), ("k", "second"), ("k", "third"))
    assert obj.duplicates == ("k", "k")
    assert obj["k"] == "third"
    assert obj.to_plain() == {"k": "third"}


def test_parse_json_text_preserves_nested_metadata():
    """Every nested JSON object becomes a JsonObject with its duplicate metadata."""
    parsed = parse_json_text(
        '{"transiciones": {"q0": {"a": "q1", "a": "q2"}},'
        ' "extra": [{"k": 1, "k": 2}]}'
    )
    root = parsed.value

    assert isinstance(root, JsonObject)
    assert root.duplicates == ()

    transiciones = root["transiciones"]
    assert isinstance(transiciones, JsonObject)
    q0 = transiciones["q0"]
    assert isinstance(q0, JsonObject)
    assert q0.pairs == (("a", "q1"), ("a", "q2"))
    assert q0.duplicates == ("a",)
    assert q0["a"] == "q2"

    extra = root["extra"]
    assert isinstance(extra, list)
    element = extra[0]
    assert isinstance(element, JsonObject)
    assert element.duplicates == ("k",)
    assert element["k"] == 2


def test_parsed_json_to_plain():
    """ParsedJson.to_plain recursively strips metadata back to builtin values."""
    parsed = parse_json_text('{"a": 1, "b": [{"c": 2}, 3], "a": 4}')
    plain = parsed.to_plain()

    assert plain == {"a": 4, "b": [{"c": 2}, 3]}
    assert type(plain) is dict
    assert type(plain["b"]) is list
    assert type(plain["b"][0]) is dict
    assert ParsedJson(5).to_plain() == 5


# --- T05: traza.py ---------------------------------------------------------


def test_reason_codes_values():
    """ReasonCode exposes the four exact contractual reason values."""
    assert [code.value for code in ReasonCode] == [
        "accepted",
        "rejected-non-final",
        "rejected-missing-transition",
        "rejected-symbol-not-in-alphabet",
    ]
    assert ReasonCode.ACCEPTED == "accepted"
    assert ReasonCode.REJECTED_NON_FINAL.value == "rejected-non-final"
    assert ReasonCode.REJECTED_MISSING_TRANSITION.value == "rejected-missing-transition"
    assert (
        ReasonCode.REJECTED_SYMBOL_NOT_IN_ALPHABET.value
        == "rejected-symbol-not-in-alphabet"
    )


def test_trace_step_is_frozen():
    """TraceStep carries one consumed-step record and cannot be mutated."""
    step = TraceStep(
        step=1,
        source="q0",
        symbol="a",
        destination="q1",
        destination_is_final=True,
    )

    assert (step.step, step.source, step.symbol) == (1, "q0", "a")
    assert (step.destination, step.destination_is_final) == ("q1", True)

    missing = TraceStep(
        step=2,
        source="q3",
        symbol="a",
        destination=None,
        destination_is_final=False,
    )
    assert missing.destination is None
    assert missing.destination_is_final is False

    with pytest.raises(FrozenInstanceError):
        step.step = 2  # type: ignore[misc]


def test_simulation_result_contract_fields():
    """SimulationResult exposes word, verdict, final state, reason, text and trace."""
    first = TraceStep(
        step=1,
        source="q0",
        symbol="c",
        destination="q3",
        destination_is_final=False,
    )
    second = TraceStep(
        step=2,
        source="q3",
        symbol="a",
        destination="q4",
        destination_is_final=True,
    )
    trace = (first, second)

    result = SimulationResult(
        word="ca",
        accepted=True,
        final_state="q4",
        reason=ReasonCode.ACCEPTED,
        explanation="La palabra 'ca' es aceptada.",
        trace=trace,
    )

    assert result.word == "ca"
    assert result.accepted is True
    assert result.final_state == "q4"
    assert result.reason is ReasonCode.ACCEPTED
    assert result.explanation == "La palabra 'ca' es aceptada."
    assert isinstance(result.trace, tuple)
    assert result.trace == trace
    assert result.trace[0] is first

    with pytest.raises(FrozenInstanceError):
        result.accepted = False  # type: ignore[misc]


# --- T06: vista.py ---------------------------------------------------------


def test_transition_view_is_data():
    """TransitionView is a frozen value object with no formatting surface."""
    view = TransitionView(source="q0", symbol="a", destination="q1")
    same = TransitionView(source="q0", symbol="a", destination="q1")
    other = TransitionView(source="q0", symbol="a", destination="q2")

    assert view == same
    assert view != other
    assert (view.source, view.symbol, view.destination) == ("q0", "a", "q1")
    assert [field.name for field in fields(TransitionView)] == [
        "source",
        "symbol",
        "destination",
    ]
    assert {name for name in dir(TransitionView) if not name.startswith("_")} == {
        "source",
        "symbol",
        "destination",
    }
    assert "-->" not in repr(view)

    with pytest.raises(FrozenInstanceError):
        view.source = "q1"  # type: ignore[misc]


def test_summary_holds_transition_views():
    """AutomatonSummary stores ordered TransitionView data, never formatted text."""
    views = (
        TransitionView("q0", "a", "q1"),
        TransitionView("q0", "b", "q2"),
        TransitionView("q5", "c", "q2"),
    )
    summary = AutomatonSummary(
        tipo="AFD",
        estados=("q0", "q1", "q2", "q3", "q4", "q5"),
        alfabeto=("a", "b", "c"),
        inicial="q0",
        finales=("q1", "q4"),
        transiciones=views,
    )

    assert summary.tipo == "AFD"
    assert summary.estados == ("q0", "q1", "q2", "q3", "q4", "q5")
    assert summary.alfabeto == ("a", "b", "c")
    assert summary.inicial == "q0"
    assert summary.finales == ("q1", "q4")
    assert isinstance(summary.transiciones, tuple)
    assert summary.transiciones == views
    assert all(isinstance(view, TransitionView) for view in summary.transiciones)
    assert [field.name for field in fields(AutomatonSummary)] == [
        "tipo",
        "estados",
        "alfabeto",
        "inicial",
        "finales",
        "transiciones",
    ]
    assert "-->" not in repr(summary)

    with pytest.raises(FrozenInstanceError):
        summary.tipo = "AFN"  # type: ignore[misc]


# --- T10: errores.py -------------------------------------------------------


def test_domain_error_hierarchy():
    """T10: errors expose stable codes, Spanish messages, str and issue tuples."""
    for error_type in (
        InvalidAutomatonDefinition,
        AutomatonFileNotFoundError,
        AutomatonFileReadError,
        MalformedJsonError,
    ):
        assert issubclass(error_type, DomainError)

    issue = ValidationIssue(
        code="MISSING_TIPO",
        message="Falta el campo obligatorio 'tipo'.",
        field="tipo",
        stage=1,
    )
    definition = InvalidAutomatonDefinition((issue,))

    assert definition.code == "INVALID_AUTOMATON_DEFINITION"
    assert definition.errors == (issue,)
    assert definition.message == "La definición del autómata no es válida."
    assert str(definition) == definition.message

    path = Path("ejemplos/afd_ejemplo.json")
    not_found = AutomatonFileNotFoundError(path)
    assert not_found.code == "AUTOMATON_FILE_NOT_FOUND"
    assert not_found.path == path
    assert not_found.message == f"No se encontró el archivo '{path}'."
    assert str(not_found) == not_found.message

    unreadable = AutomatonFileReadError(path)
    assert unreadable.code == "AUTOMATON_FILE_READ_ERROR"
    assert unreadable.path == path
    assert unreadable.message == f"No se pudo leer el archivo '{path}'."
    assert str(unreadable) == unreadable.message

    malformed = MalformedJsonError(path)
    assert malformed.code == "MALFORMED_JSON"
    assert malformed.path == path
    assert malformed.message == f"El archivo '{path}' no contiene un JSON válido."
    assert str(malformed) == malformed.message
