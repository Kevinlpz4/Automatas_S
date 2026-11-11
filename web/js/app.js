import * as api from "./api.js";
import { loadBootstrap } from "./app_logic.js";
import { apply, clear, el, mountToast, setText, showToast } from "./dom.js";

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

bootstrap();
