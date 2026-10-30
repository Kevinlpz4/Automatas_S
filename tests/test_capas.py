"""Static architecture tests: layer purity and service I/O bans (R2, R3).

Both checks parse source with :mod:`ast`, never a regular expression, so
comments, docstrings and string literals cannot trigger false positives.

Scope (phase 1): only static ``import``/``from ... import`` statements and
direct ``ast.Call`` nodes are inspected. Dynamic loading through ``importlib``
or ``__import__`` is deliberately out of scope and documented here so the
limitation is explicit rather than accidental.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

from conftest import ROOT

MODELS_DIR = ROOT / "automata" / "models"
SERVICES_DIR = ROOT / "automata" / "services"
CLI_DIR = ROOT / "automata" / "cli"

#: Layers ``models`` must never depend on (unidirectional ``services -> models``).
FORBIDDEN_FOR_MODELS = ("automata.services", "automata.cli")
#: Layers ``services`` must never depend on (``cli`` is the top layer).
FORBIDDEN_FOR_SERVICES = ("automata.cli",)


def _module_and_package(path: Path) -> tuple[str, str]:
    """Return the dotted module name and its package for ``path``."""
    module = ".".join(path.relative_to(ROOT).with_suffix("").parts)
    return module, module.rsplit(".", 1)[0]


def _resolved_imports(tree: ast.AST, package: str) -> set[str]:
    """Collect every statically imported dotted name, expanding aliases.

    Absolute ``import x`` yields ``x``. ``from a.b import c`` yields ``a.b``
    and ``a.b.c`` so both module-level and symbol-level references are caught.
    Relative imports are resolved against ``package``; expanding each alias to
    ``module + "." + alias.name`` is what makes ``from automata import
    services`` detectable as ``automata.services``.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative = "." * node.level + (node.module or "")
                module = importlib.util.resolve_name(relative, package)
            elif node.module:
                module = node.module
            else:
                continue
            names.add(module)
            for alias in node.names:
                names.add(f"{module}.{alias.name}")
    return names


def _matches_prefix(name: str, prefixes: tuple[str, ...]) -> bool:
    """Return True when ``name`` is one of ``prefixes`` or nested under one."""
    return any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)


def _layer_violations(layer_dir: Path, forbidden: tuple[str, ...]) -> list[str]:
    """Return a readable report of forbidden imports found under ``layer_dir``."""
    violations: list[str] = []
    for path in sorted(layer_dir.rglob("*.py")):
        module, package = _module_and_package(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in sorted(_resolved_imports(tree, package)):
            if _matches_prefix(imported, forbidden):
                violations.append(f"{module}: imports {imported}")
    return violations


def _io_bindings(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Return the local names bound to ``sys`` and to ``sys.exit``.

    ``import sys as s`` records ``s``; ``from sys import exit as stop`` records
    ``stop``. Alias tracking keeps the call check honest regardless of naming.
    """
    sys_aliases: set[str] = set()
    exit_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sys":
                    sys_aliases.add(alias.asname or "sys")
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module == "sys"
        ):
            for alias in node.names:
                if alias.name == "exit":
                    exit_names.add(alias.asname or "exit")
    return sys_aliases, exit_names


def _forbidden_call(
    func: ast.expr,
    sys_aliases: set[str],
    exit_names: set[str],
) -> str | None:
    """Return the banned console/process call name, or ``None`` when allowed."""
    if isinstance(func, ast.Name):
        if func.id in ("print", "input"):
            return f"{func.id}()"
        if func.id in exit_names:
            return "sys.exit()"
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "exit"
        and isinstance(func.value, ast.Name)
        and func.value.id in sys_aliases
    ):
        return "sys.exit()"
    return None


def _io_violations(layer_dir: Path) -> list[str]:
    """Return a readable report of banned I/O calls under ``layer_dir``.

    Only ``ast.Call`` nodes are flagged, so merely referencing ``sys`` or a
    docstring mentioning ``print`` is harmless. File I/O via ``Path.read_text``
    is allowed; the ban covers console/process I/O only.
    """
    violations: list[str] = []
    for path in sorted(layer_dir.rglob("*.py")):
        module, _package = _module_and_package(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        sys_aliases, exit_names = _io_bindings(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call = _forbidden_call(node.func, sys_aliases, exit_names)
                if call is not None:
                    violations.append(f"{module}: calls {call}")
    return violations


def test_layer_purity_ast():
    """R2: models import neither services nor cli; services never import cli."""
    violations = _layer_violations(MODELS_DIR, FORBIDDEN_FOR_MODELS)
    violations += _layer_violations(SERVICES_DIR, FORBIDDEN_FOR_SERVICES)

    assert violations == []


def test_services_no_io():
    """R3: services never call print/input or terminate the process."""
    assert _io_violations(SERVICES_DIR) == []


def test_cli_no_direct_io():
    """CLI writes through injected streams, never print/input or sys.exit."""
    assert _io_violations(CLI_DIR) == []
