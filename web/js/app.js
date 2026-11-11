import * as api from "./api.js";
import { buildGatingView, createInvalidationHandlers, loadBootstrap } from "./app_logic.js";
import { apply, clear, el, mountToast, setText, showToast } from "./dom.js";
import { invalidate, setSummary, state } from "./state.js";

const byId = (id) => document.getElementById(id);

function applyTypeCards(cards) {
  for (const card of cards) {
    const badge = byId(card.id)?.querySelector(".badge");
    if (badge) {
      apply(badge, setText(card.badge));
    }
  }
}

function applyExampleOptions(options, selectedExample) {
  const select = byId("example-select");
  apply(select, clear());
  for (const option of options) {
    apply(select, el("option", { value: option.value }, option.label));
  }
  select.value = selectedExample ?? "";
}

function applyGatingView() {
  const view = buildGatingView(state);
  byId("simulate-button").disabled = view.simulateDisabled;
  const status = byId("summary-status");
  if (view.notice === null) {
    status.textContent = "";
  } else {
    status.textContent = view.notice;
  }
}

async function loadExample(nombre) {
  const texto = await api.getEjemplo(nombre);
  byId("automata-editor").value = texto;
  return texto;
}

async function readFile(file) {
  const texto = await file.text();
  byId("automata-editor").value = texto;
  return texto;
}

async function runHandler(action) {
  try {
    await action();
  } catch {
    mountToast(
      byId("toast-container"),
      showToast("No se pudo cargar el contenido."),
    );
  }
}

const invalidation = createInvalidationHandlers({
  invalidate,
  readFile,
  loadExample,
});

async function bootstrap() {
  try {
    const plan = await loadBootstrap({
      getTipos: api.getTipos,
      getEjemplos: api.getEjemplos,
      getEjemplo: api.getEjemplo,
    });

    applyTypeCards(plan.typeCards);
    applyExampleOptions(plan.exampleOptions, plan.selectedExample);
    byId("automata-editor").value = plan.editorText;
  } catch {
    mountToast(
      byId("toast-container"),
      showToast("No se pudieron cargar los datos iniciales."),
    );
  }
}

byId("automata-editor").addEventListener("input", () => {
  invalidation.onEditorInput();
  applyGatingView();
});

byId("file-input").addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  if (file) {
    void runHandler(() => invalidation.onFileChange(file));
    applyGatingView();
  }
});

byId("file-drop").addEventListener("dragover", (event) => {
  event.preventDefault();
});

byId("file-drop").addEventListener("drop", (event) => {
  event.preventDefault();
  const file = event.dataTransfer?.files?.[0];
  if (file) {
    void runHandler(() => invalidation.onDrop(file));
    applyGatingView();
  }
});

byId("example-select").addEventListener("change", (event) => {
  const nombre = event.target.value;
  if (nombre) {
    void runHandler(() => invalidation.onExampleChange(nombre));
    applyGatingView();
  }
});

byId("validate-button").addEventListener("click", async () => {
  try {
    const summary = await api.validar(byId("automata-editor").value);
    setSummary(summary);
  } catch {
    setSummary(null);
  }
  applyGatingView();
});

bootstrap();
