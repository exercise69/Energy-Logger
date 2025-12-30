const CACHE_NAME = "shelly-logger-v2";
const FILES_TO_CACHE = [
  "/html/index.html",
  "/html/style.css",
  "/html/app.js",
  "/html/manifest.json",
  "/html/icon-180.png",
  "/html/icon-192.png",
  "/html/icon-512.png",
  "/html/service-worker.js"
];

// ================= INSTALL =================
self.addEventListener("install", (evt) => {
  evt.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(FILES_TO_CACHE))
  );
  self.skipWaiting();
});

// ================= ACTIVATE =================
self.addEventListener("activate", (evt) => {
  evt.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((key) => key !== CACHE_NAME ? caches.delete(key) : null)
      )
    )
  );
  self.clients.claim();
});

// ================= FETCH =================
self.addEventListener("fetch", (evt) => {
  const url = new URL(evt.request.url);

  // API-Aufrufe: Network-first für GET, POST direkt durchlassen
  if (
    url.pathname.endsWith("status.json") ||
    url.pathname.endsWith("toggle_shelly") ||
    url.pathname.endsWith("toggle_logging") ||
    url.pathname.endsWith("set_shelly_time")
  ) {
    if (evt.request.method === "POST") {
      // POST direkt zum Server weiterleiten
      return;
    }

    // GET → Network-first mit Cache-Update
    evt.respondWith((async () => {
      try {
        const resp = await fetch(evt.request);

        // Cache aktualisieren
        const cache = await caches.open(CACHE_NAME);
        cache.put(evt.request, resp.clone());

        return resp;
      } catch (err) {
        // Offline-Fallback
        const cached = await caches.match(evt.request);
        if (cached) return cached;
        return new Response(null, { status: 503, statusText: "Offline" });
      }
    })());
    return;
  }

  // Statische Dateien: Cache-first Strategie
  evt.respondWith(
    caches.match(evt.request).then((cachedResp) => {
      return cachedResp || fetch(evt.request).catch(() => {
        return new Response("Offline", { status: 503, statusText: "Offline" });
      });
    })
  );
});
