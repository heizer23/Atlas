import { lifespan } from "./format.js";

// Gleicher Maßstab wie die Zeitleiste (timeline.js): 2cm = 10 Jahre bei 96dpi.
const PX_PER_YEAR = 7.56;
const ROW_HEIGHT = 130;
const NODE_WIDTH = 130;
const NODE_HEIGHT = 52;
const MIN_NODE_GAP = 18;
const TOP_PADDING = 60;
const LEFT_PADDING = 40;
const TICK_STEP_YEARS = 10;
const ASSUMED_GENERATION_GAP = 27; // Jahre, nur zur Schätzung fehlender Geburtsjahre

let overlayEl, canvasEl, onSelectCb;

export function initFullTree(onSelect) {
  onSelectCb = onSelect;

  overlayEl = document.createElement("div");
  overlayEl.className = "fulltree-overlay";
  overlayEl.hidden = true;
  overlayEl.innerHTML = `
    <div class="fulltree-box">
      <div class="fulltree-toolbar">
        <span class="fulltree-title">Vollständiger Stammbaum</span>
        <span class="fulltree-hint">Position und Abstand entsprechen dem Geburtsjahr (2cm = 10 Jahre). „ca.” = Geburtsjahr nicht belegt, geschätzt. Personen ganz ohne Zeitanker (kein Geburtsjahr, kein Ehepartner, keine Kinder) werden hier nicht angezeigt.</span>
        <button class="fulltree-close" aria-label="Schließen">&times;</button>
      </div>
      <div class="fulltree-scroll"><div class="fulltree-canvas"></div></div>
    </div>
  `;
  document.body.appendChild(overlayEl);
  canvasEl = overlayEl.querySelector(".fulltree-canvas");

  overlayEl.querySelector(".fulltree-close").addEventListener("click", closeFullTree);
  overlayEl.addEventListener("click", (e) => {
    if (e.target === overlayEl) closeFullTree();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !overlayEl.hidden) closeFullTree();
  });
}

export function openFullTree(data, focusedId) {
  canvasEl.innerHTML = buildFullTreeHtml(data, focusedId);
  canvasEl.querySelectorAll(".fulltree-node[data-person-id]").forEach((el) => {
    el.addEventListener("click", () => {
      onSelectCb(el.dataset.personId);
      closeFullTree();
    });
  });
  overlayEl.hidden = false;

  const focusedEl = canvasEl.querySelector(".fulltree-node.is-focused");
  if (focusedEl) focusedEl.scrollIntoView({ block: "center", inline: "center" });
}

function closeFullTree() {
  overlayEl.hidden = true;
}

function buildFullTreeHtml(data, focusedId) {
  const people = data.people;
  const byId = data.peopleById;

  const generation = computeGenerations(people, byId);
  const yearById = new Map(people.map((p) => [p.id, estimateYear(p, byId)]));

  const knownYears = [...yearById.values()].filter(Boolean).map((y) => y.year);
  const minYear = Math.floor(Math.min(...knownYears) / TICK_STEP_YEARS) * TICK_STEP_YEARS;
  const maxYear = Math.ceil(Math.max(...knownYears) / TICK_STEP_YEARS) * TICK_STEP_YEARS;
  const maxGen = Math.max(...generation.values());

  const positions = layoutPositions(people, generation, yearById, minYear);

  const totalWidth = Math.max(
    LEFT_PADDING + (maxYear - minYear) * PX_PER_YEAR + NODE_WIDTH,
    ...[...positions.values()].map((p) => p.displayX + NODE_WIDTH + LEFT_PADDING)
  );
  const totalHeight = TOP_PADDING + (maxGen + 1) * ROW_HEIGHT;

  return `
    <div class="fulltree-inner" style="width:${totalWidth}px; height:${totalHeight}px;">
      <svg class="fulltree-svg" width="${totalWidth}" height="${totalHeight}">
        ${axisSvg(minYear, maxYear, totalHeight)}
        ${people.map((p) => tickSvg(positions.get(p.id))).join("")}
        ${connectorsSvg(people, byId, positions)}
      </svg>
      ${people.map((p) => nodeHtml(p, positions.get(p.id), yearById.get(p.id), focusedId)).join("")}
    </div>
  `;
}

// Generation = Länge des längsten Eltern-Kind-Pfads von einer Wurzel (Person
// ohne bekannte Eltern) aus. Ehepartner werden danach auf die jeweils höhere
// Generation des Paares angeglichen, damit Paare in derselben Zeile stehen.
function computeGenerations(people, byId) {
  const gen = new Map();

  function resolve(id, seen) {
    if (gen.has(id)) return gen.get(id);
    if (seen.has(id)) return 0;
    seen.add(id);
    const person = byId.get(id);
    const parents = (person.parents || []).filter((pid) => byId.has(pid));
    const g = parents.length ? Math.max(...parents.map((pid) => resolve(pid, seen))) + 1 : 0;
    gen.set(id, g);
    return g;
  }

  people.forEach((p) => resolve(p.id, new Set()));

  let changed = true;
  while (changed) {
    changed = false;
    for (const p of people) {
      if (!p.spouse || !byId.has(p.spouse)) continue;
      const g = Math.max(gen.get(p.id), gen.get(p.spouse));
      if (gen.get(p.id) !== g) { gen.set(p.id, g); changed = true; }
      if (gen.get(p.spouse) !== g) { gen.set(p.spouse, g); changed = true; }
    }
  }

  return gen;
}

// Bekanntes Geburtsjahr wird direkt übernommen. Fehlt es, wird es geschätzt:
// zuerst vom Geburtsjahr des Ehepartners, sonst vom frühesten Kind minus
// ASSUMED_GENERATION_GAP. Nur die Position nutzt die Schätzung — das
// angezeigte Label (lifespan()) bleibt bei "?", wenn das Jahr nicht belegt ist.
function estimateYear(person, byId, seen = new Set()) {
  if (person.birth_year != null) return { year: person.birth_year, estimated: false };
  if (seen.has(person.id)) return null;
  seen.add(person.id);

  if (person.spouse && byId.has(person.spouse)) {
    const s = estimateYear(byId.get(person.spouse), byId, seen);
    if (s) return { year: s.year, estimated: true };
  }

  const childYears = (person.children || [])
    .map((id) => byId.get(id))
    .filter(Boolean)
    .map((child) => estimateYear(child, byId, seen))
    .filter(Boolean)
    .map((r) => r.year);
  if (childYears.length) return { year: Math.min(...childYears) - ASSUMED_GENERATION_GAP, estimated: true };

  return null;
}

// Pro Generationszeile: wahre Position aus dem Geburtsjahr, dann wie in
// timeline.js Mindestabstand zwischen Boxen erzwingen, damit sich Personen
// mit knapp beieinanderliegenden Geburtsjahren nicht überlappen.
function layoutPositions(people, generation, yearById, minYear) {
  const rows = new Map();
  for (const p of people) {
    if (!yearById.get(p.id)) continue; // kein Geburtsjahr, kein Ehepartner- oder Kind-Anker -> keine Position bestimmbar
    const g = generation.get(p.id);
    if (!rows.has(g)) rows.set(g, []);
    rows.get(g).push(p);
  }

  const positions = new Map();
  for (const [g, rowPeople] of rows) {
    const entries = rowPeople
      .map((p) => ({ id: p.id, trueX: LEFT_PADDING + (yearById.get(p.id).year - minYear) * PX_PER_YEAR }))
      .sort((a, b) => a.trueX - b.trueX);

    let lastDisplayX = -Infinity;
    for (const e of entries) {
      const displayX = Math.max(e.trueX, lastDisplayX + NODE_WIDTH + MIN_NODE_GAP);
      lastDisplayX = displayX;
      positions.set(e.id, { trueX: e.trueX, displayX, y: TOP_PADDING + g * ROW_HEIGHT });
    }
  }
  return positions;
}

function axisSvg(minYear, maxYear, totalHeight) {
  const marks = [];
  for (let y = minYear; y <= maxYear; y += TICK_STEP_YEARS) {
    const x = LEFT_PADDING + (y - minYear) * PX_PER_YEAR;
    marks.push(`
      <line x1="${x}" y1="${TOP_PADDING - 16}" x2="${x}" y2="${totalHeight}" class="fulltree-gridline" />
      <text x="${x}" y="${TOP_PADDING - 22}" class="fulltree-axis-label" text-anchor="middle">${y}</text>
    `);
  }
  return marks.join("");
}

function tickSvg(pos) {
  if (!pos) return "";
  const tickY = pos.y - 10;
  const boxTopX = pos.displayX + NODE_WIDTH / 2;
  return `
    <circle cx="${pos.trueX}" cy="${tickY}" r="2.5" class="fulltree-tick" />
    <line x1="${pos.trueX}" y1="${tickY}" x2="${boxTopX}" y2="${pos.y}" class="fulltree-nudge" />
  `;
}

function connectorsSvg(people, byId, positions) {
  const lines = [];

  for (const p of people) {
    const pos = positions.get(p.id);
    if (!pos) continue;

    if (p.spouse && byId.has(p.spouse) && p.id < p.spouse) {
      const sPos = positions.get(p.spouse);
      if (sPos && sPos.y === pos.y) {
        const y = pos.y + NODE_HEIGHT / 2;
        const x1 = Math.min(pos.displayX, sPos.displayX) + NODE_WIDTH;
        const x2 = Math.max(pos.displayX, sPos.displayX);
        lines.push(`<line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" class="fulltree-marriage" />`);
      }
    }

    const parentPositions = (p.parents || [])
      .filter((id) => byId.has(id))
      .map((id) => positions.get(id))
      .filter(Boolean);
    if (parentPositions.length) {
      const parentY = parentPositions[0].y + NODE_HEIGHT;
      const anchorX = parentPositions.reduce((sum, pp) => sum + pp.displayX + NODE_WIDTH / 2, 0) / parentPositions.length;
      const childX = pos.displayX + NODE_WIDTH / 2;
      const midY = parentY + (pos.y - parentY) / 2;
      lines.push(
        `<polyline points="${anchorX},${parentY} ${anchorX},${midY} ${childX},${midY} ${childX},${pos.y}" class="fulltree-descent" />`
      );
    }
  }

  return lines.join("");
}

function nodeHtml(person, pos, yearInfo, focusedId) {
  if (!pos) return "";
  const focusedClass = person.id === focusedId ? " is-focused" : "";
  const estimatedBadge = yearInfo?.estimated ? `<span class="fulltree-estimated" title="Geburtsjahr nicht belegt, geschätzt">ca.</span>` : "";
  return `
    <div class="fulltree-node${focusedClass}" data-person-id="${person.id}"
         style="left:${pos.displayX}px; top:${pos.y}px; width:${NODE_WIDTH}px; height:${NODE_HEIGHT}px;">
      <span class="name">${person.name}</span>
      <span class="years">${estimatedBadge}${lifespan(person)}</span>
    </div>
  `;
}
