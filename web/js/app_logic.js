const TYPE_IDS = Object.freeze({
  AFD: "type-afd",
  AFN: "type-afn",
  "AFN-λ": "type-afn-lambda",
});

const TYPE_BADGES = Object.freeze({
  disponible: "Disponible",
  proximamente: "Próximamente",
});

export function buildTypeCards(tipos) {
  return tipos.map(({ tipo, estado }) => ({
    id: TYPE_IDS[tipo],
    tipo,
    estado,
    badge: TYPE_BADGES[estado] ?? estado,
  }));
}

export function buildExampleOptions(ejemplos) {
  return ejemplos.map(({ nombre, tipo }) => ({
    value: nombre,
    label: `${nombre} (${tipo})`,
  }));
}

export function selectInitialExample(ejemplos) {
  const afd = ejemplos.find(({ tipo }) => tipo === "AFD");
  return afd ? afd.nombre : null;
}

export async function loadBootstrap({ getTipos, getEjemplos, getEjemplo }) {
  const [tipos, ejemplos] = await Promise.all([getTipos(), getEjemplos()]);
  const selectedExample = selectInitialExample(ejemplos);
  const editorText =
    selectedExample === null ? "" : await getEjemplo(selectedExample);

  return {
    typeCards: buildTypeCards(tipos),
    exampleOptions: buildExampleOptions(ejemplos),
    selectedExample,
    editorText,
  };
}

const NON_AFD_NOTICE = Object.freeze({
  AFN: "Próximamente",
  "AFN-λ": "Próximamente",
});

export function buildGatingView(state) {
  const hasSummary = state.summary !== null && state.summary !== undefined;
  const simulateDisabled = !hasSummary || !state.simularHabilitado;
  const notice = hasSummary
    ? (NON_AFD_NOTICE[state.summary.tipo] ?? null)
    : null;

  return { simulateDisabled, notice };
}

export function createInvalidationHandlers({
  invalidate,
  readFile,
  loadExample,
}) {
  return {
    onEditorInput() {
      invalidate();
    },
    onFileChange(file) {
      invalidate();
      return readFile(file);
    },
    onDrop(file) {
      invalidate();
      return readFile(file);
    },
    onExampleChange(nombre) {
      invalidate();
      return loadExample(nombre);
    },
  };
}
