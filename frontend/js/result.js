// Bottom sheet that shows one diagnosis: annotated image, scores, treatment, crop info.
import { $, STATUS_TEXT, esc, healthColor, pct, state } from "./util.js";
import { renderAnnotated } from "./overlay.js";

let onAsk = () => {};

export function initResult({ onAskAssistant }) {
  onAsk = onAskAssistant;
  $("#sheet-close").addEventListener("click", closeSheet);
  $("#sheet-backdrop").addEventListener("click", closeSheet);
  document.addEventListener("keydown", (e) => e.key === "Escape" && closeSheet());
}

function closeSheet() {
  $("#sheet").hidden = true;
  $("#sheet-backdrop").hidden = true;
  speechSynthesis?.cancel?.();
}

const list = (items) => (items?.length ? `<ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "<p class='muted'>None needed.</p>");

const SEVERITY_COLOR = { none: "var(--good)", early: "var(--good)", moderate: "var(--warn)", severe: "var(--bad)" };
const URGENCY = {
  high: { text: "High", hint: "Act today – spreads fast", color: "var(--bad)" },
  medium: { text: "Medium", hint: "Treat within a few days", color: "var(--warn)" },
  low: { text: "Low", hint: "Not urgent – fix the cause", color: "var(--good)" },
  none: { text: "None", hint: "Nothing to treat", color: "var(--good)" },
};

// Plain-language meaning of the cause type stored in the knowledge base.
function typeMeaning(type = "") {
  const t = type.toLowerCase();
  if (t.includes("deficien")) return "Could be a virus or a lack of nutrients (iron, zinc, magnesium) – both turn leaves yellow and patchy.";
  if (t.includes("virus")) return "Caused by a virus. Insects such as whiteflies and aphids carry it from plant to plant; infected plants cannot be cured, only the spread can be stopped.";
  if (t.includes("oomycete")) return "Caused by a water mould (oomycete) – a fungus-like organism that spreads very fast in cool, wet weather.";
  if (t.includes("fungus or bacterium")) return "Caused by a fungus or bacteria. Both spread through water splashes, wet leaves and infected plant debris.";
  if (t.includes("secondary")) return "A fungus that grows on the sticky honeydew left by sap-sucking insects – the insects are the real problem.";
  if (t.includes("fung")) return "Caused by a fungus. It spreads through tiny spores carried by wind, water and wet leaves.";
  if (t.includes("bacter")) return "Caused by bacteria. They enter through wounds and leaf pores and spread with rain, irrigation water and tools.";
  if (t.includes("insect") || t.includes("mite") || t.includes("pest")) return "Caused by small insects or mites that suck sap from the leaves or feed inside them.";
  return "";
}

const cap = (s) => esc(String(s).charAt(0).toUpperCase() + String(s).slice(1));
const healthWord = (score) => (score >= 80 ? "good" : score >= 50 ? "fair" : "poor");

// One short paragraph that says what the result means, in everyday words.
function summary(r, plant, measured) {
  if (r.status === "no_plant") return "No plant was found in this photo. Point the camera at a plant or a leaf and try again.";
  const out = [];
  if (r.species) {
    out.push(`This looks like <b>${esc(r.crop)}</b>${r.species.hindi ? ` (${esc(r.species.hindi)})` : ""}` +
      `${plant?.category ? `, a ${esc(plant.category.toLowerCase())}` : ""} – the AI is ${pct(r.species.confidence)} sure.`);
  } else if (r.species_top?.length) {
    out.push(`The plant could not be identified with confidence (closest match: ${esc(r.species_top[0].name)}, ${pct(r.species_top[0].confidence)}).`);
  } else if (r.crop && r.crop !== "Unknown") {
    out.push(`This is a <b>${esc(r.crop)}</b> leaf.`);
  }
  if (r.status === "no_leaf") {
    out.push("To check its health, move closer so that one leaf fills most of the frame.");
  } else if (r.status === "uncertain") {
    out.push(`The health result is uncertain – the best guess is <b>${esc(r.disease)}</b>, but the AI is only ${pct(r.confidence)} sure. ` +
      "Retake the photo closer and in daylight, or compare with the other possibilities below.");
  } else if (r.healthy) {
    out.push("The leaves look <b>healthy</b> – no signs of disease or pests were found.");
  } else {
    const what = typeMeaning(r.info?.type).split(".")[0];
    out.push(`It shows signs of <b>${esc(r.disease)}</b>${what ? ` (${esc(what.charAt(0).toLowerCase() + what.slice(1))})` : ""}.`);
    if (measured) out.push(`About <b>${r.severity}%</b> of the leaf surface is affected, which is <b>${esc(r.severity_level)}</b>.`);
    const u = URGENCY[r.urgency];
    if (u && r.urgency !== "none") out.push(`${u.hint}.`);
  }
  if (r.status !== "no_leaf") out.push(`Overall health score: <b>${r.health_score}/100</b> (${healthWord(r.health_score)}).`);
  return out.join(" ");
}

const tile = (label, value, hint, color) =>
  `<div><span>${label}</span><b${color ? ` style="color:${color}"` : ""}>${value}</b><small>${hint}</small></div>`;

const GLOSSARY = [
  ["Health score (0–100)", "Overall condition of the leaf. 100 = healthy. It goes down with how dangerous the problem is and how much of the leaf is affected. 80+ good · 50–79 fair · below 50 poor."],
  ["Confidence", "How sure the AI is about its answer (the plant name and the health result each have their own), from 0 to 100%. Above 55% the result is shown normally; below that the app says “Not sure – retake”. It is a probability, not a guarantee."],
  ["Infected area", "The share of the leaf surface covered by spots, patches or discolouration, measured from the colours in the photo. Not measured for plants whose leaves are naturally colourful (croton, coleus, variegated money plant)."],
  ["Severity", "Stage of the problem, from the infected area: Early (below 5%), Moderate (5–20%), Severe (above 20%). Early problems are the easiest to control."],
  ["Urgency", "How quickly the problem can spread or damage the plant. High = act today, Medium = within a few days, Low = not urgent."],
  ["Plant identification", "Which of the 68 known plants this is. The bars show the AI's probability for the closest matches; below 35% the plant is shown as “Unknown plant”."],
  ["Crop disease model", "A specialised AI for 14 crops (tomato, potato, maize, grape, citrus, …) that names the exact disease, out of 38."],
  ["Leaf-condition model", "A general AI used for all other plants. It recognises 7 groups – healthy, leaf spot / blight, powdery mildew, rust, sooty mould, mosaic / yellowing and pests – not the exact disease name."],
  ["Overlay on the photo", "Dashed outline = the leaf the AI looked at. Red patches = spots it measured as infected. Switch it off with “Hide overlay”."],
  ["Chemical vs organic", "Chemical sprays act faster but must be used exactly as on the label, with gloves and a mask. Organic options are cheaper and safer but need repeating every 5–7 days."],
];

export function showResult(r, imageSrc) {
  state.lastResult = r;
  const info = r.info || {};
  const cropInfo = r.crop_info || {};
  const wiki = cropInfo.wikipedia || {};
  const plant = r.plant_info;
  const title = r.status === "no_plant" ? "No plant found" : r.status === "healthy" ? "Healthy" : r.disease;
  const measured = !r.healthy && r.severity_reliable !== false && r.status !== "no_leaf";
  const urgency = URGENCY[r.healthy ? "none" : r.urgency] || { text: "–", hint: "Unknown", color: "" };
  const condition = r.source === "condition_model";

  const alert = r.urgency === "high" && !r.healthy && r.status === "diseased"
    ? `<div class="alert bad">High-risk problem: it can spread fast to nearby plants. Isolate or remove the affected leaves and act today.</div>` : "";

  $("#sheet-body").innerHTML = `
    <div class="result-img">
      <canvas id="result-canvas" aria-label="Leaf with AR overlay"></canvas>
      <button class="btn ghost toggle chip" id="toggle-overlay">Hide overlay</button>
    </div>

    <div class="result-head">
      <div class="ring" style="--v:${r.health_score};--c:${healthColor(r.health_score)}" title="Health score – 100 means healthy">
        <div><b>${r.status === "no_plant" ? "–" : r.health_score}</b><small>health</small></div>
      </div>
      <div>
        <span class="badge ${r.status}">${STATUS_TEXT[r.status] || r.status}</span>
        <h2 id="sheet-title">${esc(title)}</h2>
        <div class="crop">${esc(r.crop)}${cropInfo.hi ? ` · ${esc(cropInfo.hi)}` : ""}${cropInfo.scientific ? ` · <i>${esc(cropInfo.scientific)}</i>` : ""}</div>
      </div>
    </div>

    <div class="summary"><b class="summary-title">What this means</b><p>${summary(r, plant, measured)}</p></div>
    ${alert}
    ${plant?.toxic ? `<div class="alert warn">⚠️ Safety: ${esc(plant.toxic)}.</div>` : ""}

    ${r.status === "no_plant" ? "" : `
    <div class="kv kv-explained">
      ${tile("Health confidence", pct(r.confidence), "How sure the AI is about the health result")}
      ${tile("Infected area", measured ? `${r.severity}%` : "–",
        r.healthy ? "No spots found" : plant?.variegated ? "Not measured – leaves are naturally coloured"
          : measured ? "Part of the leaf covered by spots" : "Needs a close-up of one leaf")}
      ${tile("Severity", cap(measured || r.healthy ? r.severity_level : "n/a"), "Early &lt;5% · Moderate 5–20% · Severe &gt;20%", SEVERITY_COLOR[r.severity_level])}
      ${tile("Urgency", urgency.text, urgency.hint, urgency.color)}
    </div>
    ${measured ? `<div class="meter" title="Infected leaf area"><i style="width:${Math.min(100, r.severity)}%;--c:${SEVERITY_COLOR[r.severity_level]}"></i></div>` : ""}`}

    ${r.species_top?.length ? `
    <details class="block" open>
      <summary>Which plant is this?</summary>
      <div>
        <p class="muted small">The AI compared the photo with the 68 plants it knows. Each bar shows how likely that plant is.</p>
        <div class="top3">${r.species_top.map((p) => `
          <div><span>${esc(p.name)}${p.hindi ? ` · ${esc(p.hindi)}` : ""} <i class="muted">${esc(p.scientific)}</i></span><b>${pct(p.confidence)}</b>
          <div class="meter"><i style="width:${p.confidence * 100}%"></i></div></div>`).join("")}
        </div>
      </div>
    </details>` : ""}

    ${info.symptoms ? `
    <details class="block" ${r.healthy ? "" : "open"}>
      <summary>${r.healthy ? "What a healthy leaf looks like" : `What is ${esc(r.disease.split(" (")[0])}?`}</summary>
      <div>
        ${!r.healthy && typeMeaning(info.type) ? `<p>${esc(typeMeaning(info.type))}</p>` : ""}
        <p><b>Signs to look for:</b> ${esc(info.symptoms)}</p>
        ${info.pathogen ? `<p class="muted small">Cause: ${esc(info.type)} · <i>${esc(info.pathogen)}</i></p>` : ""}
      </div>
    </details>
    ${r.healthy ? "" : `
    <details class="block" open>
      <summary>How to treat it</summary>
      <div>
        <b>Organic / low-cost (try first)</b>${list(info.organic)}
        ${info.chemical?.length ? `<b>Chemical (if it keeps spreading)</b>${list(info.chemical)}` : ""}
        <p class="muted small">${esc(r.note || "")}</p>
      </div>
    </details>`}
    <details class="block" ${r.healthy ? "open" : ""}>
      <summary>How to prevent it</summary>
      <div>${list(info.prevention)}</div>
    </details>` : ""}

    ${r.top3?.length ? `
    <details class="block">
      <summary>Other possibilities</summary>
      <div>
        <p class="muted small">Checked by the ${condition ? "leaf-condition model (works on any plant and reports general problem groups)"
          : "crop disease model (names the exact disease of this crop)"}. If the top result does not match what you see on the leaf, compare with these.</p>
        <div class="top3">${r.top3.map((p) => `
          <div><span>${esc(p.disease)}</span><b>${pct(p.confidence)}</b>
          <div class="meter"><i style="width:${p.confidence * 100}%"></i></div></div>`).join("")}
        </div>
      </div>
    </details>` : ""}

    ${plant ? `
    <details class="block">
      <summary>Caring for ${esc(plant.name.split(" (")[0])}</summary>
      <div>
        <p class="muted small">${esc(plant.category)}${plant.uses ? ` · ${esc(plant.uses)}` : ""}</p>
        ${Object.entries({ Light: plant.care?.sun, Water: plant.care?.water, Soil: plant.care?.soil })
          .filter(([, v]) => v && v !== "-").map(([k, v]) => `<p><b>${k}:</b> ${esc(v)}</p>`).join("")}
        <b>Common problems</b>${list(plant.problems)}
      </div>
    </details>` : ""}

    ${wiki.extract ? `
    <details class="block">
      <summary>About ${esc(r.crop)}</summary>
      <div class="wiki">
        ${wiki.thumbnail ? `<img src="${esc(wiki.thumbnail)}" alt="">` : ""}
        <div><p class="small">${esc(wiki.extract)}</p>${wiki.url ? `<a href="${esc(wiki.url)}" target="_blank" rel="noopener">Wikipedia ↗</a>` : ""}</div>
      </div>
    </details>` : ""}

    <details class="block glossary">
      <summary>What do these terms mean?</summary>
      <div><dl>${GLOSSARY.map(([t, d]) => `<dt>${t}</dt><dd>${d}</dd>`).join("")}</dl></div>
    </details>

    <div class="sheet-actions">
      <button class="btn primary" id="btn-ask">Ask the assistant</button>
      <button class="btn" id="btn-speak">🔊 Read aloud</button>
    </div>
    <p class="muted small center">${r.scan_id ? `Saved as scan #${r.scan_id}` : ""} ${r.elapsed_ms ? `· analysed in ${r.elapsed_ms} ms` : ""}</p>
  `;

  const canvas = $("#result-canvas");
  const img = new Image();
  let overlayOn = true;
  img.onload = () => renderAnnotated(canvas, img, r, overlayOn);
  img.src = imageSrc;
  $("#toggle-overlay").addEventListener("click", (e) => {
    overlayOn = !overlayOn;
    e.target.textContent = overlayOn ? "Hide overlay" : "Show overlay";
    renderAnnotated(canvas, img, r, overlayOn);
  });
  $("#btn-ask").addEventListener("click", () => { closeSheet(); onAsk(r); });
  $("#btn-speak").addEventListener("click", () => speak(r));

  $("#sheet").hidden = false;
  $("#sheet-backdrop").hidden = false;
  $("#sheet").scrollTop = 0;
}

function speak(r) {
  if (!("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const info = r.info || {};
  const text = r.status === "no_plant" ? "No plant was detected. Point the camera at a plant or a leaf."
    : r.healthy
    ? `This ${r.crop} leaf looks healthy. ${(info.prevention || []).slice(0, 2).join(". ")}.`
    : `${r.crop}: ${r.disease}. ${Math.round(r.confidence * 100)} percent confidence. ` +
      (r.severity_reliable === false ? "" : `About ${r.severity} percent of the leaf is affected. `) +
      `Organic treatment: ${(info.organic || []).join(". ")}.`;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-IN";
  speechSynthesis.speak(u);
}
