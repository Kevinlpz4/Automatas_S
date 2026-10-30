"""Interactive console session: menus, loading, evaluation and inspection.

The session depends only on ports plus injected text streams. It never
instantiates concrete services, never touches global stdio, and returns an exit
code instead of calling ``sys.exit``.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TextIO

from automata.cli.formato import (
    AFD_MENU_LINES,
    AFD_PROMPT,
    BATCH_PROMPT,
    COMING_SOON_MESSAGE,
    EMPTY_PATH_MESSAGE,
    EMPTY_WORD_ALIASES,
    INVALID_OPTION_MESSAGE,
    LOAD_PATH_PROMPT,
    LOAD_SUCCESS_TEMPLATE,
    MAIN_MENU_LINES,
    MAIN_PROMPT,
    NO_AUTOMATON_MESSAGE,
    NOT_AFD_MESSAGE,
    format_domain_error,
    format_result,
    format_summary,
)
from automata.cli.utf8 import configure_utf8
from automata.models.errores import DomainError
from automata.models.tipos import AFD
from automata.services.puertos import (
    AutomatonInspector,
    AutomatonLoader,
    Simulator,
)


class ConsoleSession:
    """Drive the console UI over injected ports and text streams."""

    def __init__(
        self,
        loader: AutomatonLoader,
        simulator: Simulator,
        inspector: AutomatonInspector,
        stdin: TextIO,
        stdout: TextIO,
    ) -> None:
        self._loader = loader
        self._simulator = simulator
        self._inspector = inspector
        self._stdin = stdin
        self._stdout = stdout
        self._loaded: AFD | None = None

    def run(self) -> int:
        """Run the main menu loop until Salir or EOF, always returning 0."""
        configure_utf8(self._stdout)
        while True:
            self._write_lines(MAIN_MENU_LINES)
            self._write(MAIN_PROMPT)
            line = self._read_line()
            if line is None:
                return 0
            option = line.strip()
            if option == "1":
                self._run_afd_menu()
            elif option in ("2", "3"):
                self._write_line(COMING_SOON_MESSAGE)
            elif option == "4":
                return 0
            else:
                self._write_line(INVALID_OPTION_MESSAGE)

    def _run_afd_menu(self) -> None:
        """Run the AFD submenu until Volver or EOF, sharing ``_loaded``."""
        while True:
            self._write_lines(AFD_MENU_LINES)
            self._write(AFD_PROMPT)
            line = self._read_line()
            if line is None:
                return
            option = line.strip()
            if option == "1":
                self._load_automaton()
            elif option == "2":
                self._evaluate_words()
            elif option == "3":
                self._show_definition()
            elif option == "4":
                return
            else:
                self._write_line(INVALID_OPTION_MESSAGE)

    def _load_automaton(self) -> None:
        """Prompt for a path and load an AFD, keeping the previous one on error."""
        self._write(LOAD_PATH_PROMPT)
        raw_path = self._read_line()
        if raw_path is None:
            return
        path_text = raw_path.strip()
        if not path_text:
            self._write_line(EMPTY_PATH_MESSAGE)
            return

        path = Path(path_text)
        try:
            automaton = self._loader.load(path)
        except DomainError as exc:
            self._write_lines(format_domain_error(exc).splitlines())
            return

        if not isinstance(automaton, AFD):
            self._write_line(NOT_AFD_MESSAGE)
            return

        self._loaded = automaton
        self._write_line(LOAD_SUCCESS_TEMPLATE.format(path=path))

    def _evaluate_words(self) -> None:
        """Read words one per line until an empty line or EOF and simulate each."""
        if self._loaded is None:
            self._write_line(NO_AUTOMATON_MESSAGE)
            return

        self._write_line(BATCH_PROMPT)
        while True:
            line = self._read_line()
            if line is None:
                return
            word = line.rstrip("\r\n")
            if word == "":
                return
            if word in EMPTY_WORD_ALIASES:
                word = ""
            result = self._simulator.simulate(self._loaded, word)
            self._write_lines(format_result(result).splitlines())

    def _show_definition(self) -> None:
        """Print the loaded AFD definition summary."""
        if self._loaded is None:
            self._write_line(NO_AUTOMATON_MESSAGE)
            return

        summary = self._inspector.summarize(self._loaded)
        self._write_lines(format_summary(summary).splitlines())

    def _read_line(self) -> str | None:
        """Return the next input line, or ``None`` at EOF."""
        line = self._stdin.readline()
        if line == "":
            return None
        return line

    def _write(self, text: str) -> None:
        self._stdout.write(text)

    def _write_line(self, text: str) -> None:
        self._stdout.write(f"{text}\n")

    def _write_lines(self, lines: Iterable[str]) -> None:
        for line in lines:
            self._stdout.write(f"{line}\n")
