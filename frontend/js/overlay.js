// Draws the AR layer: leaf outline, lesion patches, corner brackets and a label tag.
// `map([nx, ny])` converts normalised image coordinates (0..1) to canvas pixels.

const COLORS = {
  healthy: "#22c55e",
  diseased: "#ef4444",
  uncertain: "#f59e0b",
  no_leaf: "#f59e0b",
  no_plant: "#94a3b8",
};

const short = (s) => String(s || "").replace(/\s*\(.*\)\s*$/, "");

function path(ctx, pts, map) {
  ctx.beginPath();
  pts.forEach((p, i) => {
    const [x, y] = map(p);
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.closePath();
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

export function drawOverlay(ctx, result, map, { scale = 1, pulse = 0, showLabel = true } = {}) {
  if (!result) return;
  if (!result.leaf_found) {
    // Whole plant / tree in view: name it, ask for a closer leaf for the health check.
    if (showLabel && result.species) {
      const cw = ctx.canvas.width;
      drawTag(ctx, `${result.crop}${result.species.hindi ? ` · ${result.species.hindi}` : ""}`,
        `${Math.round(result.species.confidence * 100)}% sure · move closer to a leaf`, cw * 0.3, 70 * scale, cw * 0.7, "#38bdf8", scale);
    }
    return;
  }
  const { overlay } = result;
  const color = COLORS[result.status] || COLORS.uncertain;
  const s = scale;

  // Leaf outline with a soft glow.
  if (overlay.leaf_polygon.length > 2) {
    ctx.save();
    path(ctx, overlay.leaf_polygon, map);
    ctx.fillStyle = result.status === "healthy" ? "rgba(34,197,94,0.10)" : "rgba(255,255,255,0.06)";
    ctx.fill();
    ctx.shadowColor = color;
    ctx.shadowBlur = 12 * s;
    ctx.lineWidth = 2.5 * s;
    ctx.strokeStyle = color;
    ctx.setLineDash([10 * s, 6 * s]);
    ctx.lineDashOffset = -pulse * 40 * s;
    ctx.stroke();
    ctx.restore();
  }

  // Lesions: only highlight when the model says the leaf is not healthy.
  if (result.status !== "healthy") {
    ctx.save();
    const a = 0.35 + 0.15 * Math.sin(pulse * Math.PI * 2);
    for (const poly of overlay.lesions) {
      if (poly.length < 3) continue;
      path(ctx, poly, map);
      ctx.fillStyle = `rgba(239,68,68,${a.toFixed(3)})`;
      ctx.fill();
      ctx.lineWidth = 1.5 * s;
      ctx.strokeStyle = "rgba(254,202,202,0.95)";
      ctx.stroke();
    }
    ctx.restore();
  }

  // Corner brackets around the leaf.
  if (overlay.bbox) {
    const [bx, by, bw, bh] = overlay.bbox;
    const [x0, y0] = map([bx, by]);
    const [x1, y1] = map([bx + bw, by + bh]);
    const L = Math.min(28 * s, (x1 - x0) / 4, (y1 - y0) / 4);
    ctx.save();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 3 * s;
    ctx.lineCap = "round";
    ctx.beginPath();
    for (const [cx, cy, dx, dy] of [[x0, y0, 1, 1], [x1, y0, -1, 1], [x0, y1, 1, -1], [x1, y1, -1, -1]]) {
      ctx.moveTo(cx, cy + dy * L); ctx.lineTo(cx, cy); ctx.lineTo(cx + dx * L, cy);
    }
    ctx.stroke();
    ctx.restore();

    if (showLabel) {
      const title = result.status === "healthy" ? `${result.crop} · Healthy`
        : result.status === "uncertain" ? `${result.crop} · not sure – move closer`
        : `${result.crop} · ${short(result.disease)}`;
      const pctTxt = `${Math.round(result.confidence * 100)}% sure`;
      const sub = result.status === "uncertain" ? `best guess: ${short(result.disease)} ${pctTxt}`
        : result.severity_reliable === false || result.healthy ? `${pctTxt} · health ${result.health_score}`
        : `${pctTxt} · ${result.severity}% infected · health ${result.health_score}`;
      drawTag(ctx, title, sub, x0, y0, x1, color, s);
    }
  }
}

function drawTag(ctx, title, sub, x0, y0, x1, color, s) {
  ctx.save();
  ctx.font = `700 ${14 * s}px system-ui, sans-serif`;
  const w1 = ctx.measureText(title).width;
  ctx.font = `500 ${11.5 * s}px system-ui, sans-serif`;
  const w2 = ctx.measureText(sub).width;
  const w = Math.max(w1, w2) + 22 * s;
  const h = 44 * s;
  const cw = ctx.canvas.width;
  let x = Math.min(Math.max(8 * s, (x0 + x1) / 2 - w / 2), cw - w - 8 * s);
  let y = y0 - h - 10 * s;
  if (y < 8 * s) y = y0 + 10 * s;
  roundRect(ctx, x, y, w, h, 10 * s);
  ctx.fillStyle = "rgba(10,20,14,0.82)";
  ctx.fill();
  ctx.fillStyle = color;
  ctx.fillRect(x, y + 8 * s, 4 * s, h - 16 * s);
  ctx.fillStyle = "#fff";
  ctx.font = `700 ${14 * s}px system-ui, sans-serif`;
  ctx.fillText(title, x + 12 * s, y + 19 * s);
  ctx.fillStyle = "#cfe3d5";
  ctx.font = `500 ${11.5 * s}px system-ui, sans-serif`;
  ctx.fillText(sub, x + 12 * s, y + 35 * s);
  ctx.restore();
}

// Render an image + overlay into a canvas (used for results and history).
export function renderAnnotated(canvas, img, result, withOverlay = true) {
  const w = img.naturalWidth, h = img.naturalHeight;
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0, w, h);
  if (withOverlay) {
    const scale = Math.max(1, Math.min(w, h) / 380);
    drawOverlay(ctx, result, ([nx, ny]) => [nx * w, ny * h], { scale, pulse: 0.25 });
  }
}
