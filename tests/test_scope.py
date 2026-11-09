from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

assert (ROOT / "automata").is_dir(), (
    f"ROOT does not look like the project root: {ROOT}"
)

ARTIFACTS = (
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "node_modules",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "bun.lock",
)


@pytest.mark.parametrize("base", [ROOT, ROOT / "web"], ids=["root", "web"])
@pytest.mark.parametrize("artifact", ARTIFACTS)
def test_no_build_tooling(base: Path, artifact: str) -> None:
    target = base / artifact
    assert not target.exists(), (
        f"Build tooling artifact found: {target}. "
        "The product must remain Node/npm/build-free; "
        "Node is allowed only as a test prerequisite."
    )
