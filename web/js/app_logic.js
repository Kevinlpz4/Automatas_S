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
