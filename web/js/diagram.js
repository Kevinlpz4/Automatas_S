const WIDTH = 640;
const HEIGHT = 480;
const RADIUS = 28;
const MIN_ORBIT = 120;

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function nodeClass(node, highlight) {
  return [
    "node",
    node.final ? "final" : "",
    highlight?.activeNode === node.id ? "active" : "",
    highlight?.acceptedNode === node.id ? "accepted" : "",
    highlight?.warningNode === node.id ? "warning" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

function edgeClass(edge, highlight) {
  const active = highlight?.activeEdge;
  const isActive =
    active !== null &&
    active !== undefined &&
    active.from === edge.from &&
    active.to === edge.to &&
    active.label === edge.label;
  return ["edge", isActive ? "active" : ""].filter(Boolean).join(" ");
}

export function groupLabels(transiciones) {
  const groups = [];
  const index = new Map();

  for (const { origen, simbolo, destino } of transiciones) {
    const key = `${origen}\u0000${destino}`;
    let group = index.get(key);
    if (group === undefined) {
      group = { origen, destino, symbols: [] };
      index.set(key, group);
      groups.push(group);
    }
    if (!group.symbols.includes(simbolo)) {
      group.symbols.push(simbolo);
    }
  }

  return groups.map((group) => {
    const symbols = [...group.symbols].sort();
    return {
      origen: group.origen,
      destino: group.destino,
      symbols,
      label: symbols.length === 1 ? symbols[0] : `(${symbols.join(", ")})`,
    };
  });
}

export function layoutDiagram(summary) {
  const states = [...summary.estados];
  if (states.length === 0) {
    throw new Error("El resumen no contiene estados.");
  }

  const center = { x: WIDTH / 2, y: HEIGHT / 2 };
  const orbit = Math.max(
    MIN_ORBIT,
    Math.ceil((states.length * (2 * RADIUS + 24)) / (2 * Math.PI)),
  );
  const nodes = states.map((id, index) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * index) / states.length;
    return {
      id,
      x: center.x + orbit * Math.cos(angle),
      y: center.y + orbit * Math.sin(angle),
      r: RADIUS,
      initial: id === summary.inicial,
      final: summary.finales.includes(id),
    };
  });
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const groups = groupLabels(summary.transiciones);
  const pairKeys = new Set(groups.map((group) => `${group.origen}\u0000${group.destino}`));

  const edges = groups.map((group) => {
    const fromNode = byId.get(group.origen);
    const toNode = byId.get(group.destino);
    if (fromNode === undefined || toNode === undefined) {
      throw new Error(
        `Transición con estado desconocido: ${group.origen} -> ${group.destino}.`,
      );
    }

    if (group.origen === group.destino) {
      return {
        from: group.origen,
        to: group.destino,
        symbols: group.symbols,
        label: group.label,
        kind: "self",
        markerEnd: "url(#arrow)",
      };
    }

    const mutual = pairKeys.has(`${group.destino}\u0000${group.origen}`);
    const dx = toNode.x - fromNode.x;
    const dy = toNode.y - fromNode.y;
    const distance = Math.hypot(dx, dy);
    const ux = dx / distance;
    const uy = dy / distance;
    const offset = mutual ? (group.origen < group.destino ? 12 : -12) : 0;
    const nx = -uy * offset;
    const ny = ux * offset;

    return {
      from: group.origen,
      to: group.destino,
      symbols: group.symbols,
      label: group.label,
      kind: mutual ? "mutual" : "normal",
      offset,
      x1: fromNode.x + ux * RADIUS + nx,
      y1: fromNode.y + uy * RADIUS + ny,
      x2: toNode.x - ux * RADIUS + nx,
      y2: toNode.y - uy * RADIUS + ny,
      markerEnd: "url(#arrow)",
    };
  });

  const initialNode = byId.get(summary.inicial);
  const initialArrow =
    initialNode === undefined
      ? null
      : {
          fromX: initialNode.x - RADIUS - 40,
          fromY: initialNode.y,
          toX: initialNode.x - RADIUS,
          toY: initialNode.y,
          label: "inicio",
          markerEnd: "url(#arrow)",
        };

  return {
    role: "img",
    title: "Diagrama del autómata",
    desc: "Estados, transiciones y estado inicial.",
    width: WIDTH,
    height: HEIGHT,
    center,
    orbit,
    radius: RADIUS,
    nodes,
    edges,
    initialArrow,
    markers: [
      {
        id: "arrow",
        markerWidth: 10,
        markerHeight: 10,
        refX: 9,
        refY: 3,
        orient: "auto",
        path: "M0,0 L0,6 L9,3 z",
      },
    ],
    highlight: null,
  };
}

export function highlightStep(layout, step, { accepted = false, warning = false } = {}) {
  const source = step?.origen ?? null;
  const destination = step?.destino ?? null;
  const symbol = step?.simbolo ?? null;
  const activeEdge =
    destination === null
      ? null
      : layout.edges.find(
          (edge) =>
            edge.from === source &&
            edge.to === destination &&
            edge.symbols.includes(symbol),
        ) ?? null;

  return {
    ...layout,
    highlight: {
      activeNode: source,
      activeEdge:
        activeEdge === null
          ? null
          : { from: activeEdge.from, to: activeEdge.to, label: activeEdge.label },
      acceptedNode: accepted ? destination : null,
      warningNode: warning || step?.transicion_faltante ? source : null,
    },
  };
}

export function clearHighlight(layout) {
  return { ...layout, highlight: null };
}

function edgeToSvg(edge, highlight) {
  const className = escapeXml(edgeClass(edge, highlight));
  const label = escapeXml(edge.label);
  if (edge.kind === "self") {
    const node = edge._node;
    const x = node.x;
    const y = node.y;
    const r = node.r;
    const path = `M ${x - r * 0.7} ${y - r * 0.7} C ${x - r * 2.2} ${y - r * 3.2}, ${x + r * 2.2} ${y - r * 3.2}, ${x + r * 0.7} ${y - r * 0.7}`;
    return `<path d="${path}" class="${className}" marker-end="${edge.markerEnd}"/><text x="${x}" y="${y - r * 2.4}" class="edge-label">${label}</text>`;
  }

  const midX = (edge.x1 + edge.x2) / 2;
  const midY = (edge.y1 + edge.y2) / 2;
  return `<line x1="${edge.x1}" y1="${edge.y1}" x2="${edge.x2}" y2="${edge.y2}" class="${className}" marker-end="${edge.markerEnd}"/><text x="${midX}" y="${midY}" class="edge-label">${label}</text>`;
}

export function toSvg(layout) {
  const nodesById = new Map(layout.nodes.map((node) => [node.id, node]));
  const edges = layout.edges.map((edge) => ({
    ...edge,
    _node: nodesById.get(edge.from),
  }));
  const markers = layout.markers
    .map(
      (marker) =>
        `<marker id="${escapeXml(marker.id)}" markerWidth="${marker.markerWidth}" markerHeight="${marker.markerHeight}" refX="${marker.refX}" refY="${marker.refY}" orient="${escapeXml(marker.orient)}"><path d="${escapeXml(marker.path)}"/></marker>`,
    )
    .join("");
  const initialArrow =
    layout.initialArrow === null
      ? ""
      : `<line x1="${layout.initialArrow.fromX}" y1="${layout.initialArrow.fromY}" x2="${layout.initialArrow.toX}" y2="${layout.initialArrow.toY}" class="initial-arrow" marker-end="${layout.initialArrow.markerEnd}"/><text x="${(layout.initialArrow.fromX + layout.initialArrow.toX) / 2}" y="${layout.initialArrow.fromY - 8}" class="edge-label">${escapeXml(layout.initialArrow.label)}</text>`;
  const edgeMarkup = edges.map((edge) => edgeToSvg(edge, layout.highlight)).join("");
  const nodeMarkup = layout.nodes
    .map((node) => {
      const className = escapeXml(nodeClass(node, layout.highlight));
      const inner =
        node.final
          ? `<circle cx="${node.x}" cy="${node.y}" r="${node.r - 6}" class="node-inner"/>`
          : "";
      return `<circle cx="${node.x}" cy="${node.y}" r="${node.r}" class="${className}"/>${inner}<text x="${node.x}" y="${node.y}" class="node-label">${escapeXml(node.id)}</text>`;
    })
    .join("");

  return `<svg role="${escapeXml(layout.role)}" viewBox="0 0 ${layout.width} ${layout.height}" width="${layout.width}" height="${layout.height}" xmlns="http://www.w3.org/2000/svg"><title>${escapeXml(layout.title)}</title><desc>${escapeXml(layout.desc)}</desc><defs>${markers}</defs>${initialArrow}${edgeMarkup}${nodeMarkup}</svg>`;
}
