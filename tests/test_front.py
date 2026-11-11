import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATE_MODULE = ROOT / "web" / "js" / "state.js"
API_MODULE = ROOT / "web" / "js" / "api.js"
DOM_MODULE = ROOT / "web" / "js" / "dom.js"
DIAGRAM_MODULE = ROOT / "web" / "js" / "diagram.js"
PLAYBACK_MODULE = ROOT / "web" / "js" / "playback.js"
UPCOMING_MODULE = ROOT / "web" / "js" / "upcoming.js"
UPCOMING_FIXTURES = ROOT / "ejemplos"
STYLES_CSS = ROOT / "web" / "styles.css"
INDEX_HTML = ROOT / "web" / "index.html"

THEME_TOKENS = {
    "--bg": "#0b1220",
    "--surface": "#111a2b",
    "--surface-2": "#18243a",
    "--border": "#26364f",
    "--text": "#e6edf7",
    "--text-muted": "#9fb0c8",
    "--accent": "#22d3ee",
    "--blue": "#3b82f6",
    "--success": "#22c55e",
    "--danger": "#ef4444",
    "--warning": "#f59e0b",
}


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


def _run_diagram_script(script: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DIAGRAM_MODULE": str(DIAGRAM_MODULE)}
    return subprocess.run(
        [_node(), "--input-type=module", "-e", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_playback_script(script: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PLAYBACK_MODULE": str(PLAYBACK_MODULE)}
    return subprocess.run(
        [_node(), "--input-type=module", "-e", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_upcoming_script(script: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "UPCOMING_MODULE": str(UPCOMING_MODULE),
        "UPCOMING_FIXTURES": str(UPCOMING_FIXTURES),
    }
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


DIAGRAM_LAYOUT_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const mod = await import(pathToFileURL(process.env.DIAGRAM_MODULE).href);
assert.equal(typeof mod.layoutDiagram, "function");
assert.equal(typeof mod.groupLabels, "function");
assert.equal(typeof mod.highlightStep, "function");
assert.equal(typeof mod.clearHighlight, "function");
assert.equal(typeof mod.toSvg, "function");

const summary = {
  tipo: "AFD",
  estados: ["q0", "q1", "q2", "q3"],
  alfabeto: ["a", "b"],
  inicial: "q0",
  finales: ["q3"],
  transiciones: [
    { origen: "q0", simbolo: "a", destino: "q1" },
    { origen: "q1", simbolo: "a", destino: "q0" },
    { origen: "q1", simbolo: "b", destino: "q2" },
    { origen: "q2", simbolo: "a", destino: "q3" },
    { origen: "q3", simbolo: "a", destino: "q0" },
    { origen: "q3", simbolo: "b", destino: "q3" },
  ],
};

const layout = mod.layoutDiagram(summary);
assert.equal(layout.role, "img");
assert.equal(layout.title, "Diagrama del autómata");
assert.equal(layout.desc, "Estados, transiciones y estado inicial.");
assert.equal(layout.width, 640);
assert.equal(layout.height, 480);
assert.equal(layout.radius, 28);
assert.equal(layout.nodes.length, 4);
assert.equal(layout.edges.length, 6);
assert.equal(layout.highlight, null);
assert.equal(layout.markers[0].id, "arrow");
assert.equal(layout.markers[0].markerWidth, 10);
assert.equal(layout.markers[0].markerHeight, 10);
assert.equal(layout.markers[0].refX, 9);
assert.equal(layout.markers[0].refY, 3);
assert.equal(layout.markers[0].orient, "auto");
assert.equal(layout.markers[0].path, "M0,0 L0,6 L9,3 z");
assert.equal(layout.initialArrow.label, "inicio");
assert.equal(layout.initialArrow.markerEnd, "url(#arrow)");

const byId = Object.fromEntries(layout.nodes.map((node) => [node.id, node]));
assert.equal(byId.q0.initial, true);
assert.equal(byId.q3.final, true);
assert.equal(byId.q1.final, false);
for (const node of layout.nodes) {
  assert.equal(node.r, 28);
  assert.ok(
    Math.abs(
      Math.hypot(node.x - layout.center.x, node.y - layout.center.y) -
        layout.orbit,
    ) < 1e-9,
    `node ${node.id} must sit on the layout orbit`,
  );
}
assert.ok(layout.orbit > layout.radius * 2);
assert.ok(Math.abs(byId.q0.x - layout.center.x) < 1e-9);
assert.ok(byId.q0.y < layout.center.y);
assert.ok(layout.initialArrow.toX < byId.q0.x);
assert.ok(Math.abs(layout.initialArrow.toY - byId.q0.y) < 1e-9);

const selfLoop = layout.edges.find((edge) => edge.from === "q3" && edge.to === "q3");
assert.equal(selfLoop.kind, "self");
assert.equal(selfLoop.label, "b");
assert.equal(selfLoop.markerEnd, "url(#arrow)");

const forward = layout.edges.find((edge) => edge.from === "q0" && edge.to === "q1");
const reverse = layout.edges.find((edge) => edge.from === "q1" && edge.to === "q0");
assert.equal(forward.kind, "mutual");
assert.equal(reverse.kind, "mutual");
assert.notEqual(forward.offset, reverse.offset);

const normal = layout.edges.find((edge) => edge.from === "q1" && edge.to === "q2");
assert.equal(normal.kind, "normal");
assert.equal(normal.markerEnd, "url(#arrow)");

const again = mod.layoutDiagram(summary);
assert.deepEqual(again, layout);
console.log("diagram-layout-ok");
"""


DIAGRAM_LABELS_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const mod = await import(pathToFileURL(process.env.DIAGRAM_MODULE).href);
assert.equal(typeof mod.groupLabels, "function");

const groups = mod.groupLabels([
  { origen: "q0", simbolo: "b", destino: "q1" },
  { origen: "q0", simbolo: "a", destino: "q1" },
  { origen: "q0", simbolo: "a", destino: "q1" },
  { origen: "q1", simbolo: "c", destino: "q1" },
  { origen: "q0", simbolo: "c", destino: "q2" },
]);
assert.deepEqual(groups, [
  { origen: "q0", destino: "q1", symbols: ["a", "b"], label: "(a, b)" },
  { origen: "q1", destino: "q1", symbols: ["c"], label: "c" },
  { origen: "q0", destino: "q2", symbols: ["c"], label: "c" },
]);

const bc = mod.groupLabels([
  { origen: "q2", simbolo: "c", destino: "q3" },
  { origen: "q2", simbolo: "b", destino: "q3" },
]);
assert.deepEqual(bc, [
  { origen: "q2", destino: "q3", symbols: ["b", "c"], label: "(b, c)" },
]);

const single = mod.groupLabels([
  { origen: "q0", simbolo: "a", destino: "q1" },
]);
assert.equal(single[0].label, "a");

console.log("diagram-labels-ok");
"""


DIAGRAM_HIGHLIGHT_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const mod = await import(pathToFileURL(process.env.DIAGRAM_MODULE).href);
assert.equal(typeof mod.layoutDiagram, "function");
assert.equal(typeof mod.highlightStep, "function");
assert.equal(typeof mod.clearHighlight, "function");

const summary = {
  tipo: "AFD",
  estados: ["q0", "q1", "q2", "q3"],
  alfabeto: ["a", "b"],
  inicial: "q0",
  finales: ["q3"],
  transiciones: [
    { origen: "q0", simbolo: "a", destino: "q1" },
    { origen: "q1", simbolo: "a", destino: "q0" },
    { origen: "q1", simbolo: "b", destino: "q2" },
    { origen: "q2", simbolo: "a", destino: "q3" },
    { origen: "q3", simbolo: "a", destino: "q0" },
    { origen: "q3", simbolo: "b", destino: "q3" },
  ],
};
const layout = mod.layoutDiagram(summary);

const active = mod.highlightStep(
  layout,
  { origen: "q0", simbolo: "a", destino: "q1", transicion_faltante: false },
  { accepted: false },
);
assert.equal(active.highlight.activeNode, "q0");
assert.deepEqual(active.highlight.activeEdge, {
  from: "q0",
  to: "q1",
  label: "a",
});
assert.equal(active.highlight.acceptedNode, null);
assert.equal(active.highlight.warningNode, null);
assert.equal(active.edges.length, layout.edges.length);
assert.equal(layout.highlight, null);

const accepted = mod.highlightStep(
  layout,
  { origen: "q2", simbolo: "a", destino: "q3", transicion_faltante: false },
  { accepted: true },
);
assert.equal(accepted.highlight.acceptedNode, "q3");

const missing = mod.highlightStep(
  layout,
  { origen: "q1", simbolo: "z", destino: null, transicion_faltante: true },
  { warning: true },
);
assert.equal(missing.highlight.warningNode, "q1");
assert.equal(missing.highlight.activeEdge, null);
assert.equal(missing.edges.length, layout.edges.length);

const cleared = mod.clearHighlight(active);
assert.equal(cleared.highlight, null);

console.log("diagram-highlight-ok");
"""


DIAGRAM_SVG_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const mod = await import(pathToFileURL(process.env.DIAGRAM_MODULE).href);
assert.equal(typeof mod.layoutDiagram, "function");
assert.equal(typeof mod.toSvg, "function");

const summary = {
  tipo: "AFD",
  estados: ["q0", "q1", "q2", "q3"],
  alfabeto: ["a", "b"],
  inicial: "q0",
  finales: ["q3"],
  transiciones: [
    { origen: "q0", simbolo: "a", destino: "q1" },
    { origen: "q1", simbolo: "a", destino: "q0" },
    { origen: "q1", simbolo: "b", destino: "q2" },
    { origen: "q2", simbolo: "a", destino: "q3" },
    { origen: "q3", simbolo: "a", destino: "q0" },
    { origen: "q3", simbolo: "b", destino: "q3" },
  ],
};
const layout = mod.layoutDiagram(summary);
const svg = mod.toSvg(layout);

assert.ok(svg.startsWith("<svg"), "toSvg() must start with <svg");
assert.match(svg, /role="img"/);
assert.match(svg, /<title>Diagrama del autómata<\/title>/);
assert.match(svg, /<desc>Estados, transiciones y estado inicial\.<\/desc>/);
assert.match(svg, /marker-end="url\(#arrow\)"/);

// One outer circle per state plus one inner circle per final state.
const circleCount = (svg.match(/<circle/g) ?? []).length;
assert.equal(circleCount, layout.nodes.length + summary.finales.length);

console.log("diagram-svg-ok");
"""


PLAYBACK_CONTROLS_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const mod = await import(pathToFileURL(process.env.PLAYBACK_MODULE).href);
assert.equal(typeof mod.createPlayback, "function");

const steps = [
  { paso: 1, origen: "q0", simbolo: "a", destino: "q1", transicion_faltante: false },
  { paso: 2, origen: "q1", simbolo: "b", destino: "q2", transicion_faltante: false },
  { paso: 3, origen: "q2", simbolo: "a", destino: "q3", transicion_faltante: false },
];
const stepsBefore = JSON.parse(JSON.stringify(steps));

function fakeScheduler() {
  const calls = [];
  const cancelled = [];
  return {
    calls,
    cancelled,
    schedule(callback, intervalMs) {
      const handle = Object.freeze({
        kind: "timeout",
        id: calls.length + 1,
        token: Symbol("timeout"),
      });
      calls.push({ callback, intervalMs, handle });
      return handle;
    },
    cancel(handle) {
      cancelled.push(handle);
    },
  };
}

function makePlayback(fake, onStep = () => {}) {
  return mod.createPlayback(steps, {
    schedule: fake.schedule,
    cancel: fake.cancel,
    onStep,
  });
}

// Idle state and bounds.
{
  const fake = fakeScheduler();
  const playback = makePlayback(fake);
  const state = playback.getState();
  assert.equal(state.status, "idle");
  assert.equal(state.index, -1);
  assert.equal(state.activeStep, null);
  assert.equal(state.canPrev, false);
  assert.equal(state.canNext, true);
}

// play() emits step 0 and schedules with the explicit default interval.
{
  const fake = fakeScheduler();
  const emitted = [];
  const playback = makePlayback(fake, (step, state) => emitted.push({ step, state }));
  playback.play();

  assert.equal(playback.getState().status, "playing");
  assert.equal(playback.getState().index, 0);
  assert.deepEqual(playback.getState().activeStep, steps[0]);
  assert.equal(fake.calls.length, 1);
  assert.equal(fake.calls[0].intervalMs, 500);
  assert.equal(typeof fake.calls[0].callback, "function");
  assert.equal(typeof fake.calls[0].handle, "object");
  assert.deepEqual(emitted.at(-1).step, steps[0]);

  // One tick advances one step; the same interval callback is reused.
  fake.calls[0].callback();
  assert.equal(playback.getState().status, "playing");
  assert.equal(playback.getState().index, 1);
  assert.deepEqual(playback.getState().activeStep, steps[1]);
  assert.deepEqual(emitted.at(-1).step, steps[1]);

  // Reaching the last step finishes and cancels the opaque handle.
  fake.calls[0].callback();
  assert.equal(playback.getState().status, "finished");
  assert.equal(playback.getState().index, 2);
  assert.equal(playback.getState().canNext, false);
  assert.deepEqual(playback.getState().activeStep, steps[2]);
  assert.deepEqual(emitted.at(-1).step, steps[2]);
  assert.equal(fake.cancelled.length, 1);
  assert.equal(fake.cancelled[0], fake.calls[0].handle);
}

// pause() cancels without changing the active step.
{
  const fake = fakeScheduler();
  const playback = makePlayback(fake);
  playback.play();
  const handle = fake.calls[0].handle;
  playback.pause();
  assert.equal(playback.getState().status, "paused");
  assert.equal(playback.getState().index, 0);
  assert.equal(fake.cancelled.length, 1);
  assert.equal(fake.cancelled[0], handle);
}

// next()/prev() are stepwise, pause playback, and clamp at bounds.
{
  const fake = fakeScheduler();
  const emitted = [];
  const playback = makePlayback(fake, (step, state) => emitted.push({ step, state }));
  playback.next();
  assert.equal(playback.getState().status, "paused");
  assert.equal(playback.getState().index, 0);
  assert.equal(playback.getState().canPrev, false);

  playback.next();
  assert.equal(playback.getState().index, 1);
  playback.next();
  assert.equal(playback.getState().index, 2);
  assert.equal(playback.getState().status, "finished");
  assert.equal(playback.getState().canNext, false);

  const emittedAtLast = emitted.length;
  playback.next();
  assert.equal(playback.getState().index, 2);
  assert.equal(playback.getState().status, "finished");
  assert.equal(
    emitted.length,
    emittedAtLast,
    "next() at the last step must not advance or emit again",
  );

  playback.prev();
  assert.equal(playback.getState().status, "paused");
  assert.equal(playback.getState().index, 1);
  playback.prev();
  assert.equal(playback.getState().index, 0);
  assert.equal(playback.getState().canPrev, false);

  const emittedAtFirst = emitted.length;
  playback.prev();
  assert.equal(playback.getState().index, 0);
  assert.equal(
    emitted.length,
    emittedAtFirst,
    "prev() at the first step must not move or emit again",
  );

  playback.reset();
  assert.equal(playback.getState().status, "idle");
  assert.equal(playback.getState().index, -1);
  assert.equal(playback.getState().activeStep, null);
  assert.equal(playback.getState().canPrev, false);
  assert.equal(playback.getState().canNext, true);
}

// play() after pause schedules again with 500.
{
  const fake = fakeScheduler();
  const playback = makePlayback(fake);
  playback.play();
  playback.pause();
  playback.play();
  assert.equal(fake.calls.length, 2);
  assert.equal(fake.calls[1].intervalMs, 500);
}

assert.deepEqual(steps, stepsBefore, "createPlayback must not mutate the steps array");

// Labels are presentation constants; checked after behavior so the Red fails
// on controller behavior, not on the existence of the constant.
assert.equal(typeof mod.PLAYBACK_LABELS, "object");
assert.deepEqual(mod.PLAYBACK_LABELS, {
  play: "Reproducir",
  pause: "Pausar",
  next: "Paso siguiente",
  prev: "Paso anterior",
  reset: "Reiniciar",
});
assert.ok(Object.isFrozen(mod.PLAYBACK_LABELS));

console.log("playback-controls-ok");
"""


PLAYBACK_REDUCED_MOTION_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const mod = await import(pathToFileURL(process.env.PLAYBACK_MODULE).href);
assert.equal(typeof mod.createPlayback, "function");

const steps = [
  { paso: 1, origen: "q0", simbolo: "a", destino: "q1", transicion_faltante: false },
  { paso: 2, origen: "q1", simbolo: "b", destino: "q2", transicion_faltante: false },
  { paso: 3, origen: "q2", simbolo: "a", destino: "q3", transicion_faltante: false },
];
const stepsBefore = JSON.parse(JSON.stringify(steps));

const calls = [];
const cancelled = [];
const emitted = [];
const playback = mod.createPlayback(steps, {
  reducedMotion: true,
  schedule(callback, intervalMs) {
    calls.push({ callback, intervalMs });
    return { kind: "timeout", id: calls.length };
  },
  cancel(handle) {
    cancelled.push(handle);
  },
  onStep(step, state) {
    emitted.push({ step, state });
  },
});

playback.play();
assert.equal(calls.length, 0, "reduced motion must not schedule a timer");
assert.equal(cancelled.length, 0, "reduced motion must not cancel a timer");
assert.equal(playback.getState().status, "finished");
assert.equal(playback.getState().index, 2);
assert.deepEqual(playback.getState().activeStep, steps[2]);
assert.deepEqual(emitted.at(-1).step, steps[2], "reduced motion must emit the last step");
assert.equal(emitted.at(-1).state.status, "finished");
assert.deepEqual(steps, stepsBefore, "createPlayback must not mutate the steps array");

console.log("playback-reduced-motion-ok");
"""


PLAYBACK_REDUCED_STEPPING_SCRIPT = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const mod = await import(pathToFileURL(process.env.PLAYBACK_MODULE).href);
assert.equal(typeof mod.createPlayback, "function");

const steps = [
  { paso: 1, origen: "q0", simbolo: "a", destino: "q1", transicion_faltante: false },
  { paso: 2, origen: "q1", simbolo: "b", destino: "q2", transicion_faltante: false },
  { paso: 3, origen: "q2", simbolo: "a", destino: "q3", transicion_faltante: false },
];
const stepsBefore = JSON.parse(JSON.stringify(steps));

const calls = [];
const emitted = [];
const playback = mod.createPlayback(steps, {
  reducedMotion: true,
  schedule(callback, intervalMs) {
    calls.push({ callback, intervalMs });
    return { kind: "timeout", id: calls.length };
  },
  cancel() {},
  onStep(step, state) {
    emitted.push({ step, state });
  },
});

playback.reset();
assert.equal(playback.getState().status, "idle");

playback.next();
assert.equal(playback.getState().index, 0);
assert.equal(playback.getState().status, "paused");

playback.next();
assert.equal(playback.getState().index, 1);
playback.next();
assert.equal(playback.getState().index, 2);
assert.equal(playback.getState().status, "finished");

const emittedAtLast = emitted.length;
playback.next();
assert.equal(playback.getState().index, 2);
assert.equal(playback.getState().status, "finished");
assert.equal(
  emitted.length,
  emittedAtLast,
  "next() at the last step must not advance or emit again",
);

playback.prev();
assert.equal(playback.getState().index, 1);
assert.equal(playback.getState().status, "paused");
playback.prev();
assert.equal(playback.getState().index, 0);

const emittedAtFirst = emitted.length;
playback.prev();
assert.equal(playback.getState().index, 0);
assert.equal(
  emitted.length,
  emittedAtFirst,
  "prev() at the first step must not move or emit again",
);

assert.equal(calls.length, 0, "manual stepping must not schedule a timer");
assert.deepEqual(steps, stepsBefore, "createPlayback must not mutate the steps array");

console.log("playback-reduced-stepping-ok");
"""


UPCOMING_READ_ONLY_EXAMPLES_SCRIPT = r"""
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const mod = await import(pathToFileURL(process.env.UPCOMING_MODULE).href);
assert.equal(typeof mod.buildUpcomingExamples, "function");

const calls = [];
const getEjemplo = async (nombre) => {
  calls.push(nombre);
  return readFile(join(process.env.UPCOMING_FIXTURES, nombre), "utf8");
};

const examples = await mod.buildUpcomingExamples({ getEjemplo });
assert.deepEqual(calls, ["afn_ejemplo.json", "afn_lambda_ejemplo.json"]);
assert.equal(examples.length, 2);

const afn = examples[0];
assert.equal(afn.nombre, "afn_ejemplo.json");
assert.equal(afn.tipo, "AFN");
assert.deepEqual(afn.estados, ["q0", "q1", "q2"]);
assert.deepEqual(afn.alfabeto, ["a", "b"]);
assert.deepEqual(afn.transiciones, [
  "q0 --a--> q0, q1",
  "q0 --b--> q0",
  "q1 --b--> q2",
  "q2 --a--> q2",
  "q2 --b--> ∅",
]);

const lambda = examples[1];
assert.equal(lambda.nombre, "afn_lambda_ejemplo.json");
assert.equal(lambda.tipo, "AFN-λ");
assert.deepEqual(lambda.estados, ["q0", "q1", "q2"]);
assert.deepEqual(lambda.alfabeto, ["a", "b"]);
assert.deepEqual(lambda.transiciones, [
  "q0 --a--> q1",
  "q0 --λ--> q2",
  "q1 --b--> q2",
  "q1 --λ--> q1",
  "q2 --a--> q2",
]);

console.log("upcoming-read-only-examples-ok");
"""


UPCOMING_NO_CONTROLS_SCRIPT = r"""
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const mod = await import(pathToFileURL(process.env.UPCOMING_MODULE).href);
assert.equal(typeof mod.buildUpcomingExamples, "function");

const getEjemplo = async (nombre) =>
  readFile(join(process.env.UPCOMING_FIXTURES, nombre), "utf8");

const examples = await mod.buildUpcomingExamples({ getEjemplo });
assert.equal(examples.length, 2, "expected both upcoming examples");

const descriptorKeys = ["nombre", "tipo", "estados", "alfabeto", "transiciones"];
for (const [index, example] of examples.entries()) {
  assert.deepEqual(
    Object.keys(example).sort(),
    [...descriptorKeys].sort(),
    `examples[${index}] must expose exactly the read-only descriptor keys`,
  );
}

const controlTags = new Set(["button", "input", "select", "textarea"]);
const controlKeys = new Set([
  "onclick",
  "onchange",
  "onsubmit",
  "oninput",
  "data-action",
  "data-simulate",
  "data-validate",
  "data-execute",
]);

function assertNoControls(value, path = "examples") {
  if (Array.isArray(value)) {
    value.forEach((item, index) => assertNoControls(item, `${path}[${index}]`));
    return;
  }
  if (value === null || typeof value !== "object") {
    return;
  }
  if ("tag" in value) {
    assert.ok(
      !controlTags.has(String(value.tag).toLowerCase()),
      `${path}.tag must not be a control (${value.tag})`,
    );
  }
  for (const [key, child] of Object.entries(value)) {
    assert.ok(
      !controlKeys.has(key.toLowerCase()),
      `${path}.${key} must not be a control or event handler`,
    );
    assertNoControls(child, `${path}.${key}`);
  }
}

assertNoControls(examples);

const serialized = JSON.stringify(examples);
assert.doesNotMatch(serialized, /<button/i);
assert.doesNotMatch(serialized, /<input/i);
assert.doesNotMatch(serialized, /<select/i);
assert.doesNotMatch(serialized, /<textarea/i);
assert.doesNotMatch(serialized, /onclick\s*=/i);

console.log("upcoming-no-controls-ok");
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


def test_front_diagram_layout() -> None:
    result = _run_diagram_script(DIAGRAM_LAYOUT_SCRIPT)
    _assert_node_ok(result)


def test_front_diagram_labels() -> None:
    result = _run_diagram_script(DIAGRAM_LABELS_SCRIPT)
    _assert_node_ok(result)


def test_front_diagram_highlight() -> None:
    result = _run_diagram_script(DIAGRAM_HIGHLIGHT_SCRIPT)
    _assert_node_ok(result)


def test_front_diagram_svg() -> None:
    result = _run_diagram_script(DIAGRAM_SVG_SCRIPT)
    _assert_node_ok(result)


def test_front_playback_controls() -> None:
    result = _run_playback_script(PLAYBACK_CONTROLS_SCRIPT)
    _assert_node_ok(result)


def test_front_reduced_motion() -> None:
    result = _run_playback_script(PLAYBACK_REDUCED_MOTION_SCRIPT)
    _assert_node_ok(result)


def test_front_reduced_stepping() -> None:
    result = _run_playback_script(PLAYBACK_REDUCED_STEPPING_SCRIPT)
    _assert_node_ok(result)


def test_upcoming_read_only_examples() -> None:
    result = _run_upcoming_script(UPCOMING_READ_ONLY_EXAMPLES_SCRIPT)
    _assert_node_ok(result)


def test_upcoming_no_controls() -> None:
    result = _run_upcoming_script(UPCOMING_NO_CONTROLS_SCRIPT)
    _assert_node_ok(result)
    # Module contract only: the descriptor has no controls, and this module
    # must not fetch directly. URL/error handling stays in api.getEjemplo.
    source = UPCOMING_MODULE.read_text(encoding="utf-8")
    assert "fetch(" not in source
    assert "fetch (" not in source


def _css() -> str:
    return STYLES_CSS.read_text(encoding="utf-8")


def _css_block(css: str, header: str) -> str:
    match = re.search(rf"{re.escape(header)}\s*\{{(?P<body>.*?)\n\}}", css, re.S)
    assert match, f"missing CSS block: {header}"
    return match.group("body")


def test_front_theme_tokens() -> None:
    root = _css_block(_css(), ":root")
    for token, value in THEME_TOKENS.items():
        assert re.search(
            rf"{re.escape(token)}\s*:\s*{re.escape(value)}\s*;",
            root,
            re.I,
        ), f"missing theme token {token}: {value}"
    sidebar = re.search(r"--sidebar\s*:\s*(\d+)px\s*;", root)
    assert sidebar, "missing --sidebar token"
    assert 320 <= int(sidebar.group(1)) <= 360, "--sidebar must be 320-360px"
    assert re.search(r"--max-width\s*:\s*1440px\s*;", root), (
        "missing --max-width: 1440px"
    )


def test_front_responsive() -> None:
    css = _css()
    assert "box-sizing: border-box" in css
    desktop = _css_block(css, "@media (min-width: 1024px)")
    assert re.search(
        r"grid-template-columns:\s*var\(--sidebar\)\s+minmax\(0,\s*1fr\)\s*;",
        desktop,
    ), "desktop layout must use sidebar + fluid main"
    assert re.search(r"max-width:\s*var\(--max-width\)\s*;", desktop), (
        "desktop layout must cap at --max-width"
    )
    tablet = _css_block(css, "@media (min-width: 768px) and (max-width: 1023px)")
    assert re.search(
        r"grid-template-columns:\s*minmax\(0,\s*1fr\)\s*;",
        tablet,
    ), "tablet layout must be single column"


def test_front_reduced_motion_css() -> None:
    reduced = _css_block(_css(), "@media (prefers-reduced-motion: reduce)")
    assert "animation-duration: 0.01ms !important" in reduced
    assert "animation-iteration-count: 1 !important" in reduced
    assert "transition-duration: 0.01ms !important" in reduced
    assert "scroll-behavior: auto !important" in reduced


@pytest.mark.parametrize(
    "path",
    [STYLES_CSS, INDEX_HTML],
    ids=["styles", "index"],
)
def test_front_no_build(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    assert "@import" not in text
    assert "url(http" not in text
    assert "//cdn" not in text
    assert "@tailwind" not in text
    assert "@apply" not in text
    assert "http://" not in text
    assert "https://" not in text
    assert "fonts.googleapis.com" not in text
    assert "fonts.gstatic.com" not in text
    assert "cdnjs" not in text
    assert "unpkg.com" not in text
    assert "jsdelivr" not in text
