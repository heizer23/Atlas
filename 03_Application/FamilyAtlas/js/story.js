import { lifespan } from "./format.js";
import { primaryScreenshotForEvent, sourceById } from "./sources.js";

export function renderStory(titleEl, storyEl, atmosphereEl, data, sourcesData, focusedId) {
  const person = data.peopleById.get(focusedId);

  titleEl.innerHTML = `<h1>${person.name}</h1>`;

  const era = person.living ? lifespan(person) : `ca. ${lifespan(person)}`;

  if (person.image) {
    atmosphereEl.innerHTML = `<img src="assets/${person.image}" alt="${person.name}" loading="lazy" />`;
    atmosphereEl.setAttribute("data-caption", `${person.profession || "Lebenswelt"}, ${era}`);
  } else {
    atmosphereEl.innerHTML = "";
    atmosphereEl.setAttribute(
      "data-caption",
      person.has_data
        ? `Atmosphärisches Bild (Platzhalter) — ${person.profession || "Lebenswelt"}, ${era}`
        : "Kein Bild hinterlegt"
    );
  }

  if (!person.has_data) {
    storyEl.innerHTML = `<p class="empty-note">Noch nicht dokumentiert. Diese Person wartet auf Quellen aus dem Upload-Ordner.</p>`;
    return;
  }

  storyEl.innerHTML = `<div class="prose">${renderProse(person.prose, sourcesData)}</div>`;

  storyEl.querySelectorAll(".inline-source").forEach((btn) => {
    btn.addEventListener("click", () => {
      const fig = storyEl.querySelector(`.beleg-figure[data-event-id="${btn.dataset.eventId}"]`);
      if (fig) fig.hidden = !fig.hidden;
    });
  });
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
    const shot = primaryScreenshotForEvent(sourcesData, eventId);
    if (!shot) return "";
    eventIds.push(eventId);
    return ` <button class="inline-source" data-event-id="${eventId}" title="Beleg ein-/ausblenden">Beleg</button>`;
  });
  const figures = eventIds.map((id) => belegFigureHtml(id, sourcesData)).join("");
  return `<p>${textHtml}</p>${figures}`;
}

function belegFigureHtml(eventId, sourcesData) {
  const shot = primaryScreenshotForEvent(sourcesData, eventId);
  if (!shot) return "";
  const source = sourceById(sourcesData, shot.source_id);
  return `
    <figure class="beleg-figure" data-event-id="${eventId}" hidden>
      <img src="assets/${shot.path}" alt="${shot.role}" loading="lazy" />
      <figcaption>
        ${source ? `${source.title} — ${source.archive_ref}` : shot.role}
        <span class="beleg-badge">Entwurf — nicht gegengeprüft</span>
      </figcaption>
    </figure>
  `;
}
