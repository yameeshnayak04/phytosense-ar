// Disease library: searchable list of every class the model knows.
import { $, api, esc } from "./util.js";

let entries = [];
let crop = "All";

export async function loadLibrary() {
  if (!entries.length) {
    try {
      entries = (await api("/api/diseases")).entries;
    } catch (e) {
      $("#lib-list").innerHTML = `<p class="empty">Could not load library: ${esc(e.message)}</p>`;
      return;
    }
    $("#lib-search").addEventListener("input", render);
    const crops = ["All", ...new Set(entries.map((e) => e.crop).sort())];
    $("#lib-crops").innerHTML = crops.map((c) => `<button class="chip${c === crop ? " active" : ""}" data-crop="${esc(c)}">${esc(c)}</button>`).join("");
    $("#lib-crops").querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => {
      crop = b.dataset.crop;
      $("#lib-crops").querySelectorAll(".chip").forEach((x) => x.classList.toggle("active", x === b));
      render();
    }));
  }
  render();
}

const ul = (items) => (items.length ? `<ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "");

function render() {
  const q = $("#lib-search").value.trim().toLowerCase();
  const shown = entries
    .filter((e) => crop === "All" || e.crop === crop)
    .filter((e) => !q || `${e.crop} ${e.disease} ${e.pathogen} ${e.symptoms}`.toLowerCase().includes(q))
    .sort((a, b) => a.crop.localeCompare(b.crop) || Number(a.healthy) - Number(b.healthy) || a.disease.localeCompare(b.disease));
  $("#lib-list").innerHTML = shown.length ? shown.map((e) => `
    <details class="block">
      <summary><span><b>${esc(e.crop)}</b> – ${esc(e.disease)}</span></summary>
      <div>
        ${e.healthy ? "" : `<p class="muted small">${esc(e.type)} · <i>${esc(e.pathogen)}</i> · urgency: ${esc(e.urgency)}</p>`}
        <p>${esc(e.symptoms)}</p>
        ${e.chemical.length ? `<b>Chemical</b>${ul(e.chemical)}` : ""}
        <b>Organic</b>${ul(e.organic)}
        <b>Prevention</b>${ul(e.prevention)}
      </div>
    </details>`).join("") : `<p class="empty">No match.</p>`;
}
