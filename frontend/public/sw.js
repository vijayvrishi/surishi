const CACHE = "surishi-v2";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(["/"])).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  // Never cache API calls or backend-served docs
  if (url.pathname.startsWith("/api") || url.pathname === "/docs" || url.pathname === "/openapi.json") return;

  // App navigation: network first so deploys show up immediately; cached shell as offline fallback
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put("/", copy));
          return res;
        })
        .catch(() => caches.match("/"))
    );
    return;
  }

  // Hashed build assets: cache first (immutable filenames)
  if (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/icons/")) {
    event.respondWith(
      caches.open(CACHE).then(async (c) => {
        const hit = await c.match(event.request);
        if (hit) return hit;
        const res = await fetch(event.request);
        if (res.ok) c.put(event.request, res.clone());
        return res;
      })
    );
  }
});
