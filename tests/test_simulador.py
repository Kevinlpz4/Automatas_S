"""Service tests for AFD word simulation (T12)."""

from __future__ import annotations

import pytest

from automata.models.tipos import AFD
from automata.models.traza import ReasonCode, SimulationResult, TraceStep
from conftest import EJEMPLOS, write_json


def _load_main(loader) -> AFD:
    automaton = loader.load(EJEMPLOS / "afd_ejemplo.json")
    assert isinstance(automaton, AFD)
    return automaton


def _load_incomplete(loader) -> AFD:
    automaton = loader.load(EJEMPLOS / "afd_incompleto.json")
    assert isinstance(automaton, AFD)
    return automaton


# --- T12: basic verdicts ---------------------------------------------------


def test_simulate_accepted_word(loader, simulator):
    """R7: ``a`` reaches the final state q1."""
    result = simulator.simulate(_load_main(loader), "a")

    assert result.word == "a"
    assert result.accepted is True
    assert result.reason is ReasonCode.ACCEPTED
    assert result.final_state == "q1"
    assert result.trace == (TraceStep(1, "q0", "a", "q1", True),)


def test_simulate_rejected_word(loader, simulator):
    """R7: ``ab`` stops in the non-final state q5."""
    result = simulator.simulate(_load_main(loader), "ab")

    assert result.word == "ab"
    assert result.accepted is False
    assert result.reason is ReasonCode.REJECTED_NON_FINAL
    assert result.final_state == "q5"
    assert result.trace == (
        TraceStep(1, "q0", "a", "q1", True),
        TraceStep(2, "q1", "b", "q5", False),
    )


@pytest.mark.parametrize(
    ("word", "accepted"),
    [
        ("a", True),
        ("ca", True),
        ("aaa", True),
        ("abb", True),
        ("aba", True),
        ("ab", False),
        ("ac", False),
        ("acb", False),
        ("bab", False),
        ("cab", False),
    ],
    ids=[
        "a-accepted",
        "ca-accepted",
        "aaa-accepted",
        "abb-accepted",
        "aba-accepted",
        "ab-rejected",
        "ac-rejected",
        "acb-rejected",
        "bab-rejected",
        "cab-rejected",
    ],
)
def test_reference_words(loader, simulator, word, accepted):
    """R7: the ten design reference words have the documented verdicts."""
    result = simulator.simulate(_load_main(loader), word)

    assert result.word == word
    assert result.accepted is accepted
    expected_reason = ReasonCode.ACCEPTED if accepted else ReasonCode.REJECTED_NON_FINAL
    assert result.reason is expected_reason


# --- T12: empty word -------------------------------------------------------


def test_empty_word_accepted(loader, simulator, tmp_path):
    """R8: the empty word is accepted iff the initial state is final."""
    path = write_json(
        tmp_path,
        "inicial_final.json",
        {
            "tipo": "AFD",
            "estados": ["q0", "q1"],
            "alfabeto": ["a"],
            "inicial": "q0",
            "finales": ["q0"],
            "transiciones": {"q0": {"a": "q1"}, "q1": {"a": "q1"}},
        },
    )
    afd = loader.load(path)
    result = simulator.simulate(afd, "")

    assert result.word == ""
    assert result.accepted is True
    assert result.reason is ReasonCode.ACCEPTED
    assert result.final_state == "q0"
    assert result.trace == ()


def test_empty_word_rejected(loader, simulator):
    """R8: q0 is not final in the main AFD, so λ is rejected."""
    result = simulator.simulate(_load_main(loader), "")

    assert result.accepted is False
    assert result.reason is ReasonCode.REJECTED_NON_FINAL
    assert result.final_state == "q0"
    assert result.trace == ()


def test_empty_finales_rejects_all(loader, simulator, tmp_path):
    """R8: an empty ``finales`` list is valid and rejects every word."""
    path = write_json(
        tmp_path,
        "sin_finales.json",
        {
            "tipo": "AFD",
            "estados": ["q0", "q1"],
            "alfabeto": ["a"],
            "inicial": "q0",
            "finales": [],
            "transiciones": {"q0": {"a": "q1"}, "q1": {"a": "q1"}},
        },
    )
    afd = loader.load(path)

    for word in ("", "a", "aa", "aaa"):
        result = simulator.simulate(afd, word)
        assert result.accepted is False
        assert result.reason is ReasonCode.REJECTED_NON_FINAL
        assert result.final_state in {"q0", "q1"}


# --- T12: stopped execution ------------------------------------------------


def test_symbol_outside_alphabet(loader, simulator):
    """R9: the first symbol outside the alphabet stops execution at its step."""
    result = simulator.simulate(_load_main(loader), "az")

    assert result.accepted is False
    assert result.reason is ReasonCode.REJECTED_SYMBOL_NOT_IN_ALPHABET
    assert result.final_state is None
    assert len(result.trace) == 2
    assert result.trace[0] == TraceStep(1, "q0", "a", "q1", True)
    assert result.trace[1] == TraceStep(2, "q1", "z", None, False)
    assert result.trace[1].step == 2
    assert result.trace[1].source == "q1"
    assert result.trace[1].symbol == "z"


def test_missing_transition(loader, simulator):
    """R10: a missing transition stops execution with None destination and state."""
    result = simulator.simulate(_load_incomplete(loader), "ca")

    assert result.accepted is False
    assert result.reason is ReasonCode.REJECTED_MISSING_TRANSITION
    assert result.final_state is None
    assert len(result.trace) == 2
    assert result.trace[0] == TraceStep(1, "q0", "c", "q3", False)
    assert result.trace[1] == TraceStep(2, "q3", "a", None, False)
    assert result.trace[1].step == 2


# --- T12: trace and result contract ---------------------------------------


def test_trace_content(loader, simulator):
    """R11: ``ca`` exposes ordered 1-based steps with exact source/symbol/target."""
    result = simulator.simulate(_load_main(loader), "ca")

    assert result.trace == (
        TraceStep(1, "q0", "c", "q3", False),
        TraceStep(2, "q3", "a", "q4", True),
    )
    assert [step.step for step in result.trace] == [1, 2]
    assert [step.source for step in result.trace] == ["q0", "q3"]
    assert [step.symbol for step in result.trace] == ["c", "a"]
    assert [step.destination for step in result.trace] == ["q3", "q4"]
    assert [step.destination_is_final for step in result.trace] == [False, True]


def test_result_contract(loader, simulator):
    """R12: every result exposes the contractual fields as data."""
    result = simulator.simulate(_load_main(loader), "ca")

    assert isinstance(result, SimulationResult)
    assert isinstance(result.reason, ReasonCode)
    assert result.word == "ca"
    assert result.accepted is True
    assert result.final_state == "q4"
    assert isinstance(result.explanation, str)
    assert result.explanation
    assert "aceptada" in result.explanation.lower()
    assert isinstance(result.trace, tuple)
    assert all(isinstance(step, TraceStep) for step in result.trace)

    rejected = simulator.simulate(_load_main(loader), "ab")
    assert rejected.reason is ReasonCode.REJECTED_NON_FINAL
    assert "rechazada" in rejected.explanation.lower()
    assert rejected.final_state == "q5"

    stopped = simulator.simulate(_load_main(loader), "az")
    assert stopped.reason is ReasonCode.REJECTED_SYMBOL_NOT_IN_ALPHABET
    assert stopped.final_state is None
