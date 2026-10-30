"""Definition-view value objects: automaton data, never formatted text."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TransitionView:
    """One arrow of an automaton definition."""

    source: str
    symbol: str
    destination: str


@dataclass(frozen=True, slots=True)
class AutomatonSummary:
    """Immutable, presentation-agnostic view of an automaton definition."""

    tipo: str
    estados: tuple[str, ...]
    alfabeto: tuple[str, ...]
    inicial: str
    finales: tuple[str, ...]
    transiciones: tuple[TransitionView, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "estados", tuple(self.estados))
        object.__setattr__(self, "alfabeto", tuple(self.alfabeto))
        object.__setattr__(self, "finales", tuple(self.finales))
        object.__setattr__(self, "transiciones", tuple(self.transiciones))
