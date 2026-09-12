export async function loadData() {
  const res = await fetch("data/people.json");
  const raw = await res.json();

  const placesById = new Map(raw.places.map((p) => [p.id, p]));
  const peopleById = new Map(raw.people.map((p) => [p.id, p]));

  return { ...raw, placesById, peopleById };
}

export function personPathCoords(person, data) {
  return person.path
    .map((placeId) => data.placesById.get(placeId))
    .filter(Boolean)
    .map((place) => [place.lon, place.lat]);
}
