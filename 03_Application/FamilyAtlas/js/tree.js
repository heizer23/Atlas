import { lifespan } from "./format.js";

export function renderTree(container, data, focusedId, onSelect, onFullscreen) {
  const focused = data.peopleById.get(focusedId);
  const spouse = focused.spouse ? data.peopleById.get(focused.spouse) : null;
  const parents = (focused.parents || []).map((id) => data.peopleById.get(id)).filter(Boolean);
  const children = (focused.children || []).map((id) => data.peopleById.get(id)).filter(Boolean);

  const coupleRow = [focused, spouse].filter(Boolean);

  container.innerHTML = `
    <div class="tree-header">
      <h2>Stammbaum</h2>
      <button class="tree-fullscreen-btn" title="Vollständigen Stammbaum anzeigen">⛶ Vollbild</button>
    </div>
    <div class="tree-row tree-row--parents">${parents.length ? parents.map((p) => nodeHtml(p, focusedId)).join("") : emptyNodeHtml()}</div>
    <div class="tree-row">${coupleRow.map((p) => nodeHtml(p, focusedId)).join("")}</div>
    <div class="tree-row">${children.length ? children.map((p) => nodeHtml(p, focusedId)).join("") : emptyNodeHtml()}</div>
  `;

  container.querySelectorAll(".tree-node[data-person-id]").forEach((el) => {
    el.addEventListener("click", () => onSelect(el.dataset.personId));
  });
  container.querySelector(".tree-fullscreen-btn").addEventListener("click", onFullscreen);
}

function nodeHtml(person, focusedId) {
  const focusedClass = person.id === focusedId ? " is-focused" : "";
  return `
    <div class="tree-node${focusedClass}" data-person-id="${person.id}">
      <span class="name">${person.name}</span>
      <span class="years">${lifespan(person)}</span>
    </div>
  `;
}

function emptyNodeHtml() {
  return `<div class="tree-node tree-node--empty">unbekannt</div>`;
}
