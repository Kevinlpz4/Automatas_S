"""Repository layout and packaging tests (R1, R22)."""

from __future__ import annotations

import re

from conftest import ROOT


def test_layout_present():
    """R1: the layered package tree and top-level project files exist."""
    expected = (
        ROOT / "automata" / "models",
        ROOT / "automata" / "services",
        ROOT / "automata" / "cli",
        ROOT / "tests",
        ROOT / "ejemplos",
        ROOT / "main.py",
        ROOT / "requirements.txt",
        ROOT / "README.md",
    )

    missing = [str(path.relative_to(ROOT)) for path in expected if not path.exists()]

    assert missing == []


def _requirement_names(text: str) -> set[str]:
    """Extract normalized package names from a requirements file body."""
    names: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        name = re.split(r"[<>=!~;\[\s]", line, maxsplit=1)[0].strip()
        if name:
            names.add(name.lower())
    return names


def test_requirements_only_pytest():
    """R22: phase 1 declares pytest only and no web framework."""
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    names = _requirement_names(requirements)

    assert names == {"pytest"}
    assert "fastapi" not in names
