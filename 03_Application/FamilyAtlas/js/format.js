export function lifespan(person) {
  const birth = person.birth_year ?? "?";
  if (person.living) return `*${birth}`;
  const death = person.death_year ?? "?";
  return `${birth}–${death}`;
}
