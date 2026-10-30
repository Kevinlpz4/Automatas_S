"""Service ports: structural contracts for loading, simulating and inspecting.

The ports are [Protocol]s, not base classes. Concretes satisfy them
structurally and are injected by the composition root (``main.py``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from automata.models.tipos import AFD, Automaton
from automata.models.traza import SimulationResult
from automata.models.vista import AutomatonSummary


class AutomatonLoader(Protocol):
    """Load an automaton definition from a path."""

    def load(self, path: Path) -> Automaton: ...


class Simulator(Protocol):
    """Execute a word against a deterministic automaton."""

    def simulate(self, automaton: AFD, word: str) -> SimulationResult: ...


class AutomatonInspector(Protocol):
    """Summarize an automaton definition as structured data."""

    def summarize(self, automaton: Automaton) -> AutomatonSummary: ...
