"""Simulation trace and result value objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReasonCode(str, Enum):
    """Reason codes for simulation verdicts (exact serialized values)."""

    ACCEPTED = "accepted"
    REJECTED_NON_FINAL = "rejected-non-final"
    REJECTED_MISSING_TRANSITION = "rejected-missing-transition"
    REJECTED_SYMBOL_NOT_IN_ALPHABET = "rejected-symbol-not-in-alphabet"


@dataclass(frozen=True, slots=True)
class TraceStep:
    """One consumed symbol, with ``None`` destination when execution stopped."""

    step: int
    source: str
    symbol: str | None
    destination: str | None
    destination_is_final: bool


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Data-only result of simulating one word."""

    word: str
    accepted: bool
    final_state: str | None
    reason: ReasonCode
    explanation: str
    trace: tuple[TraceStep, ...]
