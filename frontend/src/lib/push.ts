/**
 * Web Push subscription helpers — service worker + VAPID.
 */

const API = process.env.NEXT_PUBLIC_API_URL || "";

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function ab2b64(buf: ArrayBuffer | null): string {
  if (!buf) return "";
  const bytes = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export async function ensurePushSubscription(authToken: string): Promise<{
  ok: boolean;
  reason?: string;
  subscription?: PushSubscription;
}> {
  if (typeof window === "undefined" || !("serviceWorker" in navigator) || !("PushManager" in window)) {
    return { ok: false, reason: "Push non supporté" };
  }

  // Register SW
  let registration: ServiceWorkerRegistration;
  try {
    registration = await navigator.serviceWorker.register("/sw.js");
    if (!registration.active) await navigator.serviceWorker.ready;
  } catch (e) {
    return { ok: false, reason: `SW register: ${(e as Error).message}` };
  }

  // Permission
  if (Notification.permission === "denied") {
    return { ok: false, reason: "Notifications bloquées dans le navigateur" };
  }
  if (Notification.permission === "default") {
    const p = await Notification.requestPermission();
    if (p !== "granted") return { ok: false, reason: "Permission refusée" };
  }

  // Get VAPID public key
  let publicKey: string;
  try {
    const r = await fetch(`${API}/push/vapid-public-key`);
    if (!r.ok) return { ok: false, reason: "VAPID key indisponible" };
    publicKey = (await r.json()).public_key;
  } catch {
    return { ok: false, reason: "VAPID fetch failed" };
  }

  // Subscribe
  let sub: PushSubscription;
  try {
    const existing = await registration.pushManager.getSubscription();
    if (existing) {
      sub = existing;
    } else {
      sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      });
    }
  } catch (e) {
    return { ok: false, reason: `Subscribe: ${(e as Error).message}` };
  }

  // Persist côté backend
  const payload = {
    endpoint: sub.endpoint,
    p256dh: ab2b64(sub.getKey("p256dh")),
    auth_key: ab2b64(sub.getKey("auth")),
    user_agent: navigator.userAgent,
  };
  try {
    const r = await fetch(`${API}/push/subscribe`, {
      method: "POST",
      headers: { Authorization: `Bearer ${authToken}`, "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) return { ok: false, reason: `Persist failed (${r.status})` };
  } catch {
    return { ok: false, reason: "Persist network error" };
  }

  return { ok: true, subscription: sub };
}
