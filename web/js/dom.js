export function el(tag, attrs = {}, text = "", children = []) {
  return { tag, attrs, text, children };
}

export function clear() {
  return { type: "clear" };
}

export function setText(text) {
  return { type: "text", text };
}

export function showToast(message, duracionMs = 3000) {
  return {
    ...el(
      "div",
      { class: "toast", role: "status", "aria-live": "polite" },
      message,
    ),
    duracionMs,
  };
}

export function errorCards(errores) {
  return errores.map(({ codigo, mensaje }) =>
    el("article", { class: "error-card" }, "", [
      el("span", { class: "error-code" }, codigo),
      el("p", { class: "error-message" }, mensaje),
    ]),
  );
}

export function apply(parent, descriptor) {
  if (descriptor.type === "clear") {
    parent.replaceChildren();
    return parent;
  }
  if (descriptor.type === "text") {
    parent.textContent = descriptor.text;
    return parent;
  }

  const node = document.createElement(descriptor.tag);
  for (const [name, value] of Object.entries(descriptor.attrs ?? {})) {
    node.setAttribute(name, value);
  }
  if (descriptor.text !== undefined) {
    node.textContent = descriptor.text;
  }
  for (const child of descriptor.children ?? []) {
    apply(node, child);
  }
  parent.appendChild(node);
  return node;
}

export function mountToast(container, toast, schedule = setTimeout) {
  const node = apply(container, toast);
  schedule(() => node.remove(), toast.duracionMs);
  return node;
}
