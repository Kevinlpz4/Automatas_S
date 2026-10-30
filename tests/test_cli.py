"""CLI presentation tests: UTF-8 helper, formatting and console session (T14–T17)."""

from __future__ import annotations

import ast
import io
import subprocess
import sys
from pathlib import Path

from automata.cli.formato import (
    format_domain_error,
    format_result,
    format_summary,
)
from automata.cli.sesion import ConsoleSession
from automata.cli.utf8 import configure_utf8
from automata.models.errores import (
    AutomatonFileNotFoundError,
    InvalidAutomatonDefinition,
)
from automata.models.validacion import ValidationIssue
from automata.models.vista import AutomatonSummary
from automata.services.cargador import JsonAutomatonLoader
from automata.services.inspector import DefinitionInspector
from automata.services.simulador import AFDSimulator
from conftest import EJEMPLOS, ROOT, make_session, write_json


# --- T14: UTF-8 helper -----------------------------------------------------


class _FakeStream:
    """Minimal TextIO stand-in that records ``reconfigure`` kwargs."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def reconfigure(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


def test_configure_utf8_reconfigures():
    """R19: a stream exposing reconfigure is switched to UTF-8 exactly once."""
    stream = _FakeStream()

    configure_utf8(stream)  # type: ignore[arg-type]

    assert stream.calls == [{"encoding": "utf-8"}]


def test_configure_utf8_noop_without_reconfigure():
    """R19: in-memory streams without reconfigure are left untouched."""
    stream = io.StringIO()

    configure_utf8(stream)

    assert stream.getvalue() == ""


# --- T15: formatting -------------------------------------------------------


def test_format_summary_renders_transition_view(loader):
    """R13: the summary renders the six sections and each TransitionView arrow."""
    afd = loader.load(EJEMPLOS / "afd_ejemplo.json")
    summary = DefinitionInspector().summarize(afd)

    text = format_summary(summary)

    assert "Tipo: AFD" in text
    assert "Estados:" in text
    assert "Alfabeto:" in text
    assert "Estado inicial: q0" in text
    assert "Estados finales:" in text
    assert "q1" in text and "q4" in text
    assert "Transiciones:" in text
    assert "q0 --a--> q1" in text
    assert "q5 --c--> q2" in text

    empty = AutomatonSummary(
        tipo="AFD",
        estados=("q0",),
        alfabeto=("a",),
        inicial="q0",
        finales=(),
        transiciones=(),
    )
    empty_text = format_summary(empty)
    assert "(ninguno)" in empty_text
    assert "(ninguna)" in empty_text


def test_format_result_renders_none_destination(loader, simulator):
    """R9/R10: a missing destination renders the reason-specific marker."""
    main = loader.load(EJEMPLOS / "afd_ejemplo.json")

    symbol_text = format_result(simulator.simulate(main, "az"))
    assert "RECHAZADA" in symbol_text
    assert "Motivo: rejected-symbol-not-in-alphabet" in symbol_text
    assert "(símbolo fuera del alfabeto)" in symbol_text
    assert "(transición faltante)" not in symbol_text
    assert "final: no" in symbol_text

    incomplete = loader.load(EJEMPLOS / "afd_incompleto.json")
    missing_text = format_result(simulator.simulate(incomplete, "ca"))
    assert "Motivo: rejected-missing-transition" in missing_text
    assert "(transición faltante)" in missing_text
    assert "(símbolo fuera del alfabeto)" not in missing_text

    accepted_text = format_result(simulator.simulate(main, "ca"))
    assert "ACEPTADA" in accepted_text
    assert "Motivo: accepted" in accepted_text
    assert "final: sí" in accepted_text

    empty_text = format_result(simulator.simulate(main, ""))
    assert "Palabra: λ" in empty_text


def test_format_domain_error_lists_issues():
    """R18: validation failures list one diagnostics line per issue."""
    issues = (
        ValidationIssue(
            code="MISSING_TIPO",
            message="Falta el campo obligatorio 'tipo'.",
            field="tipo",
            stage=1,
        ),
        ValidationIssue(
            code="INVALID_ROOT",
            message="El documento JSON debe ser un objeto.",
            field=None,
            stage=1,
        ),
    )
    error = InvalidAutomatonDefinition(issues)

    text = format_domain_error(error)

    assert "La definición del autómata no es válida." in text
    assert "- [MISSING_TIPO] Falta el campo obligatorio 'tipo'. (campo: tipo)" in text
    assert "- [INVALID_ROOT] El documento JSON debe ser un objeto." in text
    assert "(campo: None)" not in text

    other = AutomatonFileNotFoundError(Path("x.json"))
    other_text = format_domain_error(other)
    assert "No se encontró el archivo 'x.json'." in other_text
    assert "AUTOMATON_FILE_NOT_FOUND" in other_text
    assert "- [" not in other_text


# --- T16: console session --------------------------------------------------


class _RecordingStdout(io.StringIO):
    """StringIO subclass that records every ``reconfigure`` invocation."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict[str, object]] = []

    def reconfigure(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


def test_cli_main_menu():
    """R14: the main menu offers AFD, AFN, AFN-λ and Salir."""
    session, stdout = make_session("4\n")

    assert session.run() == 0

    output = stdout.getvalue()
    assert "Menú principal:" in output
    assert "AFD" in output
    assert "AFN" in output
    assert "AFN-λ" in output
    assert "Salir" in output


def test_cli_proximamente():
    """R14: AFN and AFN-λ print Próximamente exactly once each."""
    session, stdout = make_session("2\n3\n4\n")

    assert session.run() == 0

    assert stdout.getvalue().count("Próximamente") == 2


def test_cli_invalid_option():
    """R14: an invalid main option re-prompts without crashing."""
    session, stdout = make_session("xyz\n4\n")

    assert session.run() == 0

    assert "Opción inválida" in stdout.getvalue()


def test_cli_afd_submenu():
    """R15: the AFD submenu exposes the four documented options."""
    session, stdout = make_session("1\n4\n4\n")

    assert session.run() == 0

    output = stdout.getvalue()
    assert "Menú AFD:" in output
    assert "Cargar JSON" in output
    assert "Evaluar palabras" in output
    assert "Ver definición" in output
    assert "Volver" in output


def test_cli_keeps_loaded_in_session():
    """R15: a loaded AFD survives leaving and re-entering the AFD submenu."""
    path = EJEMPLOS / "afd_ejemplo.json"
    session, stdout = make_session(f"1\n1\n{path}\n3\n4\n1\n3\n4\n")

    assert session.run() == 0

    assert stdout.getvalue().count("q0 --a--> q1") == 2


def test_cli_evaluate_without_load():
    """R16: evaluating before loading prints the guard and returns to the menu."""
    session, stdout = make_session("1\n2\n4\n4\n")

    assert session.run() == 0

    assert "Primero tenés que cargar un AFD." in stdout.getvalue()


def test_cli_word_batch():
    """R17: words are read line by line until an empty line ends the batch."""
    path = EJEMPLOS / "afd_ejemplo.json"
    session, stdout = make_session(f"1\n1\n{path}\n2\nca\nab\n\n4\n4\n")

    assert session.run() == 0

    output = stdout.getvalue()
    assert "Palabra: ca" in output
    assert "Palabra: ab" in output
    assert output.count("ACEPTADA") == 1
    assert output.count("RECHAZADA") == 1


def test_cli_epsilon_alias(tmp_path):
    """R17: λ and epsilon both denote the empty word and display as λ."""
    path = write_json(
        tmp_path,
        "inicial_final.json",
        {
            "tipo": "AFD",
            "estados": ["q0", "q1"],
            "alfabeto": ["a"],
            "inicial": "q0",
            "finales": ["q0"],
            "transiciones": {"q0": {"a": "q1"}, "q1": {"a": "q1"}},
        },
    )
    session, stdout = make_session(f"1\n1\n{path}\n2\nλ\nepsilon\n\n4\n4\n")

    assert session.run() == 0

    output = stdout.getvalue()
    assert output.count("Palabra: λ") == 2
    assert output.count("ACEPTADA") == 2


def test_cli_load_error_no_traceback():
    """R18: a missing file renders a domain error with no traceback."""
    missing = EJEMPLOS / "no_existe.json"
    session, stdout = make_session(f"1\n1\n{missing}\n4\n4\n")

    assert session.run() == 0

    output = stdout.getvalue()
    assert "Error" in output
    assert "Traceback" not in output


def test_cli_afn_file_in_afd_submenu():
    """R18: a non-AFD file is rejected while the previous AFD is retained."""
    afd_path = EJEMPLOS / "afd_ejemplo.json"
    afn_path = EJEMPLOS / "afn_ejemplo.json"
    session, stdout = make_session(
        f"1\n1\n{afd_path}\n1\n{afn_path}\n3\n4\n4\n"
    )

    assert session.run() == 0

    output = stdout.getvalue()
    assert "El archivo cargado no contiene un AFD." in output
    assert "q0 --a--> q1" in output
    assert "Tipo: AFD" in output


def test_cli_utf8_reconfigure():
    """R19: run() reconfigures the injected stdout to UTF-8 as its first act."""
    stdout = _RecordingStdout()
    session = ConsoleSession(
        loader=JsonAutomatonLoader(),
        simulator=AFDSimulator(),
        inspector=DefinitionInspector(),
        stdin=io.StringIO("4\n"),
        stdout=stdout,
    )

    assert session.run() == 0

    assert stdout.calls == [{"encoding": "utf-8"}]


def test_definition_view():
    """R13: Ver definición prints the six sections and formatted arrows."""
    path = EJEMPLOS / "afd_ejemplo.json"
    session, stdout = make_session(f"1\n1\n{path}\n3\n4\n4\n")

    assert session.run() == 0

    output = stdout.getvalue()
    for section in (
        "Tipo:",
        "Estados:",
        "Alfabeto:",
        "Estado inicial:",
        "Estados finales:",
        "Transiciones:",
    ):
        assert section in output
    assert "q0 --a--> q1" in output


def test_cli_eof_exits_cleanly():
    """R16/design §7.1: EOF at any menu exits with 0 instead of looping."""
    empty, empty_stdout = make_session("")
    assert empty.run() == 0
    assert "Menú principal:" in empty_stdout.getvalue()

    submenu, submenu_stdout = make_session("1\n")
    assert submenu.run() == 0
    assert "Menú AFD:" in submenu_stdout.getvalue()


# --- T17: composition root -------------------------------------------------


def _uses_system_exit(path: Path) -> bool:
    """Return True when ``path`` raises SystemExit or calls ``exit``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            exc = node.exc
            if isinstance(exc, ast.Name) and exc.id == "SystemExit":
                return True
            if (
                isinstance(exc, ast.Call)
                and isinstance(exc.func, ast.Name)
                and exc.func.id == "SystemExit"
            ):
                return True
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "exit":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "exit":
                return True
    return False


def test_main_composition_root():
    """T17: main.py wires the concretes, prints the menu and exits 0."""
    completed = subprocess.run(
        [sys.executable, str(ROOT / "main.py")],
        input="4\n",
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=30,
    )

    assert completed.returncode == 0
    assert "Menú principal:" in completed.stdout
    assert "Traceback" not in completed.stderr
    assert "Traceback" not in completed.stdout

    production = [ROOT / "main.py", *sorted((ROOT / "automata").rglob("*.py"))]
    system_exit_users = [path for path in production if _uses_system_exit(path)]
    assert system_exit_users == [ROOT / "main.py"]
