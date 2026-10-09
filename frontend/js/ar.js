// Live AR scanner: camera -> small frames to /api/frame -> overlay drawn on top of the video.
import { $, busy, postImage, state, toast } from "./util.js";
import { drawOverlay } from "./overlay.js";

const FRAME_SIDE = 448;          // frames sent for live inference
const STALE_MS = 1500;           // hide overlay if no fresh answer

let stream = null;
let facing = "environment";
let live = true;
let inferring = false;
let latest = null;
let latestAt = 0;
let lastTimes = [];
let rafId = 0;
let onCaptured = () => {};

const video = () => $("#ar-video");
const canvas = () => $("#ar-canvas");

export function initAR({ onResult }) {
  onCaptured = onResult;
  $("#btn-start-cam").addEventListener("click", startCamera);
  $("#btn-flip").addEventListener("click", () => {
    facing = facing === "environment" ? "user" : "environment";
    startCamera();
  });
  $("#btn-live").addEventListener("click", toggleLive);
  $("#btn-capture").addEventListener("click", capture);
  window.addEventListener("resize", sizeCanvas);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopCamera();
  });
}

export async function startCamera() {
  const err = $("#cam-error");
  err.textContent = "";
  if (!navigator.mediaDevices?.getUserMedia) {
    err.textContent = "Camera needs HTTPS or localhost. Use the Upload tab, or open the app over HTTPS (see README).";
    return;
  }
  stopCamera();
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: facing }, width: { ideal: 1280 }, height: { ideal: 960 } },
      audio: false,
    });
  } catch (e) {
    err.textContent = `Could not open camera: ${e.message}`;
    return;
  }
  const v = video();
  v.srcObject = stream;
  await v.play().catch(() => {});
  $("#ar-placeholder").hidden = true;
  $("#ar-hud").hidden = false;
  for (const id of ["#btn-live", "#btn-capture", "#btn-flip"]) $(id).disabled = false;
  sizeCanvas();
  latest = null;
  cancelAnimationFrame(rafId);
  rafId = requestAnimationFrame(render);
  inferLoop();
}

export function stopCamera() {
  if (stream) stream.getTracks().forEach((t) => t.stop());
  stream = null;
  cancelAnimationFrame(rafId);
  const placeholder = $("#ar-placeholder");
  if (placeholder) placeholder.hidden = false;
  $("#ar-hud").hidden = true;
  for (const id of ["#btn-live", "#btn-capture", "#btn-flip"]) $(id).disabled = true;
  const c = canvas();
  c.getContext("2d").clearRect(0, 0, c.width, c.height);
}

function toggleLive() {
  live = !live;
  const b = $("#btn-live");
  b.setAttribute("aria-pressed", String(live));
  b.querySelector("span").textContent = live ? "Pause" : "Resume";
  b.querySelector("svg").innerHTML = live ? '<path d="M8 5v14M16 5v14"/>' : '<path d="M7 4l12 8-12 8z"/>';
  if (live) inferLoop();
}

function sizeCanvas() {
  const c = canvas();
  const r = c.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  c.width = Math.round(r.width * dpr);
  c.height = Math.round(r.height * dpr);
}

// Maps normalised video coords to canvas pixels, matching CSS `object-fit: cover`.
function coverMap() {
  const v = video(), c = canvas();
  const vw = v.videoWidth, vh = v.videoHeight;
  const s = Math.max(c.width / vw, c.height / vh);
  const dx = (c.width - vw * s) / 2, dy = (c.height - vh * s) / 2;
  return ([nx, ny]) => [dx + nx * vw * s, dy + ny * vh * s];
}

function grabFrame(maxSide) {
  const v = video();
  const k = Math.min(1, maxSide / Math.max(v.videoWidth, v.videoHeight));
  const off = document.createElement("canvas");
  off.width = Math.round(v.videoWidth * k);
  off.height = Math.round(v.videoHeight * k);
  off.getContext("2d").drawImage(v, 0, 0, off.width, off.height);
  return new Promise((res) => off.toBlob(res, "image/jpeg", maxSide > 1000 ? 0.92 : 0.75));
}

async function inferLoop() {
  if (inferring) return;
  inferring = true;
  while (stream && live && !document.hidden) {
    if (!video().videoWidth) { await sleep(100); continue; }
    const t0 = performance.now();
    try {
      latest = await postImage("/api/frame", await grabFrame(FRAME_SIDE));
      latestAt = performance.now();
      lastTimes = [...lastTimes.slice(-4), latestAt - t0];
      const avg = lastTimes.reduce((a, b) => a + b, 0) / lastTimes.length;
      $("#ar-fps").textContent = `AR · ${(1000 / avg).toFixed(1)} fps`;
    } catch (e) {
      $("#ar-hint").textContent = /loading/i.test(e.message) ? "AI model is loading…" : "Server not reachable";
      await sleep(1000);
    }
  }
  inferring = false;
}

function render(t) {
  const c = canvas();
  const ctx = c.getContext("2d");
  ctx.clearRect(0, 0, c.width, c.height);
  const fresh = latest && performance.now() - latestAt < STALE_MS;
  if (fresh && video().videoWidth) {
    const dpr = window.devicePixelRatio || 1;
    drawOverlay(ctx, latest, coverMap(), { scale: dpr, pulse: (t % 1500) / 1500 });
  }
  if (live) {
    $("#ar-hint").textContent = !fresh ? "Looking for a leaf…"
      : !latest.leaf_found ? "Point at a single leaf"
      : latest.status === "uncertain" ? "Hold steady, move closer"
      : latest.status === "healthy" ? "Leaf looks healthy" : "Disease spotted – tap ● for details";
  } else {
    $("#ar-hint").textContent = "Live AR paused";
  }
  rafId = requestAnimationFrame(render);
}

async function capture() {
  if (!video().videoWidth) return;
  const blob = await grabFrame(1600);
  busy(true);
  try {
    const result = await postImage("/api/diagnose", blob);
    state.lastResult = result;
    onCaptured(result, URL.createObjectURL(blob));
  } catch (e) {
    toast(`Diagnosis failed: ${e.message}`);
  } finally {
    busy(false);
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
