"""Tests for the raw-text automaton loader (R26, R27).

The text loader shares the frozen phase-1 two-stage pipeline; parity with the
file loader is the central guarantee. These tests exercise the real pipeline
without mocks.
"""

from __future__ import annotations

import pytest

from automata.models.errores import InvalidAutomatonDefinition, MalformedJsonError
from automata.models.tipos import AFD, AFN, NFALambda, TipoAutomata
from automata.services.cargador import JsonAutomatonLoader
from automata.services.texto import JsonAutomatonTextLoader, MalformedJsonTextError
from conftest import EJEMPLOS

FIXTURES = (
    "afd_ejemplo.json",
    "afd_incompleto.json",
    "afn_ejemplo.json",
    "afn_lambda_ejemplo.json",
)


def _read(name: str) -> str:
    return (EJEMPLOS / name).read_text(encoding="utf-8")


def test_text_loader_afd() -> None:
    """R26: AFD text loads into a frozen ``AFD`` with the expected fields."""
    automaton = JsonAutomatonTextLoader().load_text(_read("afd_ejemplo.json"))

    assert isinstance(automaton, AFD)
    assert automaton.tipo is TipoAutomata.AFD
    assert automaton.estados == ("q0", "q1", "q2", "q3", "q4", "q5")
    assert automaton.alfabeto == ("a", "b", "c")
    assert automaton.inicial == "q0"
    assert automaton.finales == frozenset({"q1", "q4"})
    assert len(automaton.transiciones) == 6
    assert sum(len(simbolos) for simbolos in automaton.transiciones.values()) == 18


def test_text_loader_afn() -> None:
    """R26: AFN text loads into ``AFN`` preserving destination tuples."""
    automaton = JsonAutomatonTextLoader().load_text(_read("afn_ejemplo.json"))

    assert isinstance(automaton, AFN)
    assert automaton.tipo is TipoAutomata.AFN
    assert automaton.transiciones["q0"]["a"] == ("q0", "q1")
    assert automaton.transiciones["q1"]["b"] == ("q2",)
    assert automaton.transiciones["q2"]["b"] == ()


def test_text_loader_afn_lambda() -> None:
    """R26: AFN-λ text loads into ``NFALambda`` keeping λ as a transition key."""
    automaton = JsonAutomatonTextLoader().load_text(
        _read("afn_lambda_ejemplo.json")
    )

    assert isinstance(automaton, NFALambda)
    assert automaton.tipo is TipoAutomata.AFN_LAMBDA
    assert automaton.transiciones["q0"]["λ"] == ("q2",)
    assert automaton.transiciones["q1"]["λ"] == ("q1",)
    assert "λ" not in automaton.alfabeto


def test_text_loader_malformed() -> None:
    """R27: invalid JSON raises a pathless ``MalformedJsonTextError``."""
    with pytest.raises(MalformedJsonTextError) as excinfo:
        JsonAutomatonTextLoader().load_text('{"tipo": "AFD",')

    error = excinfo.value
    assert isinstance(error, MalformedJsonError)
    assert isinstance(error, MalformedJsonTextError)
    assert error.path is None
    assert error.code == "MALFORMED_JSON"


def test_text_loader_validation() -> None:
    """R27: invalid definitions raise ``InvalidAutomatonDefinition`` with all issues."""
    loader = JsonAutomatonTextLoader()

    structural = (
        '{"estados": ["q0", "q1"], "alfabeto": ["a"], "finales": ["q1"], '
        '"transiciones": {"q0": {"a": "q1"}}}'
    )
    with pytest.raises(InvalidAutomatonDefinition) as stage1_excinfo:
        loader.load_text(structural)

    stage1_issues = stage1_excinfo.value.errors
    assert [issue.code for issue in stage1_issues] == ["MISSING_TIPO", "MISSING_FIELD"]
    assert [issue.field for issue in stage1_issues] == ["tipo", "inicial"]
    assert all(issue.stage == 1 for issue in stage1_issues)

    semantic = (
        '{"tipo": "AFD", "estados": ["q0", "q1"], "alfabeto": ["a"], '
        '"inicial": "q0", "finales": ["q1"], '
        '"transiciones": {"q0": {"a": "q9"}, "q1": {"a": "q1"}}}'
    )
    with pytest.raises(InvalidAutomatonDefinition) as stage2_excinfo:
        loader.load_text(semantic)

    stage2_issues = stage2_excinfo.value.errors
    assert [issue.code for issue in stage2_issues] == ["UNKNOWN_DESTINATION_STATE"]
    assert stage2_issues[0].field == "transiciones['q0']['a']"
    assert stage2_issues[0].stage == 2


def test_text_loader_pipeline_parity() -> None:
    """R27: text and file loaders produce equal models for every fixture."""
    text_loader = JsonAutomatonTextLoader()
    file_loader = JsonAutomatonLoader()

    for name in FIXTURES:
        path = EJEMPLOS / name
        from_text = text_loader.load_text(path.read_text(encoding="utf-8"))
        from_file = file_loader.load(path)

        assert from_text == from_file, f"pipeline parity failed for {name}"
