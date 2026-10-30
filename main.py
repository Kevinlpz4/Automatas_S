"""Composition root: wire concrete services into the console session."""

from __future__ import annotations

import sys

from automata.cli.sesion import ConsoleSession
from automata.services.cargador import JsonAutomatonLoader
from automata.services.inspector import DefinitionInspector
from automata.services.simulador import AFDSimulator


def main() -> int:
    """Build the session with concrete dependencies and return its exit code."""
    session = ConsoleSession(
        loader=JsonAutomatonLoader(),
        simulator=AFDSimulator(),
        inspector=DefinitionInspector(),
        stdin=sys.stdin,
        stdout=sys.stdout,
    )
    return session.run()


if __name__ == "__main__":
    raise SystemExit(main())
