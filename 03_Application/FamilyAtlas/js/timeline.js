import { screenshotsForEvent } from "./sources.js";

const PX_PER_YEAR = 7.56; // 5 Jahre = 1cm bei 96dpi Referenzpixeln
const MIN_LABEL_GAP = 34; // px, Mindestabstand zwischen Label-Mitten
const RULER_X = 26; // px, Position der Zeitachse
const TOP_PADDING = 20;
const TICK_STEP_YEARS = 10;

export function renderTimeline(container, data, sourcesData, focusedId, onOpenEvent) {
  const focused = data.peopleById.get(focusedId);

  const personalEntries = (focused.events || []).map((e) => ({
    trueYear: fractionalYear(e),
    dateDisplay: e.date_display,
    label: e.label,
    tag: "Person",
    regional: false,
    eventId: e.id,
    isBirth: e.type === "birth",
    hasSource: e.id ? screenshotsForEvent(sourcesData, e.id).length > 0 : false,
  }));

  const regionalEntries = (data.regional_events || []).map((e) => ({
    trueYear: e.year,
    dateDisplay: null,
    label: e.label,
    tag: "Regionalgeschichte",
    regional: true,
    hasSource: false,
  }));

  const entries = [...personalEntries, ...regionalEntries].sort((a, b) => a.trueYear - b.trueYear);

  const { minYear, maxYear } = globalYearRange(data);
  const chartHeight = Math.max(120, (maxYear - minYear) * PX_PER_YEAR + TOP_PADDING * 2);
  const positioned = layoutLabels(entries, minYear);

  container.innerHTML = `
    <h2>Zeitleiste</h2>
    <div class="timeline-chart" style="height:${chartHeight}px">
      <svg class="timeline-axis" width="100%" height="${chartHeight}">
        <line x1="${RULER_X}" y1="0" x2="${RULER_X}" y2="${chartHeight}" class="axis-line" />
        ${tickMarksSvg(minYear, maxYear)}
        ${positioned.map((p) => connectorSvg(p)).join("")}
      </svg>
      ${positioned.map(labelHtml).join("")}
    </div>
  `;

  container.querySelectorAll(".timeline-entry[data-event-id]").forEach((el) => {
    el.addEventListener("click", () => onOpenEvent(el.dataset.eventId, el.dataset.eventLabel));
  });

  scrollBirthToTop(container);
}

function scrollBirthToTop(container) {
  // Auf den nächsten Frame warten, damit Layout/Styles sicher angewendet sind,
  // bevor wir Positionen messen (sonst können wir beim ersten Render falsch messen).
  requestAnimationFrame(() => {
    const panelEl = container.closest(".panel");
    const birthEl = container.querySelector(".timeline-entry.is-birth");
    if (!panelEl || !birthEl) return;

    const targetTop =
      panelEl.scrollTop + (birthEl.getBoundingClientRect().top - panelEl.getBoundingClientRect().top) - 16;
    smoothScrollTo(panelEl, Math.max(0, targetTop));
  });
}

function smoothScrollTo(el, targetTop, duration = 700) {
  const startTop = el.scrollTop;
  const delta = targetTop - startTop;
  if (Math.abs(delta) < 1) return;
  const startTime = performance.now();

  function step(now) {
    const t = Math.min(1, (now - startTime) / duration);
    const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    el.scrollTop = startTop + delta * eased;
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function fractionalYear(e) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(e.date_display || "");
  if (!m) return e.year;
  const daysBeforeMonth = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  const dayOfYear = daysBeforeMonth[Number(m[2]) - 1] + Number(m[3]);
  return Number(m[1]) + dayOfYear / 365;
}

function globalYearRange(data) {
  const years = [];
  for (const p of data.people) {
    for (const e of p.events || []) years.push(e.year);
  }
  for (const e of data.regional_events || []) years.push(e.year);
  return { minYear: Math.min(...years), maxYear: Math.max(...years) };
}

function layoutLabels(entries, minYear) {
  let lastDisplayY = -Infinity;
  return entries
    .map((e) => ({ ...e, trueY: (e.trueYear - minYear) * PX_PER_YEAR + TOP_PADDING }))
    .map((e) => {
      const displayY = Math.max(e.trueY, lastDisplayY + MIN_LABEL_GAP);
      lastDisplayY = displayY;
      return { ...e, displayY };
    });
}

function tickMarksSvg(minYear, maxYear) {
  const startTick = Math.ceil(minYear / TICK_STEP_YEARS) * TICK_STEP_YEARS;
  const marks = [];
  for (let y = startTick; y <= maxYear; y += TICK_STEP_YEARS) {
    const ty = (y - minYear) * PX_PER_YEAR + TOP_PADDING;
    marks.push(`
      <line x1="${RULER_X - 4}" y1="${ty}" x2="${RULER_X + 4}" y2="${ty}" class="axis-tick" />
      <text x="${RULER_X - 8}" y="${ty + 3}" class="axis-tick-label" text-anchor="end">${y}</text>
    `);
  }
  return marks.join("");
}

function connectorSvg(entry) {
  const cssClass = entry.hasSource ? " has-source" : entry.regional ? " is-regional" : "";
  return `<line x1="${RULER_X}" y1="${entry.trueY}" x2="${RULER_X + 16}" y2="${entry.displayY}" class="axis-connector${cssClass}" />`;
}

function labelHtml(entry) {
  const clickable = entry.hasSource ? ` data-event-id="${entry.eventId}" data-event-label="${entry.label}"` : "";
  const classes = [
    "timeline-entry",
    entry.regional && "is-regional",
    entry.hasSource && "has-source",
    entry.isBirth && "is-birth",
  ].filter(Boolean).join(" ");
  return `
    <div class="${classes}"
         style="top:${entry.displayY - 9}px; left:${RULER_X + 20}px"${clickable}>
      <span class="timeline-year">${entry.dateDisplay || Math.round(entry.trueYear)}</span>
      <span class="timeline-label">${entry.label}</span>
    </div>
  `;
}
