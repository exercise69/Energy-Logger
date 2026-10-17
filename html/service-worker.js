/**
 * Energy-Logger service worker
 *
 * Strategy (taken from the SolarLoader):
 *  - anything unknown   → not touched, the browser fetches it directly
 *  - images / icons     → cache first (they never change)
 *  - HTML / CSS / JS    → stale-while-revalidate: served from cache at once,
 *                         refreshed in the background.
 *
 * CACHE_NAME depends on the build and is set by tools/stamp.py, so a new UI
 * replaces the old cache on the next start instead of showing the old page.
 *
 * Only GET requests for the known static files go through the cache. API
 * calls (status.json, toggle_*, logs) always reach the device, so the app
 * sees a real network error when the logger is unreachable.
 */

const CACHE_NAME = "energy-logger-v2.0-b21";   // set by tools/stamp.py
const CACHE_IMGS = "energy-logger-imgs-v1";

const STATIC_SHELL = [
  "./", "index.html", "style.css", "app.js", "manifest.json", "offline.html"
];

const STATIC_IMGS = ["icon-180.png", "icon-192.png", "icon-512.png"];

// Install: load one file after the other, do not overload the ESP32
self.addEventListener("install", (evt) => {
  evt.waitUntil((async () => {
    const shell = await caches.open(CACHE_NAME);
    const imgs = await caches.open(CACHE_IMGS);
    for (const f of STATIC_SHELL) {
      try { await shell.add(f); } catch (e) { console.warn("[SW] shell:", f, e); }
    }
    for (const f of STATIC_IMGS) {
      try { await imgs.add(f); } catch (e) { console.warn("[SW] img:", f, e); }
    }
  })());
  self.skipWaiting();
});

// Activate: delete old caches
self.addEventListener("activate", (evt) => {
  evt.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys
        .filter(k => k !== CACHE_NAME && k !== CACHE_IMGS)
        .map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (evt) => {
  const url = new URL(evt.request.url);
  if (evt.request.method !== "GET") return;
  if (url.origin !== self.location.origin) return;
  if (!isImage(url) && !isShell(url)) return;

  if (isImage(url)) {
    evt.respondWith(
      caches.match(evt.request).then(cached =>
        cached || fetch(evt.request).then(res => {
          const copy = res.clone();
          caches.open(CACHE_IMGS).then(c => c.put(evt.request, copy));
          return res;
        })
      )
    );
    return;
  }

  evt.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(evt.request, { ignoreSearch: true });
      const network = fetch(evt.request).then(res => {
        if (res.ok) cache.put(evt.request, res.clone());
        return res;
      }).catch(() => null);

      if (cached) {
        evt.waitUntil(network);   // refresh in the background
        return cached;
      }
      return (await network) || (await cache.match("offline.html")) ||
             new Response("Offline", { status: 503 });
    })
  );
});

function isShell(url) {
  const name = url.pathname.replace(/^.*\//, "");
  return name === "" || STATIC_SHELL.includes(name);
}

function isImage(url) {
  return /\.(png|ico|jpg|jpeg|svg|webp)$/.test(url.pathname);
}
