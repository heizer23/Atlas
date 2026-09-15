import { primaryScreenshotForEvent, sourceById } from "./sources.js";
import { openLightbox } from "./lightbox.js";

export function renderStory(titleEl, storyEl, data, sourcesData, focusedId) {
  const person = data.peopleById.get(focusedId);

  titleEl.innerHTML = `<h1>${person.name}</h1>`;

  if (!person.has_data) {
    storyEl.innerHTML = `<p class="empty-note">Noch nicht dokumentiert. Diese Person wartet auf Quellen aus dem Upload-Ordner.</p>`;
    return;
  }

  storyEl.innerHTML = `${renderPortraits(person)}<div class="prose">${renderProse(person.prose, sourcesData)}</div>`;

  storyEl.querySelectorAll(".beleg-figure img, .portrait img, .portrait-figure img").forEach((img) => {
    img.addEventListener("click", () => {
      openLightbox(`<img class="lightbox-fullimage" src="${img.src}" alt="${img.alt}" />`);
    });
  });
}

function renderPortraits(person) {
  if (!person.portraits || !person.portraits.length) return "";

  // Mehrere Bilder: wie Beleg-Scans neben den Text gesetzt (float, 1/3 Breite).
  if (person.portraits.length > 1) {
    return person.portraits
      .map(
        (p) => `
        <figure class="portrait-figure">
          <img src="assets/${p.path}" alt="${person.name}" loading="lazy" title="Zum Vergrößern klicken" />
        </figure>`
      )
      .join("");
  }

  // Einzelnes Bild: zentriert, eigene Breite möglich.
  const p = person.portraits[0];
  return `
    <div class="portraits">
      <figure class="portrait"${p.width ? ` style="width:${p.width}"` : ""}>
        <img src="assets/${p.path}" alt="${person.name}" loading="lazy" title="Zum Vergrößern klicken" />
      </figure>
    </div>`;
}

function renderProse(prose, sourcesData) {
  if (!prose) return "";
  return prose
    .split("\n\n")
    .map((paragraph) => paragraphWithBelege(paragraph, sourcesData))
    .join("");
}

function paragraphWithBelege(paragraph, sourcesData) {
  const eventIds = [];
  const textHtml = paragraph.replace(/\{\{([\w-]+)\}\}/g, (_, eventId) => {
    if (!primaryScreenshotForEvent(sourcesData, eventId)) return "";
    eventIds.push(eventId);
    return "";
  });
  const figures = eventIds.map((id) => belegFigureHtml(id, sourcesData)).join("");
  return `<p>${textHtml}</p>${figures}`;
}

function belegFigureHtml(eventId, sourcesData) {
  const shot = primaryScreenshotForEvent(sourcesData, eventId);
  if (!shot) return "";
  const source = sourceById(sourcesData, shot.source_id);
  return `
    <figure class="beleg-figure" data-event-id="${eventId}">
      <img src="assets/${shot.path}" alt="${shot.role}" loading="lazy" title="Zum Vergrößern klicken" />
      <figcaption>
        ${source ? `${source.title} — ${source.archive_ref}` : shot.role}
        <span class="beleg-badge">Entwurf — nicht gegengeprüft</span>
      </figcaption>
    </figure>
  `;
}
