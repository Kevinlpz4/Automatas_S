import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATE_MODULE = ROOT / "web" / "js" / "state.js"


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node 20+ is required for front behavioral tests in "
            "tests/test_front.py; install Node 20+ or run the Python-only suite."
        )
    version = subprocess.run(
        [node, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if version.returncode != 0 or not version.stdout.strip().startswith("v"):
        pytest.fail(f"Could not determine Node version: {version.stderr}")
    major = int(version.stdout.strip().lstrip("v").split(".")[0])
    if major < 20:
        pytest.fail(f"Node 20+ is required; found {version.stdout.strip()}.")
    return node


def _run_state_script(script: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "STATE_MODULE": str(STATE_MODULE)}
    return subprocess.run(
        [_node(), "--input-type=module", "-e", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_node_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        "Node front test failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


ALIAS_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const mod = await import(pathToFileURL(process.env.STATE_MODULE).href);
// Non-string inputs are out of contract; normalizeWord assumes a string.
const cases = [
  ["λ", ""],
  ["epsilon", ""],
  ["Lambda", "Lambda"],
  ["EPSILON", "EPSILON"],
  [" λ ", " λ "],
  ["λ ", "λ "],
  [" λ", " λ"],
  ["λ\u0301", "λ\u0301"],
  ["\u019B", "\u019B"],
  ["", ""],
  ["epsilon ", "epsilon "],
  [" epsilon", " epsilon"],
  [null, null],
  [undefined, undefined],
];
for (const [input, expected] of cases) {
  const actual = mod.normalizeWord(input);
  assert.equal(actual, expected, `normalizeWord(${JSON.stringify(input)})`);
}
console.log("alias-policy-ok");
"""


INVALIDATION_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const mod = await import(pathToFileURL(process.env.STATE_MODULE).href);
assert.equal(typeof mod.normalizeWord, "function");
assert.equal(typeof mod.invalidate, "function");

mod.state.summary = { tipo: "AFD" };
mod.state.result = { aceptada: true };
mod.state.trace = [{ paso: 1 }];
mod.state.playback = { index: 0 };
mod.state.simularHabilitado = true;

mod.invalidate();

assert.equal(mod.state.summary, null);
assert.equal(mod.state.result, null);
assert.deepEqual(mod.state.trace, []);
assert.equal(mod.state.playback, null);
assert.equal(mod.state.simularHabilitado, false);
console.log("invalidation-policy-ok");
"""


SUMMARY_GATING_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const mod = await import(pathToFileURL(process.env.STATE_MODULE).href);
assert.equal(typeof mod.setSummary, "function");

const afd = { tipo: "AFD", estados: ["q0"] };
mod.setSummary(afd);
assert.equal(mod.state.summary, afd);
assert.equal(mod.state.simularHabilitado, true);

const afn = { tipo: "AFN", estados: ["q0"] };
mod.setSummary(afn);
assert.equal(mod.state.summary, afn);
assert.equal(mod.state.simularHabilitado, false);

const afnLambda = { tipo: "AFN-λ", estados: ["q0"] };
mod.setSummary(afnLambda);
assert.equal(mod.state.summary, afnLambda);
assert.equal(mod.state.simularHabilitado, false);

mod.setSummary(null);
assert.equal(mod.state.summary, null);
assert.equal(mod.state.simularHabilitado, false);

console.log("summary-gating-ok");
"""


def test_front_alias_policy() -> None:
    result = _run_state_script(ALIAS_SCRIPT)
    _assert_node_ok(result)


def test_front_invalidation_policy() -> None:
    result = _run_state_script(INVALIDATION_SCRIPT)
    _assert_node_ok(result)
    # Module contract only: this does not prove the whole front avoids
    # client-side validation, only that state.js does not fetch.
    source = STATE_MODULE.read_text(encoding="utf-8")
    assert "fetch(" not in source
    assert "fetch (" not in source


def test_front_summary_gating() -> None:
    result = _run_state_script(SUMMARY_GATING_SCRIPT)
    _assert_node_ok(result)
