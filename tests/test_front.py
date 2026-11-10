import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATE_MODULE = ROOT / "web" / "js" / "state.js"
API_MODULE = ROOT / "web" / "js" / "api.js"
DOM_MODULE = ROOT / "web" / "js" / "dom.js"


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


def _run_api_script(script: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "API_MODULE": str(API_MODULE)}
    return subprocess.run(
        [_node(), "--input-type=module", "-e", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_dom_script(script: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DOM_MODULE": str(DOM_MODULE)}
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

// Literal from automata/models/tipos.py:16 (TipoAutomata.AFN_LAMBDA).
const afnLambda = { tipo: "AFN-λ", estados: ["q0"] };
mod.setSummary(afnLambda);
assert.equal(mod.state.summary, afnLambda);
assert.equal(mod.state.simularHabilitado, false);

mod.setSummary(null);
assert.equal(mod.state.summary, null);
assert.equal(mod.state.simularHabilitado, false);

console.log("summary-gating-ok");
"""


API_ENDPOINTS_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const calls = [];
const responses = {
  "GET /api/salud": { estado: "ok" },
  "GET /api/tipos": [{ tipo: "AFD", estado: "disponible" }],
  "GET /api/ejemplos": [{ nombre: "afd_ejemplo.json", tipo: "AFD" }],
  "GET /api/ejemplos/afd_ejemplo.json": '{"tipo":"AFD"}',
  "POST /api/automatas/validar": { tipo: "AFD", estados: ["q0"] },
  "POST /api/automatas/simular": { palabra: "a", aceptada: true },
};

globalThis.fetch = async (url, options = {}) => {
  const method = options.method ?? "GET";
  const key = `${method} ${url}`;
  calls.push({ method, url, options });
  const body = responses[key];
  if (body === undefined) throw new Error(`unexpected fetch: ${key}`);
  return {
    ok: true,
    status: 200,
    async json() { return body; },
    async text() { return body; },
  };
};

const api = await import(pathToFileURL(process.env.API_MODULE).href);

assert.deepEqual(await api.getSalud(), { estado: "ok" });
assert.equal(calls.at(-1).method, "GET");
assert.equal(calls.at(-1).url, "/api/salud");

assert.deepEqual(await api.getTipos(), [{ tipo: "AFD", estado: "disponible" }]);
assert.equal(calls.at(-1).url, "/api/tipos");

assert.deepEqual(await api.getEjemplos(), [{ nombre: "afd_ejemplo.json", tipo: "AFD" }]);
assert.equal(calls.at(-1).url, "/api/ejemplos");

const ejemplo = await api.getEjemplo("afd_ejemplo.json");
assert.equal(typeof ejemplo, "string");
assert.equal(ejemplo, '{"tipo":"AFD"}');
assert.equal(calls.at(-1).url, "/api/ejemplos/afd_ejemplo.json");

assert.deepEqual(await api.validar('{"tipo":"AFD"}'), { tipo: "AFD", estados: ["q0"] });
assert.equal(calls.at(-1).method, "POST");
assert.equal(calls.at(-1).url, "/api/automatas/validar");
assert.equal(calls.at(-1).options.headers["Content-Type"], "application/json");
assert.equal(calls.at(-1).options.body, '{"tipo":"AFD"}');

assert.deepEqual(await api.simular('{"tipo":"AFD"}', "a"), { palabra: "a", aceptada: true });
assert.equal(calls.at(-1).method, "POST");
assert.equal(calls.at(-1).url, "/api/automatas/simular");
assert.equal(calls.at(-1).options.headers["Content-Type"], "application/json");
assert.deepEqual(JSON.parse(calls.at(-1).options.body), {
  automata: '{"tipo":"AFD"}',
  palabra: "a",
});

console.log("api-endpoints-ok");
"""


API_ERROR_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const envelope = {
  errores: [{ codigo: "V01", mensaje: "El campo 'tipo' es obligatorio." }],
};

globalThis.fetch = async () => ({
  ok: false,
  status: 422,
  async json() { return envelope; },
  async text() { return JSON.stringify(envelope); },
});

const api = await import(pathToFileURL(process.env.API_MODULE).href);

for (const call of [
  () => api.validar('{"tipo":"AFD"}'),
  () => api.simular('{"tipo":"AFD"}', "a"),
]) {
  await assert.rejects(call, (error) => {
    assert.ok(error instanceof api.ApiError);
    assert.equal(error.name, "ApiError");
    assert.deepEqual(error.errores, envelope.errores);
    return true;
  });
}

console.log("api-error-parsing-ok");
"""


DOM_HELPERS_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const dom = await import(pathToFileURL(process.env.DOM_MODULE).href);
assert.equal(typeof dom.el, "function");
assert.equal(typeof dom.clear, "function");
assert.equal(typeof dom.setText, "function");
assert.equal(typeof dom.showToast, "function");
assert.equal(typeof dom.errorCards, "function");
assert.equal(typeof dom.apply, "function");
assert.equal(typeof dom.mountToast, "function");

assert.deepEqual(
  dom.el("div", { class: "panel" }, "", [dom.el("span", {}, "hola")]),
  {
    tag: "div",
    attrs: { class: "panel" },
    text: "",
    children: [{ tag: "span", attrs: {}, text: "hola", children: [] }],
  },
);
assert.deepEqual(dom.clear(), { type: "clear" });
assert.deepEqual(dom.setText("hola"), { type: "text", text: "hola" });

const cards = dom.errorCards([
  { codigo: "V01", mensaje: "El campo 'tipo' es obligatorio." },
  { codigo: "V02", mensaje: "El campo 'estados' no puede estar vacío." },
]);
assert.equal(cards.length, 2);
assert.equal(cards[0].tag, "article");
assert.equal(cards[0].attrs.class, "error-card");
assert.equal(cards[0].children[0].text, "V01");
assert.equal(cards[0].children[1].text, "El campo 'tipo' es obligatorio.");
assert.equal(cards[1].children[0].text, "V02");
assert.equal(cards[1].children[1].text, "El campo 'estados' no puede estar vacío.");
// The V-code is literal: no translation, prefix, or reformatting.
assert.notEqual(cards[0].children[0].text, "Error V01");

console.log("dom-helpers-ok");
"""


TOAST_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const dom = await import(pathToFileURL(process.env.DOM_MODULE).href);
assert.equal(typeof dom.showToast, "function");

const toast = dom.showToast("Ejemplo cargado");
assert.equal(toast.tag, "div");
assert.equal(toast.attrs.class, "toast");
assert.equal(toast.attrs.role, "status");
assert.equal(toast.attrs["aria-live"], "polite");
assert.equal(toast.text, "Ejemplo cargado");
assert.equal(toast.duracionMs, 3000);

const custom = dom.showToast("Archivo cargado", 1500);
assert.equal(custom.text, "Archivo cargado");
assert.equal(custom.duracionMs, 1500);

console.log("toast-aria-ok");
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


def test_front_gating_literal_matches_backend() -> None:
    """Guard that the JS gating test uses the same AFN-λ literal as the enum.

    This checks text presence, not runtime gating; the runtime behavior is
    covered by test_front_summary_gating.
    """
    from automata.models.tipos import TipoAutomata

    literal = TipoAutomata.AFN_LAMBDA.value
    assert literal == "AFN-λ"
    assert f'tipo: "{literal}"' in SUMMARY_GATING_SCRIPT


def test_front_api_endpoints() -> None:
    result = _run_api_script(API_ENDPOINTS_SCRIPT)
    _assert_node_ok(result)


def test_front_api_error_parsing() -> None:
    result = _run_api_script(API_ERROR_SCRIPT)
    _assert_node_ok(result)


def test_front_dom_helpers() -> None:
    result = _run_dom_script(DOM_HELPERS_SCRIPT)
    _assert_node_ok(result)


def test_front_toast_aria() -> None:
    result = _run_dom_script(TOAST_SCRIPT)
    _assert_node_ok(result)
