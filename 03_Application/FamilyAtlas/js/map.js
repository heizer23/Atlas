import { personPathCoords } from "./data.js";

const FOCUS_COLOR = "#3a3630";
const FAMILY_COLOR = "#c7bfae";

function setDiagnostics(text) {
  const el = document.getElementById("map-diagnostics");
  if (el) el.textContent = text;
}

export function initMap() {
  setDiagnostics("Karte wird geladen …");

  if (typeof maplibregl === "undefined") {
    setDiagnostics("Fehler: maplibre-gl.js wurde nicht geladen (CDN/Netzwerk?). Kein Kartenobjekt verfügbar.");
    return Promise.reject(new Error("maplibregl ist nicht definiert"));
  }

  let map;
  try {
    map = new maplibregl.Map({
      container: "map",
      style: osmRasterStyle(),
      center: [9.1, 52.26],
      zoom: 7,
    });
  } catch (err) {
    setDiagnostics(`Fehler beim Erzeugen der Karte: ${err.message}`);
    return Promise.reject(err);
  }

  map.on("error", (e) => {
    const msg = (e.error && e.error.message) || String(e.error || e);
    console.error("MapLibre-Fehler:", e.error || e);
    setDiagnostics(`MapLibre-Fehler: ${msg}`);
  });

  const loadTimeout = setTimeout(() => {
    setDiagnostics("Karte lädt seit 8s nicht (load-Event nie ausgelöst) — evtl. Netzwerk/CDN blockiert.");
  }, 8000);

  return new Promise((resolve, reject) => {
    map.on("load", () => {
      clearTimeout(loadTimeout);
      try {
        map.addSource("family-lines", { type: "geojson", data: emptyFC() });
        map.addSource("family-points", { type: "geojson", data: emptyFC() });
        map.addSource("focus-lines", { type: "geojson", data: emptyFC() });
        map.addSource("focus-points", { type: "geojson", data: emptyFC() });

        map.addLayer(lineLayer("family-lines-layer", "family-lines", FAMILY_COLOR, 2));
        map.addLayer(pointLayer("family-points-layer", "family-points", FAMILY_COLOR, 5));
        map.addLayer(lineLayer("focus-lines-layer", "focus-lines", FOCUS_COLOR, 3));
        map.addLayer(pointLayer("focus-points-layer", "focus-points", FOCUS_COLOR, 6));

        setDiagnostics("Karte geladen, Layer angelegt.");
        resolve(map);
      } catch (err) {
        setDiagnostics(`Fehler beim Anlegen der Kartenebenen: ${err.message}`);
        reject(err);
      }
    });
  });
}

export function updateMapFocus(map, data, focusedId) {
  const focusFC = { type: "FeatureCollection", features: [] };
  const familyFC = { type: "FeatureCollection", features: [] };
  const focusPointsFC = { type: "FeatureCollection", features: [] };
  const familyPointsFC = { type: "FeatureCollection", features: [] };
  const allCoords = [];

  for (const person of data.people) {
    const coords = personPathCoords(person, data);
    if (coords.length === 0) continue;
    allCoords.push(...coords);

    const isFocused = person.id === focusedId;
    const lineTarget = isFocused ? focusFC : familyFC;
    const pointTarget = isFocused ? focusPointsFC : familyPointsFC;

    if (coords.length > 1) {
      lineTarget.features.push({
        type: "Feature",
        geometry: { type: "LineString", coordinates: coords },
        properties: { personId: person.id },
      });
    }
    for (const coord of coords) {
      pointTarget.features.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: coord },
        properties: { personId: person.id },
      });
    }
  }

  try {
    map.getSource("focus-lines").setData(focusFC);
    map.getSource("family-lines").setData(familyFC);
    map.getSource("focus-points").setData(focusPointsFC);
    map.getSource("family-points").setData(familyPointsFC);
  } catch (err) {
    setDiagnostics(`Fehler beim Setzen der Kartendaten: ${err.message}`);
    console.error(err);
    return;
  }

  setDiagnostics(
    `${focusPointsFC.features.length} Punkt(e) fokussiert, ${familyPointsFC.features.length} Punkt(e) Familie, ${focusFC.features.length + familyFC.features.length} Linie(n).`
  );

  if (allCoords.length > 0) {
    const lons = allCoords.map((c) => c[0]);
    const lats = allCoords.map((c) => c[1]);
    const bounds = [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]];
    if (bounds.every((pair) => pair.every(Number.isFinite))) {
      map.fitBounds(bounds, { padding: 60, maxZoom: 10, duration: 600 });
    } else {
      setDiagnostics(`Ungültige Kartengrenzen, fitBounds übersprungen: ${JSON.stringify(bounds)}`);
    }
  } else {
    setDiagnostics("Keine Koordinaten zum Anzeigen gefunden (allCoords ist leer).");
  }
}

function osmRasterStyle() {
  return {
    version: 8,
    sources: {
      osm: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        attribution: "© OpenStreetMap contributors",
      },
    },
    layers: [{ id: "osm-layer", type: "raster", source: "osm" }],
  };
}

function emptyFC() {
  return { type: "FeatureCollection", features: [] };
}

function lineLayer(id, source, color, width) {
  return { id, type: "line", source, paint: { "line-color": color, "line-width": width } };
}

function pointLayer(id, source, color, radius) {
  return { id, type: "circle", source, paint: { "circle-color": color, "circle-radius": radius } };
}
