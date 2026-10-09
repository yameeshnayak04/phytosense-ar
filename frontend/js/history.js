// Scan history: stats, health trend sparkline, list of saved scans.
import { $, STATUS_TEXT, api, esc, fmtDate, healthColor, toast } from "./util.js";
import { showResult } from "./result.js";

export async function loadHistory() {
  let data;
  try {
    data = await api("/api/scans");
  } catch (e) {
    $("#scan-list").innerHTML = `<li class="empty">Could not load history: ${esc(e.message)}</li>`;
    return;
  }
  const { scans, stats } = data;
  const healthy = stats.by_status.healthy || 0;
  const diseased = stats.by_status.diseased || 0;
  $("#stats").innerHTML = `
    <div class="stat"><b>${stats.total}</b><span>Scans</span></div>
    <div class="stat"><b style="color:var(--good)">${healthy}</b><span>Healthy</span></div>
    <div class="stat"><b style="color:var(--bad)">${diseased}</b><span>Diseased</span></div>
    <div class="stat"><b>${stats.avg_health}</b><span>Avg health</span></div>`;

  $("#trend").innerHTML = trendSvg(scans.slice().reverse());

  const list = $("#scan-list");
  if (!scans.length) {
    list.innerHTML = `<li class="empty">No scans yet. Use AR Scan or Upload to diagnose your first leaf.</li>`;
    return;
  }
  list.innerHTML = scans.map((s) => `
    <li class="scan-item" data-id="${s.id}">
      <img src="${esc(s.image_url)}" alt="" loading="lazy">
      <div class="meta">
        <b>${esc(s.status === "healthy" ? `${s.crop} · Healthy` : `${s.crop} · ${s.disease}`)}</b>
        <span class="badge ${s.status}">${STATUS_TEXT[s.status] || s.status}</span>
        <span class="muted small"> ${fmtDate(s.created_at)} · ${Math.round(s.confidence * 100)}%</span>
      </div>
      <span class="health" style="color:${healthColor(s.health_score)}">${s.health_score}</span>
      <button class="del" title="Delete scan" aria-label="Delete scan">✕</button>
    </li>`).join("");

  list.querySelectorAll(".scan-item").forEach((li) => {
    li.addEventListener("click", async (e) => {
      const id = li.dataset.id;
      if (e.target.closest(".del")) {
        e.stopPropagation();
        if (!confirm("Delete this scan?")) return;
        await api(`/api/scans/${id}`, { method: "DELETE" }).catch((err) => toast(err.message));
        loadHistory();
        return;
      }
      const scan = await api(`/api/scans/${id}`);
      showResult({ ...scan.result, scan_id: scan.id }, scan.image_url);
    });
  });
}

function trendSvg(scans) {
  if (scans.length < 2) return `<p class="muted small" style="margin:0">Health trend appears after two or more scans.</p>`;
  const W = 600, H = 70, pad = 6;
  const pts = scans.map((s, i) => [pad + (i * (W - 2 * pad)) / (scans.length - 1), H - pad - (s.health_score / 100) * (H - 2 * pad)]);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join("");
  const last = scans.at(-1).health_score;
  return `<div class="muted small">Health trend · last ${scans.length} scans · latest <b style="color:${healthColor(last)}">${last}</b></div>
    <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Health score trend">
      <line x1="0" x2="${W}" y1="${H - pad - 0.5 * (H - 2 * pad)}" y2="${H - pad - 0.5 * (H - 2 * pad)}" stroke="var(--border)" stroke-dasharray="4 4"/>
      <path d="${d}" stroke="var(--primary)" fill="none" vector-effect="non-scaling-stroke"/>
    </svg>`;
}
