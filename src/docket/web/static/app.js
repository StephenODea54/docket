const SVG_NS = "http://www.w3.org/2000/svg";
let pinned = null;
let markerSeq = 0;

window.toggleTheme = () => {
  const root = document.documentElement;
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
  try {
    localStorage.setItem("docket-theme", root.dataset.theme);
  } catch (error) {}
};

const owner = (key) => key.slice(0, key.lastIndexOf("."));

const sides = (ra, rb) => {
  const options = [
    ["right", "left"],
    ["left", "right"],
    ["left", "left"],
    ["right", "right"],
  ];
  options.sort(
    (m, n) =>
      Math.abs(rb[m[1]] - ra[m[0]]) - Math.abs(rb[n[1]] - ra[n[0]])
  );
  return options[0];
};

const point = (wrap, box, rect, side) => ({
  x: rect[side] - box.left + wrap.scrollLeft,
  y: rect.top + rect.height / 2 - box.top + wrap.scrollTop,
});

function drawGraph(wrap) {
  const refsEl = wrap.querySelector("[data-graph-refs]");
  if (!refsEl) return;
  const refs = JSON.parse(refsEl.textContent || "[]");
  const cards = {};
  const cols = {};
  for (const card of wrap.querySelectorAll("[data-table]")) {
    cards[card.dataset.table] = card.firstElementChild || card;
  }
  for (const row of wrap.querySelectorAll("[data-col]")) {
    cols[row.dataset.col] = row;
  }
  const old = wrap.querySelector("svg.graph-lines");
  if (old) old.remove();
  const box = wrap.getBoundingClientRect();
  const plans = [];
  for (const ref of refs) {
    const a = cols[ref.a] || cards[ref.a];
    const b = cols[ref.b] || cards[ref.b];
    if (!a || !b) continue;
    plans.push({ ref, ra: a.getBoundingClientRect(), rb: b.getBoundingClientRect() });
  }
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "graph-lines");
  let markerId = null;
  if (plans.some((plan) => plan.ref.head)) {
    markerId = `graph-arrow-${++markerSeq}`;
    const defs = document.createElementNS(SVG_NS, "defs");
    const marker = document.createElementNS(SVG_NS, "marker");
    marker.setAttribute("id", markerId);
    marker.setAttribute("viewBox", "0 0 10 10");
    marker.setAttribute("refX", "9");
    marker.setAttribute("refY", "5");
    marker.setAttribute("markerWidth", "7");
    marker.setAttribute("markerHeight", "7");
    marker.setAttribute("orient", "auto-start-reverse");
    const tip = document.createElementNS(SVG_NS, "path");
    tip.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
    tip.setAttribute("fill", "currentColor");
    marker.appendChild(tip);
    defs.appendChild(marker);
    svg.appendChild(defs);
  }
  for (const { ref, ra, rb } of plans) {
    const [sa, sb] = sides(ra, rb);
    const pa = point(wrap, box, ra, sa);
    const pb = point(wrap, box, rb, sb);
    const bend = Math.max(28, Math.abs(pb.x - pa.x) / 2);
    const out = sa === "right" ? 1 : -1;
    const into = sb === "right" ? 1 : -1;
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute(
      "d",
      `M ${pa.x} ${pa.y} C ${pa.x + out * bend} ${pa.y}, ${pb.x + into * bend} ${pb.y}, ${pb.x} ${pb.y}`
    );
    path.dataset.a = ref.a;
    path.dataset.b = ref.b;
    path.dataset.ta = ref.ta;
    path.dataset.tb = ref.tb;
    if (ref.head && markerId) path.setAttribute("marker-end", `url(#${markerId})`);
    if (ref.job) {
      const title = document.createElementNS(SVG_NS, "title");
      title.textContent = ref.job;
      path.appendChild(title);
    }
    svg.appendChild(path);
  }
  svg.setAttribute("width", wrap.scrollWidth);
  svg.setAttribute("height", wrap.scrollHeight);
  wrap.appendChild(svg);
}

function applyGraph(wrap, tableKey, colKey) {
  const involved = {};
  for (const path of wrap.querySelectorAll("svg.graph-lines path[data-a]")) {
    let on = true;
    if (colKey) on = path.dataset.a === colKey || path.dataset.b === colKey;
    else if (tableKey) on = path.dataset.ta === tableKey || path.dataset.tb === tableKey;
    path.classList.toggle("edge-dim", !on);
    path.classList.toggle("edge-hot", on && !!(tableKey || colKey));
    if (on) {
      involved[path.dataset.ta] = true;
      involved[path.dataset.tb] = true;
      if (colKey) {
        involved[path.dataset.a] = true;
        involved[path.dataset.b] = true;
      }
    }
  }
  for (const card of wrap.querySelectorAll("[data-table]")) {
    const key = card.dataset.table;
    const on =
      (!tableKey && !colKey) ||
      key === tableKey ||
      involved[key] ||
      (colKey && colKey.startsWith(`${key}.`));
    card.classList.toggle("card-dim", !on);
  }
  for (const row of wrap.querySelectorAll("[data-col]")) {
    const on = !colKey || row.dataset.col === colKey || involved[row.dataset.col];
    row.classList.toggle("row-dim", !on);
  }
}

function clearGraph(wrap) {
  const marked = wrap.querySelectorAll(".edge-dim, .edge-hot, .card-dim, .row-dim");
  for (const el of marked) {
    el.classList.remove("edge-dim", "edge-hot", "card-dim", "row-dim");
  }
}

function clearAll() {
  pinned = null;
  for (const wrap of document.querySelectorAll("[data-graph]")) clearGraph(wrap);
}

function armGraph(wrap) {
  for (const card of wrap.querySelectorAll("[data-table]")) {
    card.addEventListener("mouseenter", () => {
      if (!pinned) applyGraph(wrap, card.dataset.table, null);
    });
    card.addEventListener("mouseleave", () => {
      if (!pinned) clearGraph(wrap);
    });
    card.addEventListener("click", (event) => {
      if (event.target.closest("a")) return;
      event.stopPropagation();
      const row = event.target.closest("[data-col]");
      const next = row
        ? { table: owner(row.dataset.col), col: row.dataset.col }
        : { table: card.dataset.table, col: null };
      if (pinned && pinned.table === next.table && pinned.col === next.col) {
        clearAll();
        return;
      }
      clearAll();
      pinned = next;
      applyGraph(wrap, pinned.table, pinned.col);
    });
  }
}

function initGraphs(root) {
  const wraps = [...root.querySelectorAll("[data-graph]")];
  if (root.matches && root.matches("[data-graph]")) wraps.push(root);
  for (const wrap of wraps) {
    if (!wrap.dataset.armed) {
      armGraph(wrap);
      wrap.dataset.armed = "1";
    }
    drawGraph(wrap);
  }
}

document.body.addEventListener("htmx:afterSwap", (event) => {
  pinned = null;
  initGraphs(event.detail.target);
});

window.addEventListener("resize", () => initGraphs(document));

document.addEventListener("click", (event) => {
  if (!event.target.closest("[data-graph]")) clearAll();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") clearAll();
});

initGraphs(document);
