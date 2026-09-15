export async function loadSources() {
  const res = await fetch("data/sources.json");
  return await res.json();
}

export function screenshotsForEvent(sourcesData, eventId) {
  return sourcesData.screenshots.filter((s) => s.event_ids.includes(eventId));
}

export function sourceById(sourcesData, sourceId) {
  return sourcesData.sources.find((s) => s.id === sourceId);
}

export function primaryScreenshotForEvent(sourcesData, eventId) {
  const shots = screenshotsForEvent(sourcesData, eventId);
  if (!shots.length) return null;
  return shots.find((s) => s.role === "Doppelseite") || shots[0];
}

export function renderEventSources(sourcesData, eventId, eventLabel) {
  const shots = screenshotsForEvent(sourcesData, eventId);
  if (!shots.length) {
    return `<h3>${eventLabel}</h3><p>Keine Scans zu diesem Ereignis hinterlegt.</p>`;
  }

  const source = sourceById(sourcesData, shots[0].source_id);

  return `
    <h3>${eventLabel}</h3>
    <div class="lightbox-gallery">
      ${shots
        .map(
          (s) => `
        <figure>
          <img src="assets/${s.path}" alt="${s.role}" loading="lazy" />
          <figcaption>${s.role}</figcaption>
        </figure>`
        )
        .join("")}
    </div>
    ${
      source
        ? `<div class="lightbox-source">
            <p><strong>${source.title}</strong><br>${source.archive_ref}</p>
            <p>${
              source.url
                ? `<a href="${source.url}" target="_blank" rel="noopener">Quelle öffnen ↗</a> · `
                : ""
            }abgerufen am ${source.accessed_on}</p>
            <p class="lightbox-caveats">${source.caveats}</p>
          </div>`
        : ""
    }
  `;
}
