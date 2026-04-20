// FinSight service worker — handle Web Push notifications.
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

self.addEventListener("install", (e) => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
