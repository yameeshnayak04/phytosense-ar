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

export function closeSheet() {
  $("#sheet").hidden = true;
  $("#sheet-backdrop").hidden = true;
  speechSynthesis?.cancel?.();
}

const list = (items) => (items?.length ? `<ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "<p class='muted'>None needed.</p>");

const SEVERITY_COLOR = { none: "var(--good)", early: "var(--good)", moderate: "var(--warn)", severe: "var(--bad)" };

export function showResult(r, imageSrc) {
  state.lastResult = r;
  const info = r.info || {};
  const cropInfo = r.crop_info || {};
  const wiki = cropInfo.wikipedia || {};
  const title = r.status === "healthy" ? "Healthy leaf" : r.disease;

  let alert = "";
  if (r.status === "no_leaf") {
    alert = `<div class="alert warn">No clear leaf was found. Place one leaf in the centre, fill the frame and use even light. The guess below may be wrong.</div>`;
  } else if (r.status === "uncertain") {
    alert = `<div class="alert warn">The model is only ${pct(r.confidence)} sure. Retake the photo closer, in daylight, or compare with the alternatives below.</div>`;
  } else if (r.urgency === "high" && !r.healthy) {
    alert = `<div class="alert bad">High-risk disease: it can spread fast. Isolate or remove affected plants and act today.</div>`;
  }

  $("#sheet-body").innerHTML = `
    <div class="result-img">
      <canvas id="result-canvas" aria-label="Leaf with AR overlay"></canvas>
      <button class="btn ghost toggle chip" id="toggle-overlay">Hide overlay</button>
    </div>

    <div class="result-head">
      <div class="ring" style="--v:${r.health_score};--c:${healthColor(r.health_score)}">
        <div><b>${r.health_score}</b><small>health</small></div>
      </div>
      <div>
        <span class="badge ${r.status}">${STATUS_TEXT[r.status] || r.status}</span>
        <h2 id="sheet-title">${esc(title)}</h2>
        <div class="crop">${esc(r.crop)}${cropInfo.hi ? ` · ${esc(cropInfo.hi)}` : ""}${cropInfo.scientific ? ` · <i>${esc(cropInfo.scientific)}</i>` : ""}</div>
      </div>
    </div>
    ${alert}

    <div class="kv">
      <div><span>Confidence</span><b>${pct(r.confidence)}</b></div>
      <div><span>Infected area</span><b>${r.healthy ? "–" : `${r.severity}%`}</b></div>
      <div><span>Severity</span><b style="color:${SEVERITY_COLOR[r.severity_level] || "inherit"}">${esc(r.severity_level)}</b></div>
    </div>
    ${r.healthy ? "" : `<div class="meter" title="Infected leaf area"><i style="width:${Math.min(100, r.severity)}%;--c:${SEVERITY_COLOR[r.severity_level]}"></i></div>`}

    <details class="block" open>
      <summary>Top predictions</summary>
      <div class="top3">${r.top3.map((p) => `
        <div><span>${esc(p.crop)} – ${esc(p.disease)}</span><b>${pct(p.confidence)}</b>
        <div class="meter"><i style="width:${p.confidence * 100}%"></i></div></div>`).join("")}
      </div>
    </details>

    ${info.symptoms ? `
    <details class="block" ${r.healthy ? "" : "open"}>
      <summary>Symptoms &amp; cause</summary>
      <div><p>${esc(info.symptoms)}</p>${info.pathogen ? `<p class="muted small">${esc(info.type)} · <i>${esc(info.pathogen)}</i></p>` : ""}</div>
    </details>
    <details class="block" ${r.healthy ? "" : "open"}>
      <summary>Treatment</summary>
      <div>
        ${info.chemical?.length ? `<b>Chemical</b>${list(info.chemical)}` : ""}
        <b>Organic / low-cost</b>${list(info.organic)}
        <p class="muted small">${esc(r.note || "")}</p>
      </div>
    </details>
    <details class="block" ${r.healthy ? "open" : ""}>
      <summary>Prevention</summary>
      <div>${list(info.prevention)}</div>
    </details>` : ""}

    ${wiki.extract ? `
    <details class="block">
      <summary>About ${esc(r.crop)}</summary>
      <div class="wiki">
        ${wiki.thumbnail ? `<img src="${esc(wiki.thumbnail)}" alt="">` : ""}
        <div><p class="small">${esc(wiki.extract)}</p>${wiki.url ? `<a href="${esc(wiki.url)}" target="_blank" rel="noopener">Wikipedia ↗</a>` : ""}</div>
      </div>
    </details>` : ""}

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
  const text = r.healthy
    ? `This ${r.crop} leaf looks healthy. ${(info.prevention || []).slice(0, 2).join(". ")}.`
    : `${r.crop}: ${r.disease}. ${Math.round(r.confidence * 100)} percent confidence. About ${r.severity} percent of the leaf is affected. ` +
      `Organic treatment: ${(info.organic || []).join(". ")}.`;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-IN";
  speechSynthesis.speak(u);
}
