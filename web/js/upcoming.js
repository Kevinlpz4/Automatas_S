const EXAMPLE_NAMES = ["afn_ejemplo.json", "afn_lambda_ejemplo.json"];

function transitionLines(transiciones) {
  const lines = [];
  for (const [origen, porSimbolo] of Object.entries(transiciones ?? {})) {
    for (const [simbolo, destinos] of Object.entries(porSimbolo ?? {})) {
      const destinosTexto =
        Array.isArray(destinos) && destinos.length > 0
          ? destinos.join(", ")
          : "∅";
      lines.push(`${origen} --${simbolo}--> ${destinosTexto}`);
    }
  }
  return lines;
}

export async function buildUpcomingExamples({ getEjemplo }) {
  const examples = [];
  for (const nombre of EXAMPLE_NAMES) {
    const texto = await getEjemplo(nombre);
    const data = JSON.parse(texto);
    examples.push({
      nombre,
      tipo: data.tipo,
      estados: data.estados.map(String),
      alfabeto: data.alfabeto.map(String),
      transiciones: transitionLines(data.transiciones),
    });
  }
  return examples;
}
