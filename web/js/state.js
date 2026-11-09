export const state = {
  summary: null,
  result: null,
  trace: [],
  playback: null,
  simularHabilitado: false,
};

/**
 * Normalizes the empty-word aliases.
 * Assumes `value` is a string (the caller reads it from a text input).
 * @param {string} value
 * @returns {string}
 */
export function normalizeWord(value) {
  return value === "λ" || value === "epsilon" ? "" : value;
}

/**
 * Stores a validated summary and enables Simular only for AFD.
 * @param {{ tipo?: string } | null} summary
 */
export function setSummary(summary) {
  state.summary = summary;
  state.simularHabilitado = summary?.tipo === "AFD";
}

export function invalidate() {
  state.summary = null;
  state.result = null;
  state.trace = [];
  state.playback = null;
  state.simularHabilitado = false;
}
