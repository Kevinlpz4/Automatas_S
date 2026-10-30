"""Core automata value objects: canonical types and their frozen structures."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType


class TipoAutomata(str, Enum):
    """Canonical JSON type discriminator for every automaton kind."""

    AFD = "AFD"
    AFN = "AFN"
    AFN_LAMBDA = "AFN-λ"


def _freeze_states(
    estados: Iterable[str],
    alfabeto: Iterable[str],
    finales: Iterable[str],
) -> tuple[tuple[str, ...], tuple[str, ...], frozenset[str]]:
    """Return immutable collections for the three state-level fields."""
    return tuple(estados), tuple(alfabeto), frozenset(finales)


def _freeze_afd_transitions(
    transiciones: Mapping[str, Mapping[str, str]],
) -> Mapping[str, Mapping[str, str]]:
    """Freeze the outer and inner AFD transition mappings."""
    return MappingProxyType(
        {
            origen: MappingProxyType(dict(simbolos))
            for origen, simbolos in transiciones.items()
        }
    )


def _freeze_afn_transitions(
    transiciones: Mapping[str, Mapping[str, Iterable[str]]],
) -> Mapping[str, Mapping[str, tuple[str, ...]]]:
    """Freeze AFN-style transitions, normalizing destination lists to tuples."""
    return MappingProxyType(
        {
            origen: MappingProxyType(
                {
                    simbolo: tuple(destinos)
                    for simbolo, destinos in simbolos.items()
                }
            )
            for origen, simbolos in transiciones.items()
        }
    )


@dataclass(frozen=True, slots=True)
class AFD:
    """Deterministic finite automaton: one destination state per pair."""

    estados: tuple[str, ...]
    alfabeto: tuple[str, ...]
    inicial: str
    finales: frozenset[str]
    transiciones: Mapping[str, Mapping[str, str]]

    def __post_init__(self) -> None:
        estados, alfabeto, finales = _freeze_states(
            self.estados, self.alfabeto, self.finales
        )
        object.__setattr__(self, "estados", estados)
        object.__setattr__(self, "alfabeto", alfabeto)
        object.__setattr__(self, "finales", finales)
        object.__setattr__(
            self, "transiciones", _freeze_afd_transitions(self.transiciones)
        )

    @property
    def tipo(self) -> TipoAutomata:
        return TipoAutomata.AFD

    def es_final(self, estado: str) -> bool:
        return estado in self.finales

    def destino(self, estado: str, simbolo: str) -> str | None:
        """Return the destination state, or ``None`` when the pair is absent."""
        simbolos = self.transiciones.get(estado)
        if simbolos is None:
            return None
        return simbolos.get(simbolo)


@dataclass(frozen=True, slots=True)
class AFN:
    """Nondeterministic finite automaton: a destination tuple per pair."""

    estados: tuple[str, ...]
    alfabeto: tuple[str, ...]
    inicial: str
    finales: frozenset[str]
    transiciones: Mapping[str, Mapping[str, tuple[str, ...]]]

    def __post_init__(self) -> None:
        estados, alfabeto, finales = _freeze_states(
            self.estados, self.alfabeto, self.finales
        )
        object.__setattr__(self, "estados", estados)
        object.__setattr__(self, "alfabeto", alfabeto)
        object.__setattr__(self, "finales", finales)
        object.__setattr__(
            self, "transiciones", _freeze_afn_transitions(self.transiciones)
        )

    @property
    def tipo(self) -> TipoAutomata:
        return TipoAutomata.AFN


@dataclass(frozen=True, slots=True)
class NFALambda:
    """Nondeterministic automaton whose symbol keys may include ``λ``."""

    estados: tuple[str, ...]
    alfabeto: tuple[str, ...]
    inicial: str
    finales: frozenset[str]
    transiciones: Mapping[str, Mapping[str, tuple[str, ...]]]

    def __post_init__(self) -> None:
        estados, alfabeto, finales = _freeze_states(
            self.estados, self.alfabeto, self.finales
        )
        object.__setattr__(self, "estados", estados)
        object.__setattr__(self, "alfabeto", alfabeto)
        object.__setattr__(self, "finales", finales)
        object.__setattr__(
            self, "transiciones", _freeze_afn_transitions(self.transiciones)
        )

    @property
    def tipo(self) -> TipoAutomata:
        return TipoAutomata.AFN_LAMBDA


Automaton = AFD | AFN | NFALambda
