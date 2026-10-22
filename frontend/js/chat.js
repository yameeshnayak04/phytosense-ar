// Plant assistant chat (Gemini when configured, offline knowledge base otherwise).
import { $, api, esc, md, state } from "./util.js";

const history = [];
const SUGGESTIONS = {
  scan: ["How do I treat this?", "Any organic remedy?", "How do I prevent it next season?", "Is it spreading to other plants?"],
  none: ["How do I treat tomato early blight?", "Organic remedy for powdery mildew", "What causes potato late blight?"],
};

export function initChat() {
  $("#chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("#chat-input");
    const text = input.value.trim();
    if (text) { input.value = ""; send(text); }
  });
  setupMic();
  renderContext();
  if (!$("#chat-log").children.length) {
    addMessage("bot", "Hi! I'm your PhytoSense plant assistant. Scan a leaf, then ask me how to treat or prevent the problem – or ask any farming question.");
  }
}

export function setContext(result) {
  state.lastResult = result;
  renderContext();
}

function renderContext() {
  const r = state.lastResult;
  $("#chat-context").innerHTML = r
    ? `Talking about: <b>${esc(r.crop)} – ${esc(r.healthy ? "Healthy" : r.disease)}</b> (${Math.round(r.confidence * 100)}% sure, ${r.severity}% infected)`
    : "No scan selected – ask any plant question.";
  const chips = r ? SUGGESTIONS.scan : SUGGESTIONS.none;
  $("#chat-chips").innerHTML = chips.map((c) => `<button class="chip" type="button">${esc(c)}</button>`).join("");
  $("#chat-chips").querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => send(b.textContent)));
}

function addMessage(role, text, source) {
  const div = document.createElement("div");
  div.className = `msg ${role === "user" ? "user" : "bot"}`;
  if (role === "user") div.textContent = text;
  else div.innerHTML = md(text) + (source ? `<span class="src">${source === "gemini" ? "Gemini AI" : "Offline knowledge base"}</span>` : "");
  $("#chat-log").appendChild(div);
  div.scrollIntoView({ behavior: "smooth", block: "end" });
  return div;
}

async function send(text) {
  addMessage("user", text);
  const typing = addMessage("bot", "Thinking…");
  typing.classList.add("typing");
  const r = state.lastResult;
  const context = r ? {
    label: r.label, crop: r.crop, disease: r.disease, status: r.status,
    confidence: r.confidence, severity: r.severity, severity_level: r.severity_level,
  } : null;
  try {
    const res = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: history.slice(-8), context, lang: state.lang }),
    });
    typing.remove();
    addMessage("bot", res.reply, res.source);
    history.push({ role: "user", text }, { role: "assistant", text: res.reply });
  } catch (e) {
    typing.remove();
    addMessage("bot", `Sorry, something went wrong: ${e.message}`);
  }
}

function setupMic() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return;
  const btn = $("#btn-mic");
  btn.hidden = false;
  btn.addEventListener("click", () => {
    const rec = new SR();
    rec.lang = { hi: "hi-IN", mr: "mr-IN", ta: "ta-IN", te: "te-IN", kn: "kn-IN", bn: "bn-IN", gu: "gu-IN", pa: "pa-IN" }[state.lang] || "en-IN";
    rec.onresult = (e) => send(e.results[0][0].transcript);
    rec.onerror = () => btn.classList.remove("active");
    rec.onend = () => btn.classList.remove("active");
    btn.classList.add("active");
    rec.start();
  });
}
