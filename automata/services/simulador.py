"""Stateless execution of a deterministic finite automaton over a word."""

from __future__ import annotations

from automata.models.tipos import AFD
from automata.models.traza import ReasonCode, SimulationResult, TraceStep


class AFDSimulator:
    """Execute words against an ``AFD`` and report data-only results."""

    def simulate(self, automaton: AFD, word: str) -> SimulationResult:
        """Consume ``word`` symbol by symbol until acceptance or rejection."""
        if word == "":
            return self._empty_word_result(automaton)

        current = automaton.inicial
        trace: list[TraceStep] = []

        for step, symbol in enumerate(word, start=1):
            if symbol not in automaton.alfabeto:
                trace.append(TraceStep(step, current, symbol, None, False))
                return SimulationResult(
                    word=word,
                    accepted=False,
                    final_state=None,
                    reason=ReasonCode.REJECTED_SYMBOL_NOT_IN_ALPHABET,
                    explanation=(
                        f"La palabra '{word}' es rechazada: el símbolo "
                        f"'{symbol}' no pertenece al alfabeto (paso {step})."
                    ),
                    trace=tuple(trace),
                )

            destination = automaton.destino(current, symbol)
            if destination is None:
                trace.append(TraceStep(step, current, symbol, None, False))
                return SimulationResult(
                    word=word,
                    accepted=False,
                    final_state=None,
                    reason=ReasonCode.REJECTED_MISSING_TRANSITION,
                    explanation=(
                        f"La palabra '{word}' es rechazada: no hay transición "
                        f"desde '{current}' con '{symbol}' (paso {step})."
                    ),
                    trace=tuple(trace),
                )

            is_final = automaton.es_final(destination)
            trace.append(TraceStep(step, current, symbol, destination, is_final))
            current = destination

        return self._finished_result(automaton, word, current, tuple(trace))

    @staticmethod
    def _empty_word_result(automaton: AFD) -> SimulationResult:
        accepted = automaton.es_final(automaton.inicial)
        if accepted:
            explanation = (
                "La palabra vacía (λ) es aceptada: el estado inicial "
                f"'{automaton.inicial}' es final."
            )
        else:
            explanation = (
                "La palabra vacía (λ) es rechazada: el estado inicial "
                f"'{automaton.inicial}' no es final."
            )
        return SimulationResult(
            word="",
            accepted=accepted,
            final_state=automaton.inicial,
            reason=ReasonCode.ACCEPTED if accepted else ReasonCode.REJECTED_NON_FINAL,
            explanation=explanation,
            trace=(),
        )

    @staticmethod
    def _finished_result(
        automaton: AFD,
        word: str,
        final_state: str,
        trace: tuple[TraceStep, ...],
    ) -> SimulationResult:
        accepted = automaton.es_final(final_state)
        if accepted:
            explanation = (
                f"La palabra '{word}' es aceptada: terminó en el estado final "
                f"'{final_state}'."
            )
        else:
            explanation = (
                f"La palabra '{word}' es rechazada: terminó en el estado "
                f"'{final_state}', que no es final."
            )
        return SimulationResult(
            word=word,
            accepted=accepted,
            final_state=final_state,
            reason=ReasonCode.ACCEPTED if accepted else ReasonCode.REJECTED_NON_FINAL,
            explanation=explanation,
            trace=trace,
        )
