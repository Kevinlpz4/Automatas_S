"""Tests for the bundled automata example fixtures (R20)."""

from __future__ import annotations

import json
from typing import Any

from conftest import EJEMPLOS

EXPECTED_EXAMPLES = (
    "afd_ejemplo.json",
    "afd_incompleto.json",
    "afn_ejemplo.json",
    "afn_lambda_ejemplo.json",
)


def _load(name: str) -> dict[str, Any]:
    return json.loads((EJEMPLOS / name).read_text(encoding="utf-8"))


def _transition_count(transiciones: dict[str, dict[str, object]]) -> int:
    return sum(len(symbols) for symbols in transiciones.values())


def test_examples_present():
    """R20: all four example fixtures exist under ejemplos/."""
    missing = [name for name in EXPECTED_EXAMPLES if not (EJEMPLOS / name).is_file()]

    assert missing == []


def test_afd_fixture_shape():
    """Main AFD matches the verified design fixture (6 states, 18 transitions)."""
    data = _load("afd_ejemplo.json")

    assert data["tipo"] == "AFD"
    assert data["estados"] == ["q0", "q1", "q2", "q3", "q4", "q5"]
    assert data["alfabeto"] == ["a", "b", "c"]
    assert data["inicial"] == "q0"
    assert data["finales"] == ["q1", "q4"]
    assert set(data["transiciones"]) == set(data["estados"])
    assert _transition_count(data["transiciones"]) == 18


def test_afd_incompleto_missing_q3_a():
    """Incomplete AFD is identical to the main one except q3 lacks symbol 'a'."""
    complete = _load("afd_ejemplo.json")
    incomplete = _load("afd_incompleto.json")

    assert incomplete["tipo"] == "AFD"
    assert incomplete["estados"] == complete["estados"]
    assert incomplete["alfabeto"] == complete["alfabeto"]
    assert incomplete["inicial"] == complete["inicial"]
    assert incomplete["finales"] == complete["finales"]
    assert "a" not in incomplete["transiciones"]["q3"]
    assert incomplete["transiciones"]["q3"] == {"b": "q2", "c": "q2"}

    for estado in complete["transiciones"]:
        if estado != "q3":
            assert incomplete["transiciones"][estado] == complete["transiciones"][estado]

    assert _transition_count(incomplete["transiciones"]) == 17
