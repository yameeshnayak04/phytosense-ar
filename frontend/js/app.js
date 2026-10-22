// App shell: tab navigation, server status, language, upload + samples.
import { $, api, busy, esc, localStorageSet, postImage, state, toast } from "./util.js";
import { initAR, stopCamera } from "./ar.js";
import { initResult, showResult } from "./result.js";
import { loadHistory } from "./history.js";
import { initChat, setContext } from "./chat.js";
import { loadLibrary } from "./library.js";

function showView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  document.querySelectorAll(".tabbar button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  if (name !== "scan") stopCamera();
  if (name === "history") loadHistory();
  if (name === "library") loadLibrary();
  if (name === "chat") setContext(state.lastResult);
  window.scrollTo({ top: 0 });
}

async function pollStatus() {
  const line = $("#status-line");
  try {
    const s = await api("/api/status");
    state.status = s;
    line.textContent = s.model_ready
      ? `AI ready · ${s.species ? `${s.species} plants · ` : ""}${s.classes} crop diseases · assistant: ${s.assistant}`
      : "Loading AI models…";
    const sel = $("#lang-select");
    if (!sel.options.length) {
      sel.innerHTML = Object.entries(s.languages).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
      sel.value = state.lang;
    }
    if (!s.model_ready) setTimeout(pollStatus, 2000);
  } catch {
    line.textContent = "Server offline – start the backend";
    setTimeout(pollStatus, 3000);
  }
}

async function diagnoseFile(file) {
  if (!file || !file.type.startsWith("image/")) {
    toast("Please choose an image file");
    return;
  }
  busy(true);
  try {
    const result = await postImage("/api/diagnose", file);
    showResult(result, URL.createObjectURL(file));
  } catch (e) {
    toast(`Diagnosis failed: ${e.message}`);
  } finally {
    busy(false);
  }
}

function initUpload() {
  const input = $("#file-input");
  const zone = $("#dropzone");
  input.addEventListener("change", () => diagnoseFile(input.files[0]).finally(() => (input.value = "")));
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("drag"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag");
    diagnoseFile(e.dataTransfer.files[0]);
  });
}

const SAMPLE_GROUPS = { plants: "Common plants of Indore", problems: "Plant problems" };

// "(c) Name, some rights reserved (CC BY)" -> "Name"
const photographer = (credit) => credit.replace(/^\(c\)\s*/, "").replace(/,\s*(some|no) rights reserved.*$/i, "").trim();

async function initSamples() {
  let samples = [];
  try { samples = await api("samples/samples.json"); } catch { return; }
  const box = $("#samples");
  box.innerHTML = Object.entries(SAMPLE_GROUPS).map(([group, title]) => `
    <h4 class="sample-group">${title}</h4>
    <div class="samples">${samples.filter((s) => s.group === group).map((s) => {
      const who = photographer(s.credit || "");
      return `
      <div class="sample">
        <button data-src="samples/${esc(s.file)}" title="Analyse: ${esc(s.label)}">
          <img src="samples/${esc(s.file)}" alt="${esc(s.label)}" loading="lazy"><span>${esc(s.label)}</span>
        </button>
        <a class="credit" href="${esc(s.source)}" target="_blank" rel="noopener">© ${esc(who && !/rights/i.test(who) ? who : "iNaturalist")} · ${esc(s.license)}</a>
      </div>`;
    }).join("")}</div>`).join("");
  box.querySelectorAll(".sample button").forEach((b) => b.addEventListener("click", async () => {
    const blob = await (await fetch(b.dataset.src)).blob();
    diagnoseFile(new File([blob], "sample.jpg", { type: blob.type || "image/jpeg" }));
  }));
}

function init() {
  document.querySelectorAll(".tabbar button").forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));
  $("#lang-select").addEventListener("change", (e) => {
    state.lang = e.target.value;
    localStorageSet("phyto.lang", state.lang);
  });
  initResult({
    onAskAssistant: (r) => { setContext(r); showView("chat"); },
  });
  initAR({ onResult: (r, src) => showResult(r, src) });
  initUpload();
  initSamples();
  initChat();
  pollStatus();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
}

init();
