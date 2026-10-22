// Library: plants the app identifies, crop diseases and general leaf conditions, searchable.
import { $, api, esc } from "./util.js";

const MODES = { plants: "Plants", diseases: "Crop diseases", conditions: "Leaf conditions" };
let mode = "plants";
let filter = "All";
let data = null;

export async function loadLibrary() {
  if (!data) {
    try {
      const [d, p] = await Promise.all([api("/api/diseases"), api("/api/plants")]);
      data = { diseases: d.entries, plants: p.plants, conditions: p.conditions };
    } catch (e) {
      $("#lib-list").innerHTML = `<p class="empty">Could not load library: ${esc(e.message)}</p>`;
      return;
    }
    $("#lib-search").addEventListener("input", render);
    $("#lib-modes").innerHTML = Object.entries(MODES)
      .map(([k, v]) => `<button class="chip${k === mode ? " active" : ""}" data-mode="${k}">${v}</button>`).join("");
    $("#lib-modes").querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => {
      mode = b.dataset.mode;
      filter = "All";
      $("#lib-modes").querySelectorAll(".chip").forEach((x) => x.classList.toggle("active", x === b));
      renderFilters();
      render();
    }));
  }
  renderFilters();
  render();
}

function renderFilters() {
  const groups = mode === "plants" ? data.plants.map((p) => p.category)
    : mode === "diseases" ? data.diseases.map((e) => e.crop) : [];
  const values = groups.length ? ["All", ...new Set(groups.sort())] : [];
  $("#lib-crops").innerHTML = values.map((c) => `<button class="chip${c === filter ? " active" : ""}" data-f="${esc(c)}">${esc(c)}</button>`).join("");
  $("#lib-crops").querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => {
    filter = b.dataset.f;
    $("#lib-crops").querySelectorAll(".chip").forEach((x) => x.classList.toggle("active", x === b));
    render();
  }));
}

const ul = (items) => (items?.length ? `<ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "");

function diseaseBlock(e, head) {
  return `
    <details class="block">
      <summary><span>${head}</span></summary>
      <div>
        ${e.healthy ? "" : `<p class="muted small">${esc(e.type)} · <i>${esc(e.pathogen)}</i> · urgency: ${esc(e.urgency)}</p>`}
        <p>${esc(e.symptoms)}</p>
        ${e.chemical.length ? `<b>Chemical</b>${ul(e.chemical)}` : ""}
        <b>Organic</b>${ul(e.organic)}
        <b>Prevention</b>${ul(e.prevention)}
      </div>
    </details>`;
}

function plantBlock(p) {
  const care = Object.entries({ Light: p.care?.sun, Water: p.care?.water, Soil: p.care?.soil }).filter(([, v]) => v && v !== "-");
  return `
    <details class="block">
      <summary><span><b>${esc(p.name)}</b>${p.hindi ? ` · ${esc(p.hindi)}` : ""}</span></summary>
      <div>
        <p class="muted small"><i>${esc(p.scientific)}</i> · ${esc(p.category)}</p>
        ${p.toxic ? `<div class="alert warn">⚠️ ${esc(p.toxic)}.</div>` : ""}
        <p>${esc(p.uses)}</p>
        ${care.map(([k, v]) => `<p><b>${k}:</b> ${esc(v)}</p>`).join("")}
        <b>Common problems</b>${ul(p.problems)}
      </div>
    </details>`;
}

function render() {
  const q = $("#lib-search").value.trim().toLowerCase();
  const has = (text) => !q || text.toLowerCase().includes(q);
  let html = "";
  if (mode === "plants") {
    html = data.plants
      .filter((p) => filter === "All" || p.category === filter)
      .filter((p) => has(`${p.name} ${p.hindi} ${p.scientific} ${p.category} ${p.problems.join(" ")}`))
      .sort((a, b) => a.name.localeCompare(b.name)).map(plantBlock).join("");
  } else if (mode === "diseases") {
    html = data.diseases
      .filter((e) => filter === "All" || e.crop === filter)
      .filter((e) => has(`${e.crop} ${e.disease} ${e.pathogen} ${e.symptoms}`))
      .sort((a, b) => a.crop.localeCompare(b.crop) || Number(a.healthy) - Number(b.healthy) || a.disease.localeCompare(b.disease))
      .map((e) => diseaseBlock(e, `<b>${esc(e.crop)}</b> – ${esc(e.disease)}`)).join("");
  } else {
    html = `<p class="muted small">Recognised on any plant – used for plants without a crop-specific disease model.</p>` +
      data.conditions.filter((c) => has(`${c.disease} ${c.pathogen} ${c.symptoms}`))
        .map((c) => diseaseBlock(c, `<b>${esc(c.disease)}</b>`)).join("");
  }
  $("#lib-list").innerHTML = html || `<p class="empty">No match.</p>`;
}
