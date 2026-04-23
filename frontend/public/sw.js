// FinSight service worker — Web Push + PWA offline basic.
//
// VERSIONING : bump CACHE_NAME à chaque changement de code client pour
// forcer le purge des caches obsolètes côté PWA installée. Sans ça, la
// version installée continue de servir un HTML/JS cached après déploiement.
const CACHE_NAME = "finsight-v3-2026-04-23";
const STATIC_ASSETS = ["/", "/app", "/manifest.json", "/logo.svg", "/icon.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)));
    await self.clients.claim();
    const clients = await self.clients.matchAll({ includeUncontrolled: true, type: "window" });
    for (const c of clients) {
      c.postMessage({ type: "SW_UPDATED", version: CACHE_NAME });
    }
  })());
});

// Canal message côté SW (forcing skipWaiting depuis la page si besoin)
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

// Network-first avec fallback cache pour la navigation.
// Ignore les requêtes API (toujours network) ET les bundles /_next/*
// (Next.js gère déjà son cache via hashed filenames).
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/") || url.hostname.includes("api.")) return;
  if (url.pathname.startsWith("/_next/")) return;
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() => caches.match("/") || caches.match("/app"))
    );
  }
});

self.addEventListener("push", (event) => {
  let data = { title: "FinSight IA", body: "Nouvelle alerte", url: "/app", icon: "/icon.png" };
  try {
    if (event.data) data = { ...data, ...event.data.json() };
  } catch {}
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: data.icon || "/icon.png",
      badge: "/icon.png",
      data: { url: data.url || "/app" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/app";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if (c.url.includes(url)) return c.focus();
      }
      return clients.openWindow(url);
    }),
  );
});

