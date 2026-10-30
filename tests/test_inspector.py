"""Service tests for the definition summary (T13)."""

from __future__ import annotations

import pytest

from automata.models.tipos import AFD
from automata.models.vista import AutomatonSummary, TransitionView
from automata.services.inspector import DefinitionInspector
from conftest import EJEMPLOS


@pytest.fixture
def inspector() -> DefinitionInspector:
    """Return the concrete definition inspector under test."""
    return DefinitionInspector()


def _load_main(loader) -> AFD:
    automaton = loader.load(EJEMPLOS / "afd_ejemplo.json")
    assert isinstance(automaton, AFD)
    return automaton


# --- T13: AFD summary ------------------------------------------------------


def test_summary_transitions_are_data(loader, inspector):
    """R13: transitions are ordered TransitionView data, never formatted text."""
    afd = _load_main(loader)
    summary = inspector.summarize(afd)

    assert isinstance(summary, AutomatonSummary)
    assert summary.tipo == "AFD"
    assert summary.estados == ("q0", "q1", "q2", "q3", "q4", "q5")
    assert summary.alfabeto == ("a", "b", "c")
    assert summary.inicial == "q0"
    assert summary.finales == ("q1", "q4")

    assert isinstance(summary.transiciones, tuple)
    assert all(isinstance(view, TransitionView) for view in summary.transiciones)

    arrow_count = sum(len(symbols) for symbols in afd.transiciones.values())
    assert arrow_count == 18
    assert len(summary.transiciones) == arrow_count

    assert summary.transiciones[0] == TransitionView("q0", "a", "q1")
    assert summary.transiciones[-1] == TransitionView("q5", "c", "q2")

    for view in summary.transiciones:
        assert "-->" not in view.source
        assert "-->" not in view.symbol
        assert "-->" not in view.destination
        assert "-->" not in repr(view)
    assert "-->" not in repr(summary)


# --- T13: AFN summary ------------------------------------------------------


def test_afn_summary_expands_destinations(loader, inspector):
    """R13: AFN emits one view per destination and omits empty transitions."""
    afn = loader.load(EJEMPLOS / "afn_ejemplo.json")
    summary = inspector.summarize(afn)

    assert summary.tipo == "AFN"
    assert len(summary.transiciones) == 5
    assert summary.transiciones == (
        TransitionView("q0", "a", "q0"),
        TransitionView("q0", "a", "q1"),
        TransitionView("q0", "b", "q0"),
        TransitionView("q1", "b", "q2"),
        TransitionView("q2", "a", "q2"),
    )
    assert TransitionView("q2", "b", "q2") not in summary.transiciones


# --- T13: AFN-λ summary ----------------------------------------------------


def test_afn_lambda_summary_puts_lambda_last(loader, inspector):
    """R13: every λ arrow forms a global suffix after alphabet-symbol arrows."""
    nfa_lambda = loader.load(EJEMPLOS / "afn_lambda_ejemplo.json")
    summary = inspector.summarize(nfa_lambda)

    assert summary.tipo == "AFN-λ"
    assert len(summary.transiciones) == 5
    assert summary.transiciones[:3] == (
        TransitionView("q0", "a", "q1"),
        TransitionView("q1", "b", "q2"),
        TransitionView("q2", "a", "q2"),
    )
    assert summary.transiciones[-2:] == (
        TransitionView("q0", "λ", "q2"),
        TransitionView("q1", "λ", "q1"),
    )
    assert [view.symbol for view in summary.transiciones] == ["a", "b", "a", "λ", "λ"]


# --- T13: ordering ---------------------------------------------------------


def test_summary_finales_ordered_by_estados(inspector):
    """The summary's finales follow the model state order, not the frozenset."""
    afd = AFD(
        estados=("s2", "s1", "s0"),
        alfabeto=("a",),
        inicial="s0",
        finales=frozenset({"s0", "s2"}),
        transiciones={"s0": {"a": "s0"}},
    )

    summary = inspector.summarize(afd)

    assert summary.finales == ("s2", "s0")
    assert summary.estados == ("s2", "s1", "s0")
    assert summary.alfabeto == ("a",)
    assert summary.inicial == "s0"
    assert summary.transiciones == (TransitionView("s0", "a", "s0"),)
