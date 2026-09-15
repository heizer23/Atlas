import { primaryScreenshotForEvent } from "./sources.js";
import { openLightbox } from "./lightbox.js";

const EVENT_CAPTION_LABELS = {
  birth: "Geburt",
  baptism: "Taufe",
  marriage: "Hochzeit",
  death: "Sterbeeintrag",
  burial: "Begräbnis",
};

export function renderStory(titleEl, storyEl, data, sourcesData, focusedId) {
  const person = data.peopleById.get(focusedId);

  titleEl.innerHTML = `<h1>${person.name}</h1>`;

  if (!person.has_data) {
    storyEl.innerHTML = `<p class="empty-note">Noch nicht dokumentiert. Diese Person wartet auf Quellen aus dem Upload-Ordner.</p>`;
    return;
  }

  storyEl.innerHTML = `${renderPortraits(person)}<div class="prose">${renderProse(person, data, sourcesData)}</div>`;

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

function renderProse(person, data, sourcesData) {
  if (!person.prose) return "";
  const shownShotIds = new Set();
  // Ein Beleg-Bild wird nur auf der Seite der Person gezeigt, deren eigenes
  // Ereignis es dokumentiert — nicht auf jeder Seite, die das Ereignis zur
  // Einordnung nur erwähnt (z.B. Karls Seite nennt Johanns Geburtsjahr 1839,
  // zeigt dazu aber nicht Johanns Taufeintrag).
  const ownEventIds = new Set((person.events || []).map((e) => e.id));
  return person.prose
    .split("\n\n")
    .map((paragraph) => paragraphWithBelege(paragraph, ownEventIds, data, sourcesData, shownShotIds))
    .join("");
}

function paragraphWithBelege(paragraph, ownEventIds, data, sourcesData, shownShotIds) {
  const eventIds = [];
  const textHtml = paragraph.replace(/\{\{([\w-]+)\}\}/g, (_, eventId) => {
    if (!ownEventIds.has(eventId)) return "";
    if (!primaryScreenshotForEvent(sourcesData, eventId)) return "";
    eventIds.push(eventId);
    return "";
  });
  const figures = eventIds.map((id) => belegFigureHtml(id, data, sourcesData, shownShotIds)).join("");
  return `<p>${textHtml}</p>${figures}`;
}

function belegFigureHtml(eventId, data, sourcesData, shownShotIds) {
  const shot = primaryScreenshotForEvent(sourcesData, eventId);
  if (!shot) return "";
  // Ein Event kann Birth+Baptism teilen und auf dasselbe Beleg-Bild zeigen —
  // nicht doppelt anzeigen, wenn es im selben Personenprofil schon gerendert wurde.
  if (shownShotIds.has(shot.id)) return "";
  shownShotIds.add(shot.id);
  return `
    <figure class="beleg-figure" data-event-id="${eventId}">
      <img src="assets/${shot.path}" alt="${shot.role}" loading="lazy" title="Zum Vergrößern klicken" />
      <figcaption>
        ${eventCaption(eventId, data) || shot.role}
      </figcaption>
    </figure>
  `;
}

function eventCaption(eventId, data) {
  const matches = [];
  for (const p of data.people) {
    for (const e of p.events || []) {
      if (e.id === eventId && EVENT_CAPTION_LABELS[e.type]) {
        matches.push({ person: p, event: e });
      }
    }
  }
  if (!matches.length) return null;
  const label = EVENT_CAPTION_LABELS[matches[0].event.type];
  const names = matches.map((m) => m.person.name).join(" & ");
  return `${label} ${names} ${matches[0].event.year}`;
}
