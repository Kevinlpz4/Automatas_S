"""Pydantic wire models with the locked Spanish field names.

Python identifiers, docstrings and code comments stay English; only the
serialized field names are Spanish, as locked by spec R16/R20. The models are
data-only: no formatting, no I/O and no route logic. Extra fields (including
English aliases) are ignored so responses never echo unintended keys.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from automata.models.traza import SimulationResult
from automata.models.vista import AutomatonSummary


class _WireModel(BaseModel):
    """Base wire model: unknown fields are dropped, never echoed."""

    model_config = ConfigDict(extra="ignore")


class SaludResponse(_WireModel):
    """Health payload."""

    estado: Literal["ok"]


class TipoItem(_WireModel):
    """One automaton type with its availability state."""

    tipo: str
    estado: Literal["disponible", "proximamente"]


class EjemploItem(_WireModel):
    """One bundled example entry."""

    nombre: str
    tipo: str


class TransicionSchema(_WireModel):
    """One automaton arrow on the wire."""

    origen: str
    simbolo: str
    destino: str


class ResumenAutomata(_WireModel):
    """Validated automaton summary with Spanish wire keys."""

    tipo: str
    estados: list[str]
    alfabeto: list[str]
    inicial: str
    finales: list[str]
    transiciones: list[TransicionSchema]

    @classmethod
    def from_summary(cls, summary: AutomatonSummary) -> "ResumenAutomata":
        """Map a domain summary to its wire representation."""
        return cls(
            tipo=summary.tipo,
            estados=list(summary.estados),
            alfabeto=list(summary.alfabeto),
            inicial=summary.inicial,
            finales=list(summary.finales),
            transiciones=[
                TransicionSchema(
                    origen=view.source,
                    simbolo=view.symbol,
                    destino=view.destination,
                )
                for view in summary.transiciones
            ],
        )


class SimularRequest(_WireModel):
    """Simulation request: automaton JSON text plus the word to consume."""

    automata: str
    palabra: str


class PasoTraza(_WireModel):
    """One consumed symbol on the wire."""

    paso: int
    origen: str
    simbolo: str | None
    destino: str | None
    destino_es_final: bool
    transicion_faltante: bool


class ResultadoSimulacion(_WireModel):
    """Simulation result with Spanish wire keys."""

    palabra: str
    aceptada: bool
    estado_final: str | None
    motivo: str
    explicacion: str
    traza: list[PasoTraza]

    @classmethod
    def from_result(cls, result: SimulationResult) -> "ResultadoSimulacion":
        """Map a domain result to its wire representation."""
        return cls(
            palabra=result.word,
            aceptada=result.accepted,
            estado_final=result.final_state,
            motivo=result.reason.value,
            explicacion=result.explanation,
            traza=[
                PasoTraza(
                    paso=step.step,
                    origen=step.source,
                    simbolo=step.symbol,
                    destino=step.destination,
                    destino_es_final=step.destination_is_final,
                    transicion_faltante=step.destination is None,
                )
                for step in result.trace
            ],
        )


class ErrorItem(_WireModel):
    """One controlled API error."""

    codigo: str
    mensaje: str


class ErrorResponse(_WireModel):
    """Controlled error envelope: exactly ``errores``."""

    errores: list[ErrorItem]
