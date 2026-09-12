const overlay = document.createElement("div");
overlay.className = "lightbox-overlay";
overlay.hidden = true;
overlay.innerHTML = `
  <div class="lightbox-box">
    <button class="lightbox-close" aria-label="Schließen">&times;</button>
    <div class="lightbox-content"></div>
  </div>
`;
document.body.appendChild(overlay);

const contentEl = overlay.querySelector(".lightbox-content");

function close() {
  overlay.hidden = true;
}

overlay.querySelector(".lightbox-close").addEventListener("click", close);
overlay.addEventListener("click", (e) => {
  if (e.target === overlay) close();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") close();
});

export function openLightbox(html) {
  contentEl.innerHTML = html;
  overlay.hidden = false;
}
