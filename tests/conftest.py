"""Shared helpers for the ScriptAutomatas test suite."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automata.cli.sesion import ConsoleSession  # noqa: E402
from automata.services.cargador import JsonAutomatonLoader  # noqa: E402
from automata.services.inspector import DefinitionInspector  # noqa: E402
from automata.services.simulador import AFDSimulator  # noqa: E402

EJEMPLOS = ROOT / "ejemplos"


def write_json(tmp_path: Path, name: str, payload: object) -> Path:
    """Write ``payload`` as UTF-8 JSON to ``tmp_path/name`` and return the path."""
    path = tmp_path / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def write_text(tmp_path: Path, name: str, text: str) -> Path:
    """Write raw ``text`` to ``tmp_path/name`` and return the path.

    Used for fixtures that must retain duplicate JSON keys, which ``json.dumps``
    would collapse.
    """
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def loader() -> JsonAutomatonLoader:
    """Return the concrete JSON loader used by service-level tests."""
    return JsonAutomatonLoader()


@pytest.fixture
def simulator() -> AFDSimulator:
    """Return the concrete AFD simulator used by service-level tests."""
    return AFDSimulator()


def make_session(input_text: str) -> tuple[ConsoleSession, StringIO]:
    """Build an in-memory ``ConsoleSession`` wired with concrete services.

    Tests inject pre-seeded stdin and capture stdout through ``StringIO``; no
    real terminal or monkeypatching of ``sys`` streams is involved.
    """
    stdout = StringIO()
    session = ConsoleSession(
        loader=JsonAutomatonLoader(),
        simulator=AFDSimulator(),
        inspector=DefinitionInspector(),
        stdin=StringIO(input_text),
        stdout=stdout,
    )
    return session, stdout
