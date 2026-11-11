"use strict";
// 2.3: service worker «Конспекту».
// E7 — офлайн: оболонка застосунку з кешу; дані (заняття, картки, PDF) — спершу з мережі, а без неї — збережена копія.
// E5 — сповіщення Web Push: показує й відкриває потрібну сторінку.
const VERSION = "kp-2.9.0";
const SHELL = "shell-" + VERSION, DATA = "data-v1";
const SHELL_URLS = ["/", "/static/style.css?v=31", "/static/study.js?v=22", "/static/course.js?v=32", "/static/semester.js?v=2", "/static/project.js?v=4", "/static/chat.js?v=2", "/static/share.js?v=1", "/static/app.js?v=35",
  "/static/icon.svg", "/static/icon-192.png", "/static/manifest.webmanifest"];
// які GET-запити API зберігати для офлайну (решта — лише мережа)
const CACHE_API = [/^\/api\/(state|schedule|week|deadlines|checklists|semester|study(\/progress)?)$/, /^\/api\/lectures$/,
  /^\/api\/lectures\/[^/]+$/, /^\/api\/lectures\/[^/]+\/output\/.+/, /^\/api\/subjects\/[^/]+\/(course|materials|szpargalka\.pdf|project)$/, /^\/api\/subjects\/[^/]+\/project\/file\/(current|steps)\/.+/];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_URLS)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k.startsWith("shell-") && k !== SHELL).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const cacheable = (url) => CACHE_API.some((rx) => rx.test(url.pathname));
const keyOf = (url) => url.pathname + (url.pathname.startsWith("/api/lectures/") && url.pathname.includes("/output/") ? "" : url.search);

async function networkFirst(req, url) {
  const cache = await caches.open(DATA);
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(keyOf(url), res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(keyOf(url));
    if (hit) { const h = new Headers(hit.headers); h.set("X-Konspekt-Offline", "1"); return new Response(hit.body, { status: hit.status, headers: h }); }
    throw err;
  }
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname === "/" || url.pathname.startsWith("/static/")) {  // оболонка: мережа, а без неї — кеш
    e.respondWith(fetch(req).then((res) => { if (res.ok) caches.open(SHELL).then((c) => c.put(req, res.clone())); return res; })
      .catch(() => caches.match(req, { ignoreSearch: url.pathname === "/" }).then((r) => r || caches.match("/"))));
    return;
  }
  if (url.pathname.startsWith("/api/") && cacheable(url)) e.respondWith(networkFirst(req, url));
});

// «Прогрів»: застосунок надсилає список свіжих конспектів і даних — зберігаємо їх, поки є зв'язок
self.addEventListener("message", (e) => {
  const m = e.data || {};
  if (m.type !== "warm" || !Array.isArray(m.urls)) return;
  e.waitUntil((async () => {
    const cache = await caches.open(DATA);
    for (const u of m.urls.slice(0, 120)) {
      try { const url = new URL(u, location.origin); const res = await fetch(url); if (res.ok) await cache.put(keyOf(url), res); } catch { /* немає зв'язку — наступного разу */ }
    }
  })());
});

self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch { d = { title: e.data && e.data.text() }; }
  e.waitUntil(self.registration.showNotification(d.title || "Конспект", {
    body: d.body || "", tag: d.tag || "konspekt", icon: "/static/icon-192.png", badge: "/static/icon-192.png", data: { url: d.url || "#/" },
  }));
});
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const target = "/" + (e.notification.data && e.notification.data.url || "#/");
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((cs) => {
    for (const c of cs) { if ("focus" in c) { c.navigate(target).catch(() => {}); return c.focus(); } }
    return self.clients.openWindow(target);
  }));
});
