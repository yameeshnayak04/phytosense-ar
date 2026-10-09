// Service worker: caches the app shell so the UI opens offline (diagnosis still needs the server).
const CACHE = "phytosense-v1";
const SHELL = ["./", "index.html", "css/styles.css", "js/app.js", "js/ar.js", "js/overlay.js", "js/result.js",
  "js/history.js", "js/chat.js", "js/library.js", "js/util.js", "icons/icon.svg", "icons/icon-192.png", "manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
// Network first for everything (fresh code while developing), cache as fallback for the shell.
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/") || url.pathname.startsWith("/uploads/")) return;
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
