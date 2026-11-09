export class ApiError extends Error {
  constructor(errores, status) {
    super(errores?.[0]?.mensaje ?? `HTTP ${status}`);
    this.name = "ApiError";
    this.errores = errores;
    this.status = status;
  }
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (response.ok) {
    return response;
  }
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const errores = Array.isArray(payload?.errores) ? payload.errores : [];
  throw new ApiError(errores, response.status);
}

export async function getSalud() {
  const response = await request("/api/salud");
  return response.json();
}

export async function getTipos() {
  const response = await request("/api/tipos");
  return response.json();
}

export async function getEjemplos() {
  const response = await request("/api/ejemplos");
  return response.json();
}

export async function getEjemplo(nombre) {
  const response = await request(`/api/ejemplos/${encodeURIComponent(nombre)}`);
  return response.text();
}

export async function validar(textoAutomata) {
  const response = await request("/api/automatas/validar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: textoAutomata,
  });
  return response.json();
}

export async function simular(textoAutomata, palabra) {
  const response = await request("/api/automatas/simular", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ automata: textoAutomata, palabra }),
  });
  return response.json();
}
