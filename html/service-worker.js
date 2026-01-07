const CACHE_NAME = "shelly-logger-v5.9"; // Version erhöht für Update
const FILES_TO_CACHE = [
  "/html/index.html",
  "/html/style.css",
  "/html/app.js",
  "/html/manifest.json",
  "/html/icon-180.png",
  "/html/icon-192.png",
  "/html/icon-512.png",
  "/html/offline.html",
  "/service-worker.js"
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

  // 1. SPEZIALFALL: Hauptseite (Root oder index.html)
  // Strategie: Network-First. Wenn offline -> offline.html zeigen.
  if (url.pathname === "/" || url.pathname.endsWith("index.html") || url.pathname.endsWith("/html/")) {
    evt.respondWith(
      fetch(evt.request).catch(async () => {
        const cache = await caches.open(CACHE_NAME);
        return await cache.match("/html/offline.html");
      })
    );
    return;
  }

  // 2. SPEZIALFALL: status.json
  // Wir lassen diese Anfrage IMMER direkt ans Netzwerk gehen (kein Cache-Fallback),
  // damit die offline.html zuverlässig merkt, wann der Server wieder da ist.
  if (url.pathname.endsWith("status.json")) {
    evt.respondWith(fetch(evt.request));
    return;
  }

  // 3. ANDERE API-Aufrufe (POST direkt, GET mit Cache-Update)
  if (
    url.pathname.endsWith("toggle_shelly") ||
    url.pathname.endsWith("toggle_logging") ||
    url.pathname.endsWith("set_shelly_time")
  ) {
    if (evt.request.method === "POST") {
      evt.respondWith(fetch(evt.request));
      return;
    }

    evt.respondWith((async () => {
      try {
        const resp = await fetch(evt.request);
        const cache = await caches.open(CACHE_NAME);
        cache.put(evt.request, resp.clone());
        return resp;
      } catch (err) {
        const cached = await caches.match(evt.request);
        if (cached) return cached;
        return new Response(JSON.stringify({ online: false }), {
          headers: { "Content-Type": "application/json" }
        });
      }
    })());
    return;
  }

  // 4. STATISCHE DATEIEN (CSS, JS, Bilder): Cache-first Strategie
  evt.respondWith(
    caches.match(evt.request).then((cachedResp) => {
      return cachedResp || fetch(evt.request).catch(async () => {
        // Fallback falls auch im Cache nichts ist (z.B. neue Bilder)
        const offline = await caches.match("/html/offline.html");
        return offline || new Response("Offline", { status: 503 });
      });
    })
  );
});

