"""Human-readable rendering for menus, summaries, results and domain errors.

This is the only presentation module that turns domain value objects
(``AutomatonSummary``, ``TransitionView``, ``TraceStep``, ``DomainError``) into
text. Models and services stay free of formatting.
"""

from __future__ import annotations

from automata.models.errores import DomainError, InvalidAutomatonDefinition
from automata.models.traza import ReasonCode, SimulationResult, TraceStep
from automata.models.vista import AutomatonSummary

# --- menu text -------------------------------------------------------------

MAIN_MENU_LINES: tuple[str, ...] = (
    "Menú principal:",
    "  1) AFD",
    "  2) AFN",
    "  3) AFN-λ",
    "  4) Salir",
)
MAIN_PROMPT = "Opción: "

AFD_MENU_LINES: tuple[str, ...] = (
    "Menú AFD:",
    "  1) Cargar JSON",
    "  2) Evaluar palabras",
    "  3) Ver definición",
    "  4) Volver",
)
AFD_PROMPT = "Opción: "

# --- session messages ------------------------------------------------------

INVALID_OPTION_MESSAGE = "Opción inválida. Elegí una opción del menú."
COMING_SOON_MESSAGE = "Próximamente"
LOAD_PATH_PROMPT = "Ruta del archivo JSON: "
EMPTY_PATH_MESSAGE = "La ruta no puede estar vacía."
NOT_AFD_MESSAGE = "El archivo cargado no contiene un AFD."
NO_AUTOMATON_MESSAGE = "Primero tenés que cargar un AFD."
LOAD_SUCCESS_TEMPLATE = "AFD cargado desde '{path}'."
BATCH_PROMPT = (
    "Ingresá una palabra por línea. Una línea vacía termina el lote "
    "(usá 'λ' o 'epsilon' para la palabra vacía)."
)
EMPTY_WORD_ALIASES: tuple[str, ...] = ("λ", "epsilon")

# --- summary text ----------------------------------------------------------

SUMMARY_TIPO = "Tipo"
SUMMARY_ESTADOS = "Estados"
SUMMARY_ALFABETO = "Alfabeto"
SUMMARY_INICIAL = "Estado inicial"
SUMMARY_FINALES = "Estados finales"
SUMMARY_TRANSICIONES = "Transiciones"
EMPTY_FINALES = "(ninguno)"
EMPTY_TRANSITIONS = "(ninguna)"

# --- result text -----------------------------------------------------------

RESULT_WORD = "Palabra"
RESULT_VERDICT = "Resultado"
RESULT_REASON = "Motivo"
RESULT_EXPLANATION = "Explicación"
RESULT_TRACE = "Traza"
EMPTY_WORD = "λ"
EMPTY_TRACE = "(sin pasos)"
ACCEPTED_LABEL = "ACEPTADA"
REJECTED_LABEL = "RECHAZADA"
MISSING_SYMBOL = "(símbolo fuera del alfabeto)"
MISSING_TRANSITION = "(transición faltante)"
FINAL_YES = "sí"
FINAL_NO = "no"

# --- error text ------------------------------------------------------------

ERROR_PREFIX = "Error"


def format_summary(summary: AutomatonSummary) -> str:
    """Render an ``AutomatonSummary`` as the six definition-view sections."""
    lines = [
        f"{SUMMARY_TIPO}: {summary.tipo}",
        f"{SUMMARY_ESTADOS}: {', '.join(summary.estados)}",
        f"{SUMMARY_ALFABETO}: {', '.join(summary.alfabeto)}",
        f"{SUMMARY_INICIAL}: {summary.inicial}",
        f"{SUMMARY_FINALES}: {_join_or(summary.finales, EMPTY_FINALES)}",
        f"{SUMMARY_TRANSICIONES}:",
    ]
    if summary.transiciones:
        lines.extend(
            f"  {view.source} --{view.symbol}--> {view.destination}"
            for view in summary.transiciones
        )
    else:
        lines.append(f"  {EMPTY_TRANSITIONS}")
    return "\n".join(lines)


def format_result(result: SimulationResult) -> str:
    """Render a ``SimulationResult`` with verdict, reason, explanation and trace."""
    word = result.word if result.word else EMPTY_WORD
    verdict = ACCEPTED_LABEL if result.accepted else REJECTED_LABEL
    lines = [
        f"{RESULT_WORD}: {word}",
        f"{RESULT_VERDICT}: {verdict}",
        f"{RESULT_REASON}: {result.reason.value}",
        f"{RESULT_EXPLANATION}: {result.explanation}",
        f"{RESULT_TRACE}:",
    ]
    if result.trace:
        lines.extend(
            _format_trace_step(step, result.reason) for step in result.trace
        )
    else:
        lines.append(f"  {EMPTY_TRACE}")
    return "\n".join(lines)


def format_domain_error(exc: DomainError) -> str:
    """Render a domain error, expanding validation issues when present."""
    lines = [f"{ERROR_PREFIX} [{exc.code}]: {exc.message}"]
    if isinstance(exc, InvalidAutomatonDefinition):
        lines.extend(
            _format_issue(issue.code, issue.message, issue.field)
            for issue in exc.errors
        )
    return "\n".join(lines)


def _join_or(values: tuple[str, ...], fallback: str) -> str:
    return ", ".join(values) if values else fallback


def _format_trace_step(step: TraceStep, reason: ReasonCode) -> str:
    symbol = step.symbol if step.symbol is not None else ""
    if step.destination is None:
        if reason is ReasonCode.REJECTED_SYMBOL_NOT_IN_ALPHABET:
            destination = MISSING_SYMBOL
        else:
            destination = MISSING_TRANSITION
    else:
        destination = step.destination
    final = FINAL_YES if step.destination_is_final else FINAL_NO
    return (
        f"  Paso {step.step}: {step.source} --{symbol}--> "
        f"{destination} (final: {final})"
    )


def _format_issue(code: str, message: str, field: str | None) -> str:
    line = f"- [{code}] {message}"
    if field is not None:
        line = f"{line} (campo: {field})"
    return line
