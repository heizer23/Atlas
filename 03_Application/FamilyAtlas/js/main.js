import { loadData } from "./data.js";
import { initMap, updateMapFocus } from "./map.js";
import { renderTree } from "./tree.js";
import { renderTimeline } from "./timeline.js";
import { renderStory } from "./story.js";
import { loadSources, renderEventSources } from "./sources.js";
import { openLightbox } from "./lightbox.js";

const DEFAULT_FOCUS = "johann-1839";

const treeEl = document.getElementById("tree");
const timelineEl = document.getElementById("timeline");
const titleEl = document.getElementById("story-title");
const storyEl = document.getElementById("story");
const atmosphereEl = document.getElementById("atmosphere");

let map = null;
let focusedId = DEFAULT_FOCUS;

const [data, sourcesData] = await Promise.all([loadData(), loadSources()]);
render();

// Karte unabhängig laden: wenn sie hängt oder fehlschlägt, bleibt der Rest
// der Seite trotzdem benutzbar. map.js zeigt eigene Fehler in #map-diagnostics.
initMap()
  .then((loadedMap) => {
    map = loadedMap;
    updateMapFocus(map, data, focusedId);
  })
  .catch((err) => console.error("FamilyAtlas: Karte konnte nicht initialisiert werden.", err));

function render() {
  renderTree(treeEl, data, focusedId, setFocus);
  renderTimeline(timelineEl, data, sourcesData, focusedId, openEventSources);
  renderStory(titleEl, storyEl, atmosphereEl, data, sourcesData, focusedId);
  if (map) updateMapFocus(map, data, focusedId);
}

function setFocus(personId) {
  focusedId = personId;
  render();
}

function openEventSources(eventId, eventLabel) {
  openLightbox(renderEventSources(sourcesData, eventId, eventLabel));
}
