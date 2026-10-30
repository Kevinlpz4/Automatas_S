"""Definition inspection: automaton data as a summary, never formatted text."""

from __future__ import annotations

from automata.models.tipos import AFD, Automaton, NFALambda
from automata.models.vista import AutomatonSummary, TransitionView

LAMBDA = "λ"


class DefinitionInspector:
    """Build a deterministic, presentation-agnostic summary of an automaton."""

    def summarize(self, automaton: Automaton) -> AutomatonSummary:
        """Return type, state order, alphabet, finals and ordered transition views."""
        return AutomatonSummary(
            tipo=automaton.tipo.value,
            estados=tuple(automaton.estados),
            alfabeto=tuple(automaton.alfabeto),
            inicial=automaton.inicial,
            finales=self._ordered_finals(automaton),
            transiciones=self._transition_views(automaton),
        )

    @staticmethod
    def _ordered_finals(automaton: Automaton) -> tuple[str, ...]:
        """Order finals by the model's state order, never by the frozenset."""
        return tuple(
            estado for estado in automaton.estados if estado in automaton.finales
        )

    def _transition_views(self, automaton: Automaton) -> tuple[TransitionView, ...]:
        """Emit alphabet-symbol views first, then the global λ suffix."""
        views: list[TransitionView] = []

        for estado in automaton.estados:
            for simbolo in automaton.alfabeto:
                views.extend(
                    TransitionView(estado, simbolo, destino)
                    for destino in self._destinations(automaton, estado, simbolo)
                )

        if isinstance(automaton, NFALambda):
            for estado in automaton.estados:
                views.extend(
                    TransitionView(estado, LAMBDA, destino)
                    for destino in self._destinations(automaton, estado, LAMBDA)
                )

        return tuple(views)

    @staticmethod
    def _destinations(
        automaton: Automaton,
        estado: str,
        simbolo: str,
    ) -> tuple[str, ...]:
        """Return destinations for one pair: AFD at most one, AFN a tuple."""
        if isinstance(automaton, AFD):
            destino = automaton.destino(estado, simbolo)
            return () if destino is None else (destino,)
        return automaton.transiciones.get(estado, {}).get(simbolo, ())
