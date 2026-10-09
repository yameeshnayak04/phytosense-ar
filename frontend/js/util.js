// Shared helpers: DOM, API calls, toast/busy, tiny markdown renderer, app state.

export const $ = (sel, root = document) => root.querySelector(sel);

export const state = {
  lang: localStorageGet("phyto.lang") || "en",
  lastResult: null,      // last full diagnosis (used as assistant context)
  status: null,          // /api/status payload
};

export function localStorageGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}
export function localStorageSet(key, value) {
  try { localStorage.setItem(key, value); } catch { /* private mode */ }
}

export async function api(path, options = {}) {
  const res = await fetch(path, options);
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const msg = (data && (data.detail?.[0]?.msg || data.detail)) || `${res.status} ${res.statusText}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

export function postImage(path, blob, fields = {}) {
  const fd = new FormData();
  fd.append("file", blob, "leaf.jpg");
  for (const [k, v] of Object.entries(fields)) fd.append(k, v);
  return api(path, { method: "POST", body: fd });
}

let toastTimer;
export function toast(text, ms = 3200) {
  const t = $("#toast");
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), ms);
}

export function busy(on, text = "Analysing leaf…") {
  $("#busy-text").textContent = text;
  $("#busy").hidden = !on;
}

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Minimal, safe markdown: **bold**, *italic*/_italic_, "- " bullets, paragraphs.
export function md(text) {
  const inline = (s) => esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*(?!\s)(.+?)\*/g, "$1<i>$2</i>")
    .replace(/(^|\s)_(.+?)_(?=\s|$|[.,])/g, "$1<i>$2</i>");
  const out = [];
  let list = null;
  for (const raw of String(text).split("\n")) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)$/);
    if (bullet) {
      if (!list) { list = []; out.push(list); }
      list.push(`<li>${inline(bullet[1])}</li>`);
    } else {
      list = null;
      if (line.trim()) out.push(`<p>${inline(line)}</p>`);
    }
  }
  return out.map((b) => (Array.isArray(b) ? `<ul>${b.join("")}</ul>` : b)).join("");
}

export const STATUS_TEXT = {
  healthy: "Healthy",
  diseased: "Disease detected",
  uncertain: "Not sure – retake",
  no_leaf: "No leaf found",
};

export function healthColor(score) {
  if (score >= 80) return "var(--good)";
  if (score >= 50) return "var(--warn)";
  return "var(--bad)";
}

export function fmtDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function pct(x) {
  return `${Math.round(Number(x) * 100)}%`;
}
