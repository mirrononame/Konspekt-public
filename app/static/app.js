/* Конспект — фронтенд (без збірки, без зовнішніх залежностей, працює офлайн) */
"use strict";

// ============================================================ utils
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const enc = encodeURIComponent;
const MONTHS = ["січ", "лют", "бер", "кві", "тра", "чер", "лип", "сер", "вер", "жов", "лис", "гру"];
const MONTHS_FULL = ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"];
const DAYS = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"];
const DAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"];
const PARITY = { all: "Щотижня", even: "Парні тижні", odd: "Непарні тижні" };
const LANG_SHORT = { pl: "PL", uk: "UA", ru: "RU", en: "EN" };

function fmtSize(b) {
  if (!b && b !== 0) return "";
  const u = ["Б", "КБ", "МБ", "ГБ"]; let i = 0;
  while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
  return `${b.toFixed(i > 1 ? 1 : 0)} ${u[i]}`;
}
function fmtDur(s) {
  if (!s) return "";
  s = Math.round(s); if (s < 60) return `${s} с`; const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h} год ${m} хв` : `${m} хв`;
}
function parseDate(d) { const [y, m, dd] = (d || "").split("-").map(Number); return y ? new Date(y, m - 1, dd) : null; }
function isoDate(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }
function fmtDate(d, withDay = false) {
  const x = parseDate(d); if (!x) return "—";
  const dow = (x.getDay() + 6) % 7;
  return `${withDay ? DAYS[dow].toLowerCase() + ", " : ""}${x.getDate()} ${MONTHS_FULL[x.getMonth()]}${x.getFullYear() !== new Date().getFullYear() ? " " + x.getFullYear() : ""}`;
}
function relTime(iso) {
  if (!iso) return ""; const t = new Date(iso).getTime(); const diff = (Date.now() - t) / 1000;
  if (diff < 60) return "щойно"; if (diff < 3600) return `${Math.floor(diff / 60)} хв тому`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} год тому`;
  return new Date(iso).toLocaleDateString("uk-UA");
}
function minutes(t) { const [h, m] = (t || "0:0").split(":").map(Number); return h * 60 + m; }
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
function h(html) { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; }

// ============================================================ icons
const ICONS = {
  home: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>',
  upload: '<path d="M12 16V4m0 0-4.5 4.5M12 4l4.5 4.5"/><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
  book: '<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v17H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M4 19.5V21.5M8 7h8M8 11h6"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r="1"/><circle cx="3.5" cy="12" r="1"/><circle cx="3.5" cy="18" r="1"/>',
  calendar: '<rect x="3" y="4.5" width="18" height="17" rx="2.5"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20.5 20.5-4.5-4.5"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  mic: '<rect x="9" y="2.5" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3.5"/>',
  slides: '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M12 17v4M8 21h8M7 9h6M7 12h10"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2.5"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
  file: '<path d="M14 2.5H6a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8.5z"/><path d="M14 2.5v6h6"/>',
  pdf: '<path d="M14 2.5H6a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8.5z"/><path d="M14 2.5v6h6M8 13h8M8 17h5"/>',
  trash: '<path d="M3 6h18M8 6V4.5A1.5 1.5 0 0 1 9.5 3h5A1.5 1.5 0 0 1 16 4.5V6m2.5 0-.8 13.1a2 2 0 0 1-2 1.9H8.3a2 2 0 0 1-2-1.9L5.5 6"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  sparkles: '<path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  check: '<path d="m4.5 12.5 5 5 10-11"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  pin: '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
  download: '<path d="M12 4v12m0 0-4.5-4.5M12 16l4.5-4.5"/><path d="M4 18v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  copy: '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14.7-4.3L3 9m0-5v5h5"/><path d="M4 13a8 8 0 0 0 14.7 4.3L21 15m0 5v-5h-5"/>',
  edit: '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
  alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4.5M12 8h.01"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  wave: '<path d="M2 12h2M6 8v8M10 4v16M14 7v10M18 10v4M22 12h0"/>',
  archive: '<rect x="2.5" y="3.5" width="19" height="5" rx="1.5"/><path d="M4.5 8.5V19a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5V8.5M10 12.5h4"/>',
  cpu: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
  undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
  video: '<rect x="2.5" y="5.5" width="13.5" height="13" rx="2.5"/><path d="m16 10 5.5-3.2v10.4L16 14"/>',
  phone: '<rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M11 18h2"/>',
  menu: '<circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/>',
  more: '<circle cx="12" cy="5" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="12" cy="19" r="1.6"/>',
  lock: '<rect x="4.5" y="10.5" width="15" height="10.5" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>',
  grad: '<path d="M2.5 9 12 4.5 21.5 9 12 13.5z"/><path d="M6.5 11v4.5c3.2 2.3 7.8 2.3 11 0V11M21.5 9v5"/>',
};
ICONS.play = '<path d="M7 4.5v15l12-7.5z"/>';
ICONS.code = '<path d="m8 8-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14"/>';
ICONS.help = '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.2a2.6 2.6 0 0 1 5 .9c0 1.8-2.5 2.2-2.5 3.9M12 17.2v.1"/>';
ICONS.map = '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14"/>';
ICONS.brain = '<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 6 1V5a3 3 0 0 0-3-1zM15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-6 1"/>';
const icon = (n, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ""}</svg>`;

// ============================================================ api
class ApiError extends Error {}
async function api(path, opts = {}) {
  const o = { ...opts, headers: { ...(opts.headers || {}) } };
  if (o.body && !(o.body instanceof FormData) && typeof o.body !== "string") {
    o.body = JSON.stringify(o.body); o.headers["Content-Type"] = "application/json";
  }
  let r;
  try { r = await fetch(path, o); }
  catch (e) { setOffline(true); throw new ApiError("Немає зв'язку з сервером"); }
  setOffline(r.headers.get("X-Konspekt-Offline") === "1");  // 2.3: відповідь зі збереженої копії (service worker)
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json().catch(() => ({})) : await r.text();
  if (!r.ok) throw new ApiError((data && data.detail) || `Помилка ${r.status}`);
  return data;
}
const GET = (p) => api(p);
const POST = (p, b) => api(p, { method: "POST", body: b });
const PUT = (p, b) => api(p, { method: "PUT", body: b });
const PATCH = (p, b) => api(p, { method: "PATCH", body: b });
const DEL = (p) => api(p, { method: "DELETE" });

function setOffline(v) { const el = $("#offline"); if (el) el.hidden = !v; }

// ============================================================ toasts & modals
function toast(msg, type = "ok", ms = 3600) {
  const el = h(`<div class="toast ${type}">${icon(type === "err" ? "alert" : type === "info" ? "info" : "check")}<div>${msg}</div></div>`);
  $("#toasts").append(el);
  setTimeout(() => { el.style.transition = "opacity .3s"; el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, ms);
}
function handleErr(e) { console.error(e); toast(esc(e.message || e), "err", 6000); }

function modal({ title, body = "", okText = "OK", cancelText = "Скасувати", danger = false, onOpen } = {}) {
  return new Promise((resolve) => {
    const bg = h(`<div class="modal-bg"><div class="modal" role="dialog" aria-modal="true">
      <h2>${title}</h2><div class="m-body">${body}</div>
      <div class="actions">${cancelText ? `<button class="btn ghost" data-a="no">${cancelText}</button>` : ""}
      <button class="btn ${danger ? "danger" : "primary"}" data-a="ok">${okText}</button></div></div></div>`);
    const close = (v) => { bg.remove(); document.removeEventListener("keydown", onKey); resolve(v); };
    const onKey = (e) => { if (e.key === "Escape") close(false); if (e.key === "Enter" && e.target.tagName !== "TEXTAREA") { e.preventDefault(); close(collect()); } };
    const collect = () => { const vals = {}; $$("[name]", bg).forEach((i) => (vals[i.name] = i.type === "checkbox" ? i.checked : i.value)); return Object.keys(vals).length ? vals : true; };
    bg.addEventListener("click", (e) => { if (e.target === bg) close(false); const a = e.target.closest("[data-a]"); if (a) close(a.dataset.a === "ok" ? collect() : false); });
    document.addEventListener("keydown", onKey);
    $("#modal-root").append(bg);
    onOpen && onOpen(bg);
    const f = $("input,textarea,select", bg) || $("[data-a=ok]", bg); f && f.focus();
  });
}
const confirmBox = (title, body, okText = "Так", danger = false) => modal({ title, body: `<p class="muted">${body}</p>`, okText, danger });

async function copyText(t, msg = "Скопійовано") {
  try { await navigator.clipboard.writeText(t); }
  catch { const ta = h(`<textarea style="position:fixed;opacity:0"></textarea>`); ta.value = t; document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove(); }
  if (msg) toast(msg);
}

// ============================================================ global state
const S = { state: null, schedule: null, rev: 0, view: null, dirty: false, uploading: false };
const subjById = (id) => (S.schedule?.subjects || []).find((s) => s.id === id);
const subjChip = (s) => s ? `<span class="subj-chip" style="--c:${s.color}">${esc(s.short || s.name)}</span>` : `<span class="subj-chip" style="--c:#94a3b8">Без предмета</span>`;
const statusBadge = (st, label) => `<span class="badge s-${st}"><span class="dot"></span>${esc(label || S.state?.status_labels?.[st] || st)}</span>`;
const typeLabel = (t) => (S.state?.types || {})[t] || t;

async function loadBase() {
  const [st, sc] = await Promise.all([GET("/api/state"), GET("/api/schedule")]);
  S.state = st; S.schedule = sc; S.rev = st.rev;
  applyTheme(st.settings.theme);
  if (st.beta) { document.title = "Конспект БЕТА"; document.body.classList.add("is-beta"); }
  if ((st.settings.ui_language || "uk") !== I18N.lang) i18nSet(st.settings.ui_language);  // 2.10: мова інтерфейсу
  renderNav();
}

function applyTheme(t) {
  if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
  else delete document.documentElement.dataset.theme;
}

// ============================================================ navigation
// 2.7: головні розділи + «Ще». 2.8: «Вчитися» (картки) прибрано — на його місці «Семестр» (колоквіуми, залік)
const NAV = [
  { href: "#/", ic: "home", t: "Сьогодні", badge: true },
  { href: "#/subjects", ic: "book", t: "Предмети" },
  { href: "#/semester", ic: "grad", t: "Семестр" },
];
const MORE_ITEMS = [
  { href: "#/schedule", ic: "calendar", t: "Розклад", d: "тиждень з USOS" },
  { href: "#/planner", ic: "clock", t: "Планер", d: "день, дорога, час для праці" },
  { href: "#/search", ic: "search", t: "Пошук", d: "по всіх конспектах" },
  { href: "#/settings", ic: "settings", t: "Налаштування", d: "USOS, ePortal, Whisper…" },
];

// нижня «шторка» для телефона (меню, дії лекції)
function openSheet(title, html, onBind) {
  closeSheet();
  const el = h(`<div class="sheet-bg" id="sheet"><div class="sheet" role="dialog" aria-modal="true"><div class="sheet-grip"></div>
    ${title ? `<div class="sheet-title">${title}</div>` : ""}<div class="sheet-body">${html}</div></div></div>`);
  el.addEventListener("click", (e) => { if (e.target === el || e.target.closest("a[href^='#']") || e.target.closest("[data-close]") || e.target.closest(".sheet-actions [data-act]")) setTimeout(closeSheet, 0); });
  document.body.append(el);
  requestAnimationFrame(() => el.classList.add("open"));
  document.addEventListener("keydown", sheetKey);
  onBind && onBind(el);
  return el;
}
function sheetKey(e) { if (e.key === "Escape") closeSheet(); }
function closeSheet() { const el = $("#sheet"); if (el) el.remove(); document.removeEventListener("keydown", sheetKey); }
window.addEventListener("hashchange", closeSheet);

function openMoreSheet() {
  const th = S.state?.settings?.theme || "auto";
  openSheet("", `<div class="more-grid">${MORE_ITEMS.map((n) => `<a href="${n.href}" class="more-tile">${icon(n.ic)}<b>${n.t}</b><span>${n.d}</span></a>`).join("")}</div>
    <div class="btn-row" style="margin-top:10px"><a class="btn sm" href="#/lectures">${icon("list")} Усі лекції</a><a class="btn sm" href="#/todo">${icon("check")} Що здати${S.state?.todo_open ? ` (${S.state.todo_open})` : ""}</a></div>
    <div class="more-foot"><button class="btn sm" id="sh-theme">${icon(th === "dark" ? "moon" : "sun")} Тема: ${{ auto: "як у системі", light: "світла", dark: "темна" }[th]}</button>
      ${S.state?.week ? `<span class="small muted">Тиждень ${S.state.week.week} · ${S.state.week.label} · v${S.state.version}</span>` : ""}</div>`, (el) => {
    $("#sh-theme", el).onclick = async () => {
      const next = { auto: "light", light: "dark", dark: "auto" }[th];
      S.state.settings = await PUT("/api/settings", { theme: next }); applyTheme(next); renderNav(); openMoreSheet();
    };
  });
}

function renderNav() {
  const cur = location.hash.split("?")[0] || "#/";
  const isActive = (href) => href === "#/" ? cur === "#/" || cur === "" : cur.startsWith(href) ||
    (href === "#/subjects" && (cur.startsWith("#/subject/") || cur.startsWith("#/lecture")));
  const waiting = claudeWaiting();
  const recOn = typeof REC !== "undefined" && REC.state !== "idle";
  $("#nav").innerHTML = NAV.map((n) => `<a href="${n.href}" class="${isActive(n.href) ? "active" : ""}">${icon(n.ic)}<span>${n.t}</span>${n.badge && waiting ? `<span class="count" title="Чекають на Claude">${waiting}</span>` : ""}${n.badge && S.state?.todo_open ? `<span class="count" style="background:var(--warn-soft);color:var(--warn)" title="Пунктів до здачі">${S.state.todo_open}</span>` : ""}</a>`).join("")
    + `<a href="${recOn ? "#/record" : "#/upload"}" class="nav-add ${isActive("#/upload") || isActive("#/record") ? "active" : ""}">${recOn ? `<span class="rec-dot"></span><span>Іде запис</span>` : `${icon("plus")}<span>Додати / записати</span>`}</a>`
    + `<div class="nav-more-t">Ще</div>` + MORE_ITEMS.map((n) => `<a href="${n.href}" class="small-nav ${isActive(n.href) ? "active" : ""}">${icon(n.ic)}<span>${n.t}</span></a>`).join("");
  // телефон: Сьогодні · Предмети · «+» · Семестр · Ще
  const moreActive = MORE_ITEMS.some((n) => isActive(n.href));
  const tab = (href, ic, label, extra = "") => `<a href="${href}" class="${isActive(href) ? "active" : ""}">${icon(ic)}<span>${label}</span>${extra}</a>`;
  $("#bottom-nav").innerHTML =
    tab("#/", "home", "Сьогодні", waiting ? `<i class="bn-badge">${waiting}</i>` : "") +
    tab("#/subjects", "book", "Предмети") +
    (recOn  // під час запису кнопка показує запис; інакше «+» — одразу до додавання лекції
      ? `<a href="#/record" class="bn-fab live ${isActive("#/record") ? "active" : ""}" aria-label="Запис"><span class="rec-dot"></span><b id="bn-rec-t">${fmtClock(recElapsed())}</b></a>`
      : `<a href="#/upload" class="bn-fab add ${isActive("#/upload") ? "active" : ""}" aria-label="Додати лекцію">${icon("plus")}</a>`) +
    tab("#/semester", "grad", "Семестр") +
    `<button type="button" class="${moreActive ? "active" : ""}" id="bn-more">${icon("menu")}<span>Ще</span></button>`;
  $("#bn-more").onclick = openMoreSheet;
  const w = S.state?.week;
  const th = S.state?.settings?.theme || "auto";
  $("#sidebar-foot").innerHTML = `
    ${S.state?.beta ? `<div class="badge beta-badge" title="Бета-версія на копії даних: реальні дані не змінюються">БЕТА · копія даних</div>` : ""}
    ${w ? `<div class="badge" title="Тиждень семестру">${icon("calendar")} Тиждень ${w.week} · ${w.label}</div>` : ""}
    <div style="display:flex;align-items:center;justify-content:space-between">
      <span>v${S.state?.version || ""}</span>
      <button class="btn ghost icon" id="theme-btn" title="Тема: ${th}">${icon(th === "dark" ? "moon" : "sun")}</button>
    </div>`;
  $("#theme-btn").onclick = async () => {
    const next = { auto: "light", light: "dark", dark: "auto" }[th];
    S.state.settings = await PUT("/api/settings", { theme: next });
    applyTheme(next); renderNav(); toast(`Тема: ${{ auto: "як у системі", light: "світла", dark: "темна" }[next]}`, "info", 1800);
  };
}

const ROUTES = [
  [/^#?\/?$/, () => viewHome()],
  [/^#\/upload$/, (m, q) => viewUpload(q)],
  [/^#\/record$/, (m, q) => viewRecord(q)],
  [/^#\/lectures$/, (m, q) => viewLectures(q)],
  [/^#\/lecture\/([^/]+)$/, (m, q) => viewLecture(decodeURIComponent(m[1]), q)],
  [/^#\/subjects$/, () => viewSubjects()],
  [/^#\/subject\/([^/]+)$/, (m, q) => viewSubject(decodeURIComponent(m[1]), q)],
  [/^#\/study$/, (m, q) => viewStudy(q)],
  [/^#\/schedule$/, () => viewSchedule()],
  [/^#\/planner$/, (m, q) => viewPlanner(q)],
  [/^#\/todo$/, (m, q) => viewTodo(q)],
  [/^#\/semester$/, () => viewSemester()],
  [/^#\/search$/, (m, q) => viewSearch(q)],
  [/^#\/settings$/, () => viewSettings()],
];

async function route() {
  if (S.dirty && !(await confirmBox("Є незбережені зміни", "Вийти зі сторінки без збереження?", "Вийти", true))) {
    history.replaceState(null, "", S.lastHash || "#/"); return;
  }
  S.dirty = false;
  const [path, qs] = (location.hash || "#/").split("?");
  const q = Object.fromEntries(new URLSearchParams(qs || ""));
  S.lastHash = location.hash;
  S.view = null;
  renderNav();
  const view = $("#view");
  view.innerHTML = `<div class="skeleton" style="height:34px;width:40%;margin-bottom:22px"></div><div class="skeleton" style="height:160px"></div>`;
  for (const [rx, fn] of ROUTES) {
    const m = path.match(rx);
    if (m) {
      try { await fn(m, q); } catch (e) { view.innerHTML = errorBox(e); console.error(e); }
      window.scrollTo({ top: 0 });
      view.classList.add("enter"); setTimeout(() => view.classList.remove("enter"), 300);  // 2.3 (E8): плавна поява лише при переході
      return;
    }
  }
  view.innerHTML = `<div class="empty">${icon("alert")}<b>Сторінку не знайдено</b><a href="#/">На головну</a></div>`;
}
const errorBox = (e) => `<div class="callout err">${icon("alert")}<div class="c-body"><div class="c-title">Не вдалося завантажити</div>${esc(e.message || e)}<div style="margin-top:10px"><button class="btn sm" onclick="route()">${icon("refresh")} Повторити</button></div></div></div>`;
function setView(html, refresh) {
  $("#view").innerHTML = html;
  S.view = { refresh };
}

// живе оновлення: сервер змінює rev, коли щось змінилось на диску (наприклад, Claude поклав PDF)
async function poll() {
  try {
    const r = await GET("/api/rev");
    if (offQ.get().length) flushOfflineAnswers();  // 2.3: зв'язок повернувся — досилаємо відповіді на картки
    if (r.rev !== S.rev) {
      S.rev = r.rev;
      const [st, sc] = await Promise.all([GET("/api/state"), GET("/api/schedule")]);
      const prevDone = S.state?.counts?.done || 0;
      S.state = st; S.schedule = sc; renderNav();
      if (st.counts.done > prevDone) toast(`${icon("sparkles")} Готовий новий конспект!`, "ok", 5000);
      if (S.view?.refresh && !S.dirty && !S.uploading) S.view.refresh();
    }
  } catch { /* offline banner already shown */ }
  setTimeout(poll, document.hidden ? 8000 : 3000);
}

// ============================================================ lecture row
function lectureRow(m) {
  const d = parseDate(m.date);
  const s = m.subject;
  const title = m.display_title || (s ? s.name : "Лекція без предмета");
  const counts = { audio: 0, slides: 0, image: 0 };
  (m.files || []).forEach((f) => (counts[f.kind] = (counts[f.kind] || 0) + 1));
  return `<a class="row" href="#/lecture/${enc(m.id)}">
    <div class="date-box">${d ? `<div class="d">${d.getDate()}</div><div class="m">${MONTHS[d.getMonth()]}</div>` : "—"}</div>
    <div class="body">
      <div class="title">${esc(title)}</div>
      <div class="meta">${subjChip(s)}<span>${esc(typeLabel(m.type))}</span>${m.time ? `<span>${icon("clock")} ${esc(m.time)}</span>` : ""}
        ${counts.audio ? `<span title="Аудіо">${icon("mic")} ${counts.audio}${m.audio_duration ? " · " + fmtDur(m.audio_duration) : ""}</span>` : ""}
        ${counts.slides ? `<span title="Презентації">${icon("slides")} ${counts.slides}</span>` : ""}
        ${counts.image ? `<span title="Фото">${icon("image")} ${counts.image}</span>` : ""}
        <span title="Мова конспекту">${LANG_SHORT[m.notes_language] || ""}</span></div>
    </div>
    <div class="right">${m.output?.pdf ? `<span class="badge" title="Є PDF">${icon("pdf")} PDF</span>` : ""}${statusBadge(m.status, m.status_label)}</div>
  </a>`;
}

const claudeWaiting = () => (S.state?.counts?.waiting_claude || 0) + (S.state?.subjects_waiting || 0) + (S.state?.help_waiting || 0) + (S.state?.explain_waiting || 0) + (S.state?.plans_waiting || 0) + (S.state?.reports_waiting || 0);
function claudeCallout(n) {
  const since = S.state?.waiting_since ? (Date.now() - new Date(S.state.waiting_since).getTime()) / 3600000 : 0;
  const stale = since > 20;
  return `<div class="callout ${stale ? "err" : "warn"}">${icon(stale ? "alert" : "sparkles")}<div class="c-body">
    <div class="c-title">${n} ${n === 1 ? "завдання чекає" : "завдання чекають"} на Claude${stale ? ` уже ${since > 48 ? Math.floor(since / 24) + " дн." : Math.floor(since) + " год"}` : ""}</div>
    <div class="small">${stale ? "Автообробка, схоже, не спрацювала (найчастіше — ПК був вимкнений або спав у час запуску: 13:50 і 20:50). Надішліть у Claude (Cowork) це повідомлення — і заодно попросіть перевірити заплановане завдання." : "Claude обробить чергу автоматично (о 13:50 і 20:50, коли ПК увімкнений). Щоб швидше — надішліть у Claude (Cowork) це повідомлення. PDF з'явиться тут сам."}</div>
    <div class="prompt-box"><code id="claude-prompt">Оброби нові лекції з мого застосунку «Конспект»</code><button class="btn sm" data-copy-prompt>${icon("copy")} Копіювати</button></div>
    ${S.state?.remote_client ? "" : `<div class="btn-row" style="margin-top:8px"><button class="btn sm primary" data-open-claude>${icon("sparkles")} Надіслати в Claude</button><span class="small muted">скопіює повідомлення й відкриє Claude — вставте (Ctrl+V) у чат Cowork, де підключено цей ПК, і натисніть Enter</span></div>`}
  </div></div>`;
}
// 2.2: на головній — один рядок; повний блок лишається, коли черга застрягла (> 20 год)
function claudeLine(n) {
  const since = S.state?.waiting_since ? (Date.now() - new Date(S.state.waiting_since).getTime()) / 3600000 : 0;
  if (since > 20) return claudeCallout(n);
  return `<div class="card claude-line">${icon("sparkles")}<span><b>${n} ${n === 1 ? "завдання чекає" : "завдання чекають"} на Claude</b> <span class="small muted">· сам обробить о 13:50 і 20:50</span></span>
    <code id="claude-prompt" hidden>Оброби нові лекції з мого застосунку «Конспект»</code>
    <span style="flex:1"></span><button class="btn sm ghost" data-copy-prompt title="Копіювати повідомлення для Claude">${icon("copy")}</button>
    ${S.state?.remote_client ? "" : `<button class="btn sm primary" data-open-claude>Надіслати</button>`}</div>`;
}
async function bindCopyPrompt(root = document) {
  const btn = $("[data-copy-prompt]", root); if (!btn) return;
  try { const t = await GET("/api/claude-prompt"); $("#claude-prompt", root).textContent = t; } catch {}
  btn.onclick = () => copyText($("#claude-prompt", root).textContent);
  const op = $("[data-open-claude]", root);
  if (op) op.onclick = async () => {
    await copyText($("#claude-prompt", root).textContent);
    try { await POST("/api/open-claude"); } catch { location.href = "claude://"; }
  };
}

// ============================================================ HOME
async function viewHome() {
  const render = async () => {
    const [items, wk] = await Promise.all([GET("/api/lectures"), GET("/api/week")]);
    const st = S.state, today = st.today;
    const todayCls = (wk.days.find((d) => d.date === today) || { classes: [] }).classes;
    const now = new Date(); const nowM = now.getHours() * 60 + now.getMinutes();
    let upcoming = null;
    if (!todayCls.some((c) => minutes(c.end) > nowM)) {
      for (const d of wk.days) if (d.date > today && d.classes.length) { upcoming = d; break; }
    }
    const hour = now.getHours();
    const greet = hour < 5 ? "Доброї ночі" : hour < 12 ? "Доброго ранку" : hour < 18 ? "Доброго дня" : "Доброго вечора";
    const lecturedToday = new Set(items.filter((m) => m.date === today).map((m) => m.subject_id + m.type));
    const c = st.counts;
    setView(`
      <div class="page-head"><div><h1>${greet}!</h1>
        <div class="sub">Сьогодні ${fmtDate(today, true)} · тиждень ${st.week.week} (${st.week.label})</div></div>
        <div class="btn-row head-actions"><a class="btn lg" href="#/upload">${icon("plus")} Додати файли</a><a class="btn primary lg rec-btn" href="#/record">${icon("mic")} Записати лекцію</a></div></div>
      <div class="hero">
        <div class="card pad">
          <div class="section-head"><h2>Сьогодні</h2><a class="small" href="#/schedule">Розклад →</a></div>
          <div class="today-list">${(() => {
            const card = (cl, dateFor, isToday) => {
              const isNow = isToday && minutes(cl.start) - 10 <= nowM && nowM <= minutes(cl.end);
              const past = isToday && minutes(cl.end) < nowM;
              const has = isToday && lecturedToday.has(cl.subject_id + cl.type);
              const canAdd = isToday && minutes(cl.start) - 15 <= nowM;
              return `<div class="class-card ${isNow ? "now" : ""} ${past && has ? "past" : ""}" style="--c:${cl.subject.color}">
                <div class="bar"></div><div class="time">${cl.start}–${cl.end}</div>
                <div class="info">${isNow ? `<div class="now-tag">Зараз</div>` : ""}<div class="name">${esc(cl.subject.name)}</div>
                  <div class="sub">${esc(typeLabel(cl.type))} · ${esc(cl.room)}${cl.parity !== "all" ? " · " + PARITY[cl.parity].toLowerCase() : ""}</div></div>
                ${has ? `<span class="badge s-done">${icon("check")} додано</span>` :
                  isNow ? `<a class="btn sm primary" href="#/record?subject=${enc(cl.subject_id)}&type=${cl.type}">${icon("mic")} Записати</a>` :
                  canAdd ? `<a class="btn sm" href="#/upload?subject=${enc(cl.subject_id)}&date=${dateFor}&time=${cl.start}&type=${cl.type}">${icon("upload")} Додати запис</a>` : ""}
              </div>`;
            };
            let html = todayCls.length ? todayCls.map((cl) => card(cl, today, true)).join("") :
              `<div class="empty" style="padding:18px">${icon("calendar")}<b>Сьогодні занять немає</b></div>`;
            if (upcoming) html += `<div class="label-t" style="margin:10px 0 2px">Далі · ${fmtDate(upcoming.date, true)}</div>` + upcoming.classes.map((cl) => card(cl, upcoming.date, false)).join("");
            return html;
          })()}</div>
        </div>
        <div class="card pad" id="dl-card"><h2>${icon("clock")} Дедлайни</h2><div class="small muted"><span class="spinner"></span></div></div>
      </div>
      ${claudeWaiting() ? `<div class="section">${claudeLine(claudeWaiting())}</div>` : ""}
      ${st.total ? "" : `<div class="section"><div class="card pad">
          <h2>Як це працює</h2>
          <ol class="small" style="margin:0;padding-left:18px;color:var(--text-2);display:flex;flex-direction:column;gap:8px">
            <li><b>Запишіть лекцію</b> кнопкою «Записати лекцію» (на телефоні через Tailscale) — або на диктофон і перетягніть файл сюди.</li>
            <li><b>Перетягніть файли</b> сюди: аудіо, презентацію, фото дошки. Предмет підбереться за розкладом.</li>
            <li>${S.state.whisper.available ? "Аудіо <b>розшифрується локально</b> (безкоштовно, на вашому ПК)." : "За бажанням увімкніть <b>локальну розшифровку</b> в налаштуваннях — це пришвидшить роботу."}</li>
            <li><b>Напишіть Claude</b> «Оброби нові лекції» — PDF-конспект з'явиться тут автоматично.</li>
          </ol>
        </div></div>`}
      <div class="section">
        <div class="section-head"><h2>Останні лекції</h2>${items.length ? `<a class="small" href="#/lectures">Усі →</a>` : ""}</div>
        <div class="card list">${items.length ? items.slice(0, 7).map(lectureRow).join("") :
          `<div class="empty">${icon("mic")}<b>Ще немає жодної лекції</b>Перетягніть аудіо в будь-яке місце вікна або натисніть «Додати лекцію».</div>`}</div>
      </div>`, render);
    bindCopyPrompt();
    loadDeadlines($("#dl-card"));
  };
  await render();
}

// ============================================================ LECTURES LIST
async function viewLectures(q) {
  const f = { subject: q.subject || "", status: q.status || "", text: "" };
  const render = async () => {
    const items = await GET("/api/lectures");
    const draw = () => {
      let list = items;
      if (f.subject === "__none") list = list.filter((m) => !m.subject);
      else if (f.subject) list = list.filter((m) => m.subject_id === f.subject);
      if (f.status) list = list.filter((m) => m.status === f.status);
      if (f.text) { const t = f.text.toLowerCase(); list = list.filter((m) => `${m.display_title} ${m.subject?.name} ${m.date} ${m.user_notes}`.toLowerCase().includes(t)); }
      $("#lec-list").innerHTML = list.length ? list.map(lectureRow).join("") : `<div class="empty">${icon("search")}<b>Нічого не знайдено</b>Змініть фільтри.</div>`;
      $("#lec-count").textContent = `${list.length} з ${items.length}`;
    };
    setView(`
      <div class="page-head"><div><h1>Усі лекції</h1><div class="sub" id="lec-count"></div></div>
        <a class="btn primary" href="#/upload">${icon("plus")} Додати</a></div>
      <div class="btn-row" style="margin-bottom:14px">
        <input class="input" id="f-text" placeholder="Фільтр за назвою…" style="max-width:260px" value="${esc(f.text)}">
        <select class="input" id="f-subj" style="max-width:280px"><option value="">Усі предмети</option>${S.schedule.subjects.map((s) => `<option value="${s.id}" ${f.subject === s.id ? "selected" : ""}>${esc(s.name)}</option>`).join("")}<option value="__none" ${f.subject === "__none" ? "selected" : ""}>Без предмета</option></select>
        <div class="seg" id="f-status">${[["", "Усі"], ["done", "Готові"], ["waiting_claude", "Чекають"], ["transcribing", "Розшифровка"], ["draft", "Чернетки"], ["error", "Помилки"]].map(([v, t]) => `<button data-v="${v}" class="${f.status === v ? "on" : ""}">${t}</button>`).join("")}</div>
      </div>
      <div class="card list" id="lec-list"></div>`, render);
    $("#f-text").oninput = debounce((e) => { f.text = e.target.value; draw(); }, 150);
    $("#f-subj").onchange = (e) => { f.subject = e.target.value; draw(); };
    $$("#f-status button").forEach((b) => (b.onclick = () => { f.status = b.dataset.v; $$("#f-status button").forEach((x) => x.classList.toggle("on", x === b)); draw(); }));
    draw();
  };
  await render();
}

// ============================================================ SUBJECTS
async function viewSubjects() {
  const render = async () => {
    const [items, wk] = await Promise.all([GET("/api/lectures"), GET("/api/week")]);
    const subs = S.schedule.subjects;
    const next = (sid) => { for (const d of wk.days) for (const c of d.classes) if (c.subject_id === sid && (d.date > S.state.today || (d.date === S.state.today))) return `${DAYS_SHORT[(parseDate(d.date).getDay() + 6) % 7]} ${c.start}`; return "—"; };
    const noSubj = items.filter((m) => !m.subject).length;
    setView(`
      <div class="page-head"><div><h1>Предмети</h1><div class="sub">${subs.length} предметів у розкладі</div></div>
        <a class="btn" href="#/schedule">${icon("edit")} Редагувати</a></div>
      <div class="grid cols-3">${subs.map((s) => {
        const ls = items.filter((m) => m.subject_id === s.id);
        return `<a class="card subj-card" href="#/subject/${enc(s.id)}" style="--c:${s.color}"><div class="top"></div><div class="in">
          <div class="short">${esc(s.short)}</div><div class="nm">${esc(s.name)}</div>
          <div class="nums"><div><b>${ls.length}</b>лекцій</div><div><b>${ls.filter((m) => m.status === "done").length}</b>конспектів</div><div><b>${next(s.id)}</b>цього тижня</div></div>
        </div></a>`;
      }).join("")}
      ${noSubj ? `<a class="card subj-card" href="#/lectures?subject=__none" style="--c:#94a3b8"><div class="top"></div><div class="in"><div class="nm">Без предмета</div><div class="small muted">Лекції, для яких предмет не вибрано</div><div class="nums"><div><b>${noSubj}</b>лекцій</div></div></div></a>` : ""}
      </div>`, render);
  };
  await render();
}

const TYPE_TABS = { W: ["Виклади", "book"], L: ["Лаби", "cpu"], P: ["Проєкт", "archive"], C: ["Вправи", "edit"], S: ["Семінари", "list"] };
async function viewSubject(sid, q = {}) {
  let tab = q.tab || "";
  let editingPlan = false;
  const render = async () => {
    S.onGlobalDrop = null;
    const s = subjById(sid);
    if (!s) { setView(`<div class="empty">${icon("alert")}<b>Предмет не знайдено</b><a href="#/subjects">До предметів</a></div>`); return; }
    const [items, mat, crs] = await Promise.all([GET(`/api/lectures?subject=${enc(sid)}`), GET(`/api/subjects/${enc(sid)}/materials`), GET(`/api/subjects/${enc(sid)}/course`).catch(() => ({ memory: {}, map: { items: [] } }))]);
    const sem = (await GET("/api/semester").catch(() => [])).find((x) => x.subject_id === sid);  // 2.3: «Готуюсь до тесту»
    const proj = await GET(`/api/subjects/${enc(sid)}/project`).catch(() => ({ exists: false }));  // 2.4
    const pchat = proj.exists && (tab === "project") ? await GET(`/api/chat/project/${enc(sid)}`).catch(() => ({})) : null;  // 2.7
    const cls = S.schedule.classes.filter((c) => c.subject_id === sid).sort((a, b) => a.day - b.day || minutes(a.start) - minutes(b.start));
    const done = items.filter((m) => m.output?.pdf).length;

    const types = Object.keys(TYPE_TABS).filter((t) => cls.some((c) => c.type === t) || items.some((m) => m.type === t));
    if (!types.length) types.push("W");
    // 2.7: три вкладки — Заняття (усі типи в одній стрічці), Проєкт, Матеріали (з картою курсу й планом тем)
    let typ = q.type || "";
    if (tab.startsWith("t-")) { typ = q.type = tab.slice(2); tab = "lessons"; }
    if (tab === "map" || tab === "plan") { q.open = tab; tab = "materials"; }
    if (!tab || tab === "lectures" || (tab === "project" && !proj.exists)) tab = "lessons";
    const lecturesTab = () => {
      const list = items.filter((m) => !typ || (m.type || "W") === typ);
      const byMonth = {};
      const filt = types.length > 1 ? `<div class="seg" id="sj-types" style="margin-top:4px"><button class="${typ ? "" : "on"}" data-typ="">Усі</button>${types.map((t) => `<button class="${typ === t ? "on" : ""}" data-typ="${t}">${TYPE_TABS[t][0]} <span class="muted">${items.filter((m) => (m.type || "W") === t).length}</span></button>`).join("")}</div>` : "";
      list.forEach((m) => { const k = (m.date || "").slice(0, 7); (byMonth[k] = byMonth[k] || []).push(m); });
      return filt + (list.length ? Object.entries(byMonth).map(([k, ls]) => {
        const [y, mo] = k.split("-").map(Number);
        return `<div style="margin-top:14px"><h3 class="muted">${["Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень", "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"][mo - 1] || ""} ${y || ""}</h3><div class="card list">${ls.map(lectureRow).join("")}</div></div>`;
      }).join("") : `<div class="card" style="margin-top:14px"><div class="empty">${icon("mic")}<b>Ще немає занять${typ ? " цього типу" : ""}</b><a class="btn sm" href="#/upload?subject=${enc(sid)}${typ ? `&type=${typ}` : ""}">${icon("plus")} Додати</a></div></div>`);
    };

    const planTab = () => {
      const pending = mat.parse_pending ? `<div class="callout warn" style="margin-bottom:12px">${icon("sparkles")}<div class="c-body"><div class="c-title">Claude розпізнає план із матеріалів</div>Запит у черзі з ${new Date(mat.parse_requested_at).toLocaleString("uk-UA")}. <button class="btn sm ghost" id="pl-cancel">Скасувати</button></div></div>` : "";
      if (editingPlan) {
        const rows = (mat.plan.length ? mat.plan : [{ date: "", title: "", topics: [] }]);
        return `${pending}<div class="card pad"><div class="table-wrap"><table class="tbl" id="pl-table"><thead><tr><th style="width:150px">Дата</th><th>Тема</th><th style="width:40%">Підтеми (кожна з нового рядка)</th><th></th></tr></thead><tbody>
          ${rows.map((it) => `<tr><td><input class="input" type="date" data-k="date" value="${esc(it.date)}"></td><td><input class="input" data-k="title" value="${esc(it.title)}"></td><td><textarea class="input" data-k="topics" style="min-height:60px">${esc((it.topics || []).join("\n"))}</textarea></td><td><button class="btn ghost icon sm danger" data-rmrow>${icon("trash")}</button></td></tr>`).join("")}
          </tbody></table></div>
          <div class="btn-row" style="margin-top:10px"><button class="btn sm" id="pl-add">${icon("plus")} Рядок</button><span style="flex:1"></span><button class="btn ghost" id="pl-cancel-edit">Скасувати</button><button class="btn primary" id="pl-save">${icon("check")} Зберегти план</button></div></div>`;
      }
      const lecByDate = {}; items.forEach((m) => (lecByDate[m.date] = lecByDate[m.date] || m));
      const today = S.state.today;
      return `${pending}<div class="btn-row" style="margin-bottom:12px"><button class="btn" id="pl-edit">${icon("edit")} ${mat.plan.length ? "Редагувати план" : "Ввести план вручну"}</button>
          <button class="btn" id="pl-parse" ${mat.parse_pending ? "disabled" : ""}>${icon("sparkles")} Розпізнати план з матеріалів (Claude)</button>
          ${mat.plan_updated_at ? `<span class="small muted">Оновлено ${relTime(mat.plan_updated_at)}${mat.plan_source === "claude" ? " · Claude" : ""}</span>` : ""}</div>
        ${mat.plan.length ? `<div class="card list">${mat.plan.map((it) => {
          const lec = lecByDate[it.date];
          const past = it.date && it.date <= today;
          return `<div class="row" style="align-items:flex-start"><div class="date-box">${it.date ? `<div class="d">${parseDate(it.date).getDate()}</div><div class="m">${MONTHS[parseDate(it.date).getMonth()]}</div>` : "—"}</div>
            <div class="body"><div class="title" style="white-space:normal">${esc(it.title)}</div>
              ${it.topics?.length ? `<ul class="small" style="margin:4px 0 0;padding-left:18px;color:var(--text-2)">${it.topics.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : ""}
              ${(it.links || []).map((l) => `<div class="small"><a href="${esc(l.url)}" target="_blank">${icon("external")} ${esc(l.title || l.url)}</a></div>`).join("")}</div>
            <div class="right">${lec ? `<a class="btn sm" href="#/lecture/${enc(lec.id)}">${statusBadge(lec.status, lec.status_label)}</a>` :
              past ? `<a class="btn sm" href="#/upload?subject=${enc(sid)}&date=${it.date}">${icon("plus")} Додати</a>` : `<span class="small muted">попереду</span>`}</div></div>`;
        }).join("")}</div>` : `<div class="card"><div class="empty">${icon("list")}<b>Плану тем ще немає</b>Завантажте у «Матеріали» скріншот або PDF із ePortalu / силабус і натисніть «Розпізнати план» — або введіть план вручну. Тоді тема кожної лекції підставлятиметься автоматично.</div></div>`}`;
    };

    const materialsTab = () => `
      <details class="lsec" ${q.open === "plan" ? "open" : ""}><summary>${icon("calendar")} <b>План тем</b>${mat.plan.length ? `<span class="cnt">${mat.plan.length}</span>` : ""}</summary><div id="sj-plan">${planTab()}</div></details>
      <details class="lsec" ${q.open === "map" ? "open" : ""}><summary>${icon("map")} <b>Карта курсу</b>${crs.map.items.length ? `<span class="cnt">${crs.map.items.length}</span>` : ""}</summary><div>${courseMapHtml(sid, crs, items)}</div></details>
      <div class="grid cols-2" style="margin-top:14px">
        <div class="card pad" id="dl-subj" style="grid-column:1/-1"></div>
        <div class="card pad"><h2>${icon("edit")} Нотатки до предмета</h2>
          <textarea class="input" id="mt-notes" style="min-height:180px" placeholder="Умови заліку, дати колоквіумів, вимоги викладача, контакти…">${esc(mat.notes)}</textarea>
          <div class="btn-row" style="margin-top:10px"><button class="btn primary sm" id="mt-save">${icon("check")} Зберегти</button><span class="small muted" id="mt-st">Claude враховує ці нотатки в кожному конспекті</span></div></div>
        <div class="card pad"><h2>${icon("external")} Посилання</h2>
          <div class="list" id="mt-links">${mat.links.map((l, i) => `<div class="row" style="padding:8px 2px"><div class="body"><a class="title" href="${esc(l.url)}" target="_blank" style="display:block">${esc(l.title || l.url)}</a><div class="meta">${esc(l.url)}</div></div><button class="btn ghost icon sm danger" data-rmlink="${i}">${icon("trash")}</button></div>`).join("") || '<div class="small muted">Ще немає</div>'}</div>
          <div class="btn-row" style="margin-top:10px"><input class="input" id="ln-title" placeholder="Назва (напр. Специфікація OpenGL 2.0)" style="flex:1;min-width:140px"><input class="input" id="ln-url" placeholder="https://…" style="flex:1;min-width:140px"><button class="btn sm" id="ln-add">${icon("plus")} Додати</button></div></div>
        <div class="card pad" style="grid-column:1/-1"><h2>${icon("folder")} Файли предмета</h2>
          <p class="small muted" style="margin-top:0">Силабус, скріншоти плану з ePortalu, умови заліку, збірники задач. Claude використовує їх для всіх лекцій цього предмета.</p>
          ${mat.files.length ? `<div class="list" style="margin-bottom:12px">${mat.files.map((f) => `<div class="row" style="padding:8px 2px"><div class="ico ${kindOf(f.name)}" style="width:32px;height:32px;border-radius:9px;display:grid;place-items:center;background:var(--bg-soft)">${icon(KIND_ICON[kindOf(f.name)])}</div><div class="body"><div class="title">${esc(f.name)}</div><div class="meta">${fmtSize(f.size)} · ${relTime(f.added_at)}</div></div><a class="btn sm" target="_blank" href="/api/subjects/${enc(sid)}/files/${enc(f.name)}">${icon("external")}</a><button class="btn ghost icon sm danger" data-rmfile="${esc(f.name)}">${icon("trash")}</button></div>`).join("")}</div>` : ""}
          <div class="dropzone" id="mt-dz" style="padding:22px"><div class="t">${icon("upload")} Перетягніть файли або натисніть</div><div class="s" id="mt-prog">PDF, DOCX, JPG/PNG…</div><input type="file" id="mt-in" multiple hidden></div></div>
      </div>`;

    setView(`
      <a class="small muted" href="#/subjects" style="display:inline-flex;align-items:center;gap:4px">${icon("left")} Предмети</a>
      <div class="page-head" style="margin-top:8px"><div><div style="margin-bottom:6px">${subjChip(s)}</div><h1>${esc(s.name)}</h1>
        <div class="sub">${items.length} лекцій · ${done} конспектів</div></div>
        <div class="btn-row">
          ${examPrepHtml(sid, sem)}
          ${done ? `<a class="btn" href="/api/subjects/${enc(sid)}/script.pdf" id="dl-script">${icon("download")} Скрипт PDF</a>` : ""}
          <a class="btn primary" href="#/upload?subject=${enc(sid)}">${icon("plus")} Додати лекцію</a></div></div>
      <div class="chips" style="margin-bottom:14px">${cls.map((c) => `<span class="badge">${DAYS_SHORT[c.day]} ${c.start}–${c.end} · ${c.type} · ${esc(c.room)}${c.parity !== "all" ? " · " + PARITY[c.parity].toLowerCase() : ""}</span>`).join("")}</div>
      <div class="tabs" id="sj-tabs">${[["lessons", "list", "Заняття", items.length], ...(proj.exists ? [["project", "grad", "Проєкт", 0]] : []), ["materials", "folder", "Матеріали", mat.files.length + mat.links.length]].map(([k, ic, t, c]) => `<button data-tab="${k}" class="${tab === k ? "on" : ""}">${icon(ic)} ${t}${c ? `<span class="cnt">${c}</span>` : ""}</button>`).join("")}</div>
      <div id="sj-body">${tab === "project" ? projectHtml(sid, proj, pchat) : tab === "materials" ? materialsTab() : lecturesTab()}</div>`, render);

    bindExamPrep(render);
    if (tab === "project") { bindProject(sid, render); bindChat(render); }
    $$("#sj-tabs [data-tab]").forEach((b) => (b.onclick = () => { tab = b.dataset.tab; editingPlan = false; S.dirty = false; history.replaceState(null, "", `#/subject/${enc(sid)}?tab=${tab}`); render(); }));
    $$("#sj-types [data-typ]").forEach((b) => (b.onclick = () => { typ = q.type = b.dataset.typ; history.replaceState(null, "", `#/subject/${enc(sid)}?tab=lessons${typ ? "&type=" + typ : ""}`); render(); }));
    // script download with error handling
    $("#dl-script") && ($("#dl-script").onclick = async (e) => {
      e.preventDefault(); const btn = e.currentTarget; btn.innerHTML = '<span class="spinner"></span> Збираю…';
      try {
        const r = await fetch(`/api/subjects/${enc(sid)}/script.pdf`);
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Помилка ${r.status}`);
        const blob = await r.blob(); const a = document.createElement("a");
        a.href = URL.createObjectURL(blob); a.download = `${s.short || sid} - skrypt.pdf`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
      } catch (er) { handleErr(er); }
      btn.innerHTML = `${icon("download")} Скрипт PDF`;
    });
    // plan
    $("#pl-edit") && ($("#pl-edit").onclick = () => { editingPlan = true; q.open = "plan"; S.dirty = true; $("#sj-plan").innerHTML = planTab(); bindPlan(); });
    $("#pl-parse") && ($("#pl-parse").onclick = async () => {
      if (!mat.files.length && !mat.links.length) { toast("Спочатку додайте нижче скріншот/PDF плану або посилання", "info", 5000); return; }
      const r = await modal({ title: "Розпізнати план тем", okText: "У чергу", body: `<p class="small muted">Claude прочитає файли й посилання предмета та складе план: дата → тема → підтеми.</p><div class="field"><label>Побажання (необов'язково)</label><textarea class="input" name="instructions" placeholder="Напр.: план на сторінці 2 силабусу"></textarea></div>` });
      if (!r) return;
      try { await POST(`/api/subjects/${enc(sid)}/parse`, { instructions: r.instructions }); toast("Запит додано в чергу Claude"); render(); } catch (e) { handleErr(e); }
    });
    $("#pl-cancel") && ($("#pl-cancel").onclick = async () => { await DEL(`/api/subjects/${enc(sid)}/parse`); render(); });
    const bindPlan = () => {
      $("#pl-add") && ($("#pl-add").onclick = () => { $("#pl-table tbody").insertAdjacentHTML("beforeend", `<tr><td><input class="input" type="date" data-k="date"></td><td><input class="input" data-k="title"></td><td><textarea class="input" data-k="topics" style="min-height:60px"></textarea></td><td><button class="btn ghost icon sm danger" data-rmrow>${icon("trash")}</button></td></tr>`); bindPlan(); });
      $$("[data-rmrow]").forEach((b) => (b.onclick = () => b.closest("tr").remove()));
      $("#pl-cancel-edit") && ($("#pl-cancel-edit").onclick = () => { editingPlan = false; S.dirty = false; render(); });
      $("#pl-save") && ($("#pl-save").onclick = async () => {
        const itemsP = $$("#pl-table tbody tr").map((tr) => ({ date: $("[data-k=date]", tr).value, title: $("[data-k=title]", tr).value, topics: $("[data-k=topics]", tr).value }));
        try { await PUT(`/api/subjects/${enc(sid)}/plan`, { items: itemsP }); editingPlan = false; S.dirty = false; toast("План збережено"); render(); } catch (e) { handleErr(e); }
      });
    };
    bindPlan();
    // materials
    if ($("#mt-save")) {
      loadDeadlines($("#dl-subj"), sid);
      $("#mt-notes").oninput = () => { S.dirty = true; $("#mt-st").textContent = "Є незбережені зміни"; };
      $("#mt-save").onclick = async () => { try { await PUT(`/api/subjects/${enc(sid)}/materials`, { notes: $("#mt-notes").value }); S.dirty = false; toast("Збережено"); $("#mt-st").textContent = "Збережено ✓"; } catch (e) { handleErr(e); } };
      $("#ln-add").onclick = async () => {
        const url = $("#ln-url").value.trim(); if (!url) return toast("Вкажіть адресу посилання", "err");
        try { await PUT(`/api/subjects/${enc(sid)}/materials`, { links: [...mat.links, { title: $("#ln-title").value, url }] }); render(); } catch (e) { handleErr(e); }
      };
      $$("[data-rmlink]").forEach((b) => (b.onclick = async () => { const ls = mat.links.filter((_, i) => i !== +b.dataset.rmlink); await PUT(`/api/subjects/${enc(sid)}/materials`, { links: ls }).catch(handleErr); render(); }));
      $$("[data-rmfile]").forEach((b) => (b.onclick = async () => {
        if (!(await confirmBox("Видалити файл?", `«${esc(b.dataset.rmfile)}» буде переміщено в кошик.`, "Видалити", true))) return;
        await DEL(`/api/subjects/${enc(sid)}/files/${enc(b.dataset.rmfile)}`).catch(handleErr); render();
      }));
      const dz = $("#mt-dz"), fi = $("#mt-in");
      const up = async (files) => {
        let i = 0;
        for (const f of files) {
          i++; $("#mt-prog").textContent = `Завантаження ${i}/${files.length}: ${f.name}`;
          const fd = new FormData(); fd.append("file", f, f.name);
          try { await api(`/api/subjects/${enc(sid)}/files`, { method: "POST", body: fd }); } catch (e) { handleErr(e); }
        }
        toast("Файли додано"); render();
      };
      dz.onclick = () => fi.click(); fi.onchange = () => up([...fi.files]);
      dz.ondragover = (e) => { e.preventDefault(); dz.classList.add("over"); };
      dz.ondragleave = () => dz.classList.remove("over");
      dz.ondrop = (e) => { e.preventDefault(); e.stopPropagation(); dz.classList.remove("over"); hideOverlay(); up([...e.dataTransfer.files]); };
      S.onGlobalDrop = (files) => up([...files]);
    }
  };
  await render();
}

// ============================================================ STUDY — див. study.js

// ============================================================ UPLOAD
const pendingDrop = { files: null };

function readDuration(file) {
  return new Promise((resolve) => {
    if (!/^(audio|video)\//.test(file.type) && !/\.(m4a|mp3|wav|ogg|opus|aac|flac|webm|mp4|mov|3gp|amr|wma)$/i.test(file.name)) return resolve(null);
    const url = URL.createObjectURL(file);
    const a = document.createElement("audio");
    let done = false;
    const fin = (v) => { if (done) return; done = true; URL.revokeObjectURL(url); resolve(v && isFinite(v) ? v : null); };
    a.preload = "metadata";
    a.onloadedmetadata = () => fin(a.duration);
    a.onerror = () => fin(null);
    setTimeout(() => fin(null), 6000);
    a.src = url;
  });
}
const kindOf = (name) => {
  const e = (name.split(".").pop() || "").toLowerCase();
  if (["mp4", "mkv", "mov", "avi", "m4v", "wmv", "flv", "mpg", "mpeg", "ts", "mts", "m2ts"].includes(e)) return "video";
  if (["mp3", "m4a", "wav", "ogg", "oga", "opus", "aac", "flac", "wma", "amr", "3gp", "webm", "mp4", "mkv", "mov", "m4b", "caf", "aiff", "aif"].includes(e)) return "audio";
  if (["pdf", "ppt", "pptx", "odp", "key", "doc", "docx", "odt", "txt", "md", "rtf"].includes(e)) return "slides";
  if (["jpg", "jpeg", "png", "heic", "heif", "webp", "gif", "bmp", "tif", "tiff"].includes(e)) return "image";
  return "other";
};
const KIND_ICON = { audio: "mic", video: "video", slides: "slides", image: "image", other: "file" };
const KIND_LABEL = { audio: "Аудіо", video: "Відео → аудіо + ключові кадри", slides: "Презентація / документ", image: "Фото", other: "Інший файл" };

function uploadOne(lid, item, onProgress) {
  return new Promise((resolve, reject) => {
    const fd = new FormData();
    fd.append("file", item.file, item.file.name);
    if (item.duration) fd.append("duration", String(item.duration));
    const x = new XMLHttpRequest();
    x.open("POST", `/api/lectures/${enc(lid)}/files`);
    x.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    x.onload = () => {
      let data = {}; try { data = JSON.parse(x.responseText); } catch {}
      x.status < 300 ? resolve(data) : reject(new Error(data.detail || `Помилка ${x.status}`));
    };
    x.onerror = () => reject(new Error("Зв'язок перервано. Перевірте, чи працює сервер."));
    x.send(fd);
  });
}

async function viewUpload(q) {
  const st = S.state.settings;
  const U = {
    files: [], subject: q.subject || "", type: q.type || "W", date: q.date || S.state.today, time: q.time || "",
    title: "", audio_language: st.default_audio_language, notes_language: st.default_notes_language,
    user_notes: "", instructions: "", transcribe: st.auto_transcribe && S.state.whisper.available,
    claude: st.auto_request_claude, candidates: [], source: q.subject ? "manual" : null, existing: null, attachTo: q.lecture || "",
  };
  const allLectures = await GET("/api/lectures");
  if (U.attachTo) {
    const ex = allLectures.find((m) => m.id === U.attachTo);
    if (ex) Object.assign(U, { subject: ex.subject_id, date: ex.date, time: ex.time, type: ex.type });
  }

  const subjOptions = () => `<option value="">— Не вибрано —</option>` + S.schedule.subjects.map((s) => `<option value="${s.id}" ${U.subject === s.id ? "selected" : ""}>${esc(s.name)}</option>`).join("");
  setView(`
    <div class="page-head"><div><h1>${U.attachTo ? "Додати файли до лекції" : "Додати лекцію"}</h1><div class="sub">Аудіо, презентації, фото дошки — усе разом або частинами</div></div></div>
    <div class="upload-layout">
      <div>
        <div class="dropzone" id="dz"><div class="big">${icon("upload")}</div>
          <div class="t">Перетягніть файли сюди або натисніть, щоб вибрати</div>
          <div class="s">MP3, M4A, WAV… · відео MP4, MKV, MOV (записи Teams / Meet / Zoom) · PDF, PPTX · JPG, PNG, HEIC · будь-який розмір · скріншоти — <b>Ctrl+V</b></div>
          <input type="file" id="file-in" multiple hidden></div>
        <div class="file-list" id="files"></div>
        <div class="card pad section" id="meta-card">
          <div class="section-head"><h2>Про лекцію</h2><span class="small muted" id="det-src"></span></div>
          <div id="cands" class="chips" style="margin-bottom:14px"></div>
          <div class="form-grid">
            <div class="field full"><label>Предмет</label><select class="input" id="u-subj">${subjOptions()}</select></div>
            <div class="field"><label>Дата</label><input class="input" type="date" id="u-date" value="${esc(U.date)}"></div>
            <div class="field"><label>Час початку</label><input class="input" type="time" id="u-time" value="${esc(U.time)}"></div>
            <div class="field"><label>Тип заняття</label><select class="input" id="u-type">${Object.entries(S.state.types).map(([k, v]) => `<option value="${k}" ${U.type === k ? "selected" : ""}>${v}</option>`).join("")}</select></div>
            <div class="field"><label>Тема (необов'язково)</label><input class="input" id="u-title" placeholder="Claude визначить сам" maxlength="300"></div>
            <div class="field"><label>Мова лекції (аудіо)</label><div class="seg" id="u-alang">${["pl", "uk", "ru", "en"].map((l) => `<button data-v="${l}" class="${U.audio_language === l ? "on" : ""}">${LANG_SHORT[l]}</button>`).join("")}</div></div>
            <div class="field"><label>Мова конспекту (PDF)</label><div class="seg" id="u-nlang">${["pl", "uk", "ru"].map((l) => `<button data-v="${l}" class="${U.notes_language === l ? "on" : ""}">${S.state.langs[l]}</button>`).join("")}</div></div>
            <div class="field full"><label>Мої нотатки</label><textarea class="input" id="u-notes" placeholder="Напр.: викладач сказав, що тема 3 буде на колоквіумі"></textarea></div>
            <div class="field full"><label>Побажання до конспекту для Claude</label><textarea class="input" id="u-instr" style="min-height:60px" placeholder="Напр.: більше прикладів, додай таблицю порівняння протоколів"></textarea></div>
          </div>
        </div>
        <div id="existing" style="margin-top:14px"></div>
      </div>
      <div class="sticky">
        <div class="card pad">
          <h2>Обробка</h2>
          <div style="display:flex;flex-direction:column;gap:8px">
            <label class="check ${S.state.whisper.available ? "" : "disabled"}"><input type="checkbox" id="u-tr" ${U.transcribe ? "checked" : ""} ${S.state.whisper.available ? "" : "disabled"}>
              <div><b>Розшифрувати на цьому ПК</b><span>${S.state.whisper.available ? `Безкоштовно, Whisper${S.state.whisper.cuda ? " на відеокарті" : " на процесорі"}` : `Не встановлено — <a href="#/settings">увімкнути</a>. Без цього розшифрує Claude.`}</span></div></label>
            <label class="check"><input type="checkbox" id="u-cl" ${U.claude ? "checked" : ""}>
              <div><b>Передати Claude на конспект</b><span>Лекція стане в чергу «Чекає на Claude»</span></div></label>
          </div>
          <div id="summary" class="small muted" style="margin:14px 0"></div>
          <div id="up-progress" class="hidden" style="margin-bottom:12px"><div class="small" id="up-label"></div><div class="progress"><i id="up-bar"></i></div></div>
          <button class="btn primary lg" id="u-go" style="width:100%">${icon("upload")} Зберегти лекцію</button>
        </div>
      </div>
    </div>`);

  const sync = () => {
    const n = U.files.length, sz = U.files.reduce((a, f) => a + f.file.size, 0);
    const dur = U.files.reduce((a, f) => a + (f.duration || 0), 0);
    $("#summary").innerHTML = n ? `${n} ${n === 1 ? "файл" : "файлів"} · ${fmtSize(sz)}${dur ? " · " + fmtDur(dur) + " аудіо" : ""}` : "Додайте хоча б один файл (або збережіть порожню лекцію й додайте файли пізніше).";
    S.dirty = n > 0 && !S.uploading;
    // така сама лекція вже існує?
    const ex = U.subject && allLectures.find((m) => m.subject_id === U.subject && m.date === U.date && m.type === U.type && m.id !== U.attachTo);
    const exBox = $("#existing");
    if (U.attachTo) {
      const t = allLectures.find((m) => m.id === U.attachTo);
      exBox.innerHTML = `<div class="callout info">${icon("info")}<div class="c-body"><div class="c-title">Файли буде додано до наявної лекції</div>${esc(t?.display_title || t?.subject?.name || "")} · ${fmtDate(t?.date)}<div style="margin-top:8px"><button class="btn sm" id="ex-new">Створити окрему лекцію</button></div></div></div>`;
      $("#ex-new").onclick = () => { U.attachTo = ""; sync(); };
    } else if (ex) {
      exBox.innerHTML = `<div class="callout info">${icon("info")}<div class="c-body"><div class="c-title">Лекція з цього предмета за ${fmtDate(U.date)} уже є</div>Можливо, ви досилаєте презентацію чи другу частину запису?<div class="btn-row" style="margin-top:8px"><button class="btn sm primary" id="ex-attach">Додати до неї</button><a class="btn sm" href="#/lecture/${enc(ex.id)}">Відкрити</a></div></div></div>`;
      $("#ex-attach").onclick = () => { U.attachTo = ex.id; sync(); };
    } else exBox.innerHTML = "";
    $("#u-go").innerHTML = `${icon("upload")} ${U.attachTo ? "Додати файли" : "Зберегти лекцію"}`;
    if (U.subject && U.date) {
      const key = U.subject + U.date;
      if (U.planKey !== key) {
        U.planKey = key;
        GET(`/api/subjects/${enc(U.subject)}/materials`).then((mt) => {
          const it = mt.plan.find((x) => x.date === U.date);
          $("#u-title").placeholder = it ? `За планом: ${it.title}` : "Claude визначить сам";
        }).catch(() => {});
      }
    }
  };

  const drawFiles = () => {
    $("#files").innerHTML = U.files.map((f, i) => `<div class="file-item" data-i="${i}">
      <div class="ico ${f.kind}">${icon(KIND_ICON[f.kind])}</div>
      <div class="fn"><b>${esc(f.file.name)}</b><span>${KIND_LABEL[f.kind]} · ${fmtSize(f.file.size)}${f.duration ? " · " + fmtDur(f.duration) : ""}${f.status ? " · " + f.status : ""}</span>
        ${f.progress != null ? `<div class="progress"><i style="width:${Math.round(f.progress * 100)}%"></i></div>` : ""}</div>
      ${S.uploading ? "" : `<button class="btn ghost icon" data-rm="${i}" title="Прибрати">${icon("x")}</button>`}</div>`).join("");
    $$("[data-rm]").forEach((b) => (b.onclick = () => { U.files.splice(+b.dataset.rm, 1); drawFiles(); sync(); }));
  };

  const drawCands = () => {
    const src = { filename: "за назвою файлу", file_time: "за часом створення файлу", manual: "за вказаною датою",
      filename_subject: "за назвою файлу та розкладом", recent: "за останніми заняттями" }[U.source];
    $("#det-src").innerHTML = src ? `${icon("sparkles")} Визначено ${src}` : "";
    $("#cands").innerHTML = U.candidates.length ? U.candidates.slice(0, 4).map((c) => `
      <button class="cand ${U.subject === c.subject_id && U.type === c.type ? "on" : ""}" data-s="${c.subject_id}" data-t="${c.type}" data-st="${c.start}" data-d="${c.date || ""}" style="--c:${c.color}">
        <span class="bar"></span><span><span class="t">${esc(c.subject)}</span><br><span class="m">${c.date && c.date !== U.date ? fmtDate(c.date) + ", " : ""}${c.start}–${c.end} · ${esc(typeLabel(c.type))} · ${esc(c.room)}</span></span>
        <span class="conf">${Math.round(c.confidence * 100)}%</span></button>`).join("") :
      (U.source ? `<div class="small muted">${icon("info")} У цей час за розкладом немає занять — виберіть предмет вручну.</div>` : "");
    if (U.hint) $("#cands").insertAdjacentHTML("afterbegin", `<div class="small muted" style="width:100%">${icon("file")} У назві «${esc(U.hint.file)}» впізнано предмет <b>${esc(U.hint.subject)}</b></div>`);
    $$(".cand").forEach((b) => (b.onclick = () => {
      U.subject = b.dataset.s; U.type = b.dataset.t; U.time = b.dataset.st;
      if (b.dataset.d) { U.date = b.dataset.d; $("#u-date").value = U.date; }
      $("#u-subj").value = U.subject; $("#u-type").value = U.type; $("#u-time").value = U.time; drawCands(); sync();
    }));
  };

  const detect = async (manual = false) => {
    const audio = U.files.find((f) => f.kind === "audio") || U.files.find((f) => f.kind === "video");
    const names = U.files.map((f) => f.file.name);
    const body = manual ? { date: U.date, time: U.time, duration: audio?.duration, filenames: names } :
      audio ? { filenames: names, last_modified: audio.file.lastModified, duration: audio.duration }
            : { filenames: names, materials_only: true };
    try {
      const r = await POST("/api/detect", body);
      U.candidates = r.candidates || []; U.source = r.source;
      if (!manual) {
        if (r.date) { U.date = r.date; $("#u-date").value = r.date; }
        const t = U.candidates[0]?.start || r.time;
        if (t) { U.time = t; $("#u-time").value = t; }
      }
      if (U.candidates[0] && (U.candidates[0].confidence >= 0.5 || !U.subject) && !U.attachTo) {
        U.subject = U.candidates[0].subject_id; U.type = U.candidates[0].type;
        $("#u-subj").value = U.subject; $("#u-type").value = U.type;
      }
      U.hint = r.subject_hint || null;
      drawCands(); sync();
    } catch (e) { handleErr(e); }
  };

  const addFiles = async (list) => {
    const arr = [...list].filter((f) => f.size > 0);
    if (!arr.length) return;
    for (const file of arr) {
      if (U.files.some((x) => x.file.name === file.name && x.file.size === file.size)) continue;
      U.files.push({ file, kind: kindOf(file.name), duration: null });
    }
    drawFiles(); sync();
    await Promise.all(U.files.filter((f) => (f.kind === "audio" || f.kind === "video") && f.duration == null).map(async (f) => { f.duration = (await readDuration(f.file)) || 0; }));
    drawFiles(); sync();
    if (!q.subject && !U.attachTo) detect(false);
  };

  // dropzone
  const dz = $("#dz"), fi = $("#file-in");
  dz.onclick = () => fi.click();
  fi.onchange = () => { addFiles(fi.files); fi.value = ""; };
  dz.ondragover = (e) => { e.preventDefault(); dz.classList.add("over"); };
  dz.ondragleave = () => dz.classList.remove("over");
  dz.ondrop = (e) => { e.preventDefault(); e.stopPropagation(); dz.classList.remove("over"); hideOverlay(); addFiles(e.dataTransfer.files); };
  S.onGlobalDrop = (files) => addFiles(files);

  $("#u-subj").onchange = (e) => { U.subject = e.target.value; drawCands(); sync(); };
  $("#u-type").onchange = (e) => { U.type = e.target.value; drawCands(); sync(); };
  $("#u-date").onchange = (e) => { U.date = e.target.value; detect(true); };
  $("#u-time").onchange = (e) => { U.time = e.target.value; detect(true); };
  $("#u-title").oninput = (e) => (U.title = e.target.value);
  $("#u-notes").oninput = (e) => (U.user_notes = e.target.value);
  $("#u-instr").oninput = (e) => (U.instructions = e.target.value);
  $("#u-tr").onchange = (e) => (U.transcribe = e.target.checked);
  $("#u-cl").onchange = (e) => (U.claude = e.target.checked);
  const seg = (id, key) => $$(`#${id} button`).forEach((b) => (b.onclick = () => { U[key] = b.dataset.v; $$(`#${id} button`).forEach((x) => x.classList.toggle("on", x === b)); }));
  seg("u-alang", "audio_language"); seg("u-nlang", "notes_language");

  $("#u-go").onclick = async () => {
    if (!U.subject && !(await confirmBox("Предмет не вибрано", "Зберегти лекцію без предмета? Його можна буде вказати пізніше.", "Зберегти"))) return;
    if (!U.date) return toast("Вкажіть дату", "err");
    const go = $("#u-go"); go.disabled = true;
    S.uploading = true; S.dirty = false; drawFiles();
    let lid = U.attachTo;
    try {
      if (!lid) {
        const m = await POST("/api/lectures", { subject_id: U.subject, type: U.type, date: U.date, time: U.time, title: U.title,
          audio_language: U.audio_language, notes_language: U.notes_language, user_notes: U.user_notes });
        lid = m.id; U.attachTo = lid;
      } else if (U.user_notes || U.title) {
        const cur = allLectures.find((m) => m.id === lid);
        await PATCH(`/api/lectures/${enc(lid)}`, { ...(U.title ? { title: U.title } : {}), ...(U.user_notes ? { user_notes: [cur?.user_notes, U.user_notes].filter(Boolean).join("\n\n") } : {}) });
      }
      const total = U.files.reduce((a, f) => a + f.file.size, 0) || 1;
      let doneBytes = 0, failed = 0;
      $("#up-progress").classList.remove("hidden");
      for (const f of U.files) {
        if (f.uploaded) { doneBytes += f.file.size; continue; }
        f.status = "завантаження…"; f.progress = 0; drawFiles();
        try {
          const r = await uploadOne(lid, f, (p) => {
            f.progress = p;
            const pct = Math.round(((doneBytes + p * f.file.size) / total) * 100);
            $("#up-bar").style.width = pct + "%"; $("#up-label").textContent = `Завантаження ${pct}% · ${esc(f.file.name)}`;
            const it = $(`.file-item[data-i="${U.files.indexOf(f)}"] .progress i`); if (it) it.style.width = Math.round(p * 100) + "%";
          });
          f.uploaded = true; f.status = "✓ збережено"; f.progress = null;
          if (r.already_here) toast(`Файл «${esc(f.file.name)}» уже є в цій лекції — пропущено`, "info", 6000);
          if (r.duplicate_of) toast(`Файл «${esc(f.file.name)}» уже є в іншій лекції (${esc(r.duplicate_of)})`, "info", 7000);
        } catch (e) { failed++; f.status = "помилка: " + e.message; f.progress = null; }
        doneBytes += f.file.size; drawFiles();
      }
      if (failed) {
        S.uploading = false; go.disabled = false; go.innerHTML = `${icon("refresh")} Повторити (${failed})`;
        toast(`Не вдалося завантажити ${failed} файл(и). Натисніть «Повторити».`, "err", 8000);
        return;
      }
      const hasAudio = U.files.some((f) => f.kind === "audio" || f.kind === "video");
      if (U.transcribe && hasAudio) await POST(`/api/lectures/${enc(lid)}/transcribe`).catch(handleErr);
      if (U.claude && (U.files.length || q.lecture)) await POST(`/api/lectures/${enc(lid)}/claude`, { instructions: U.instructions }).catch(handleErr);
      else if (U.instructions) await PATCH(`/api/lectures/${enc(lid)}`, { user_notes: [U.user_notes, "Побажання: " + U.instructions].filter(Boolean).join("\n\n") });
      S.uploading = false;
      toast("Лекцію збережено");
      location.hash = `#/lecture/${enc(lid)}`;
    } catch (e) {
      S.uploading = false; go.disabled = false; handleErr(e);
    }
  };

  drawFiles(); sync(); drawCands();
  if (pendingDrop.files) { const fl = pendingDrop.files; pendingDrop.files = null; addFiles(fl); }
  else if (q.subject || q.date) detect(true);
}

// ============================================================ LECTURE
function renderMarkdown(md) {
  const lines = md.replace(/\r/g, "").split("\n");
  let out = "", inList = null, inCode = false, para = [], table = [];
  const inline = (s) => esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/(^|[^*])\*([^*]+)\*/g, "$1<i>$2</i>");
  const flushP = () => { if (para.length) { out += `<p>${inline(para.join(" "))}</p>`; para = []; } };
  const flushL = () => { if (inList) { out += `</${inList}>`; inList = null; } };
  const flushT = () => {
    if (!table.length) return;
    const rows = table.filter((r) => !/^\s*\|?\s*:?-{2,}/.test(r)).map((r) => r.replace(/^\s*\||\|\s*$/g, "").split("|"));
    out += `<table>${rows.map((r, i) => `<tr>${r.map((c) => `<${i ? "td" : "th"}>${inline(c.trim())}</${i ? "td" : "th"}>`).join("")}</tr>`).join("")}</table>`;
    table = [];
  };
  for (const l of lines) {
    if (l.startsWith("```")) { flushP(); flushL(); flushT(); out += inCode ? "</code></pre>" : "<pre><code>"; inCode = !inCode; continue; }
    if (inCode) { out += esc(l) + "\n"; continue; }
    if (/^\s*\|.*\|\s*$/.test(l)) { flushP(); flushL(); table.push(l); continue; } else flushT();
    let m;
    if ((m = l.match(/^(#{1,4})\s+(.*)/))) { flushP(); flushL(); out += `<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`; }
    else if ((m = l.match(/^\s*[-*]\s+(.*)/))) { flushP(); if (inList !== "ul") { flushL(); out += "<ul>"; inList = "ul"; } out += `<li>${inline(m[1])}</li>`; }
    else if ((m = l.match(/^\s*\d+[.)]\s+(.*)/))) { flushP(); if (inList !== "ol") { flushL(); out += "<ol>"; inList = "ol"; } out += `<li>${inline(m[1])}</li>`; }
    else if ((m = l.match(/^>\s?(.*)/))) { flushP(); flushL(); out += `<blockquote>${inline(m[1])}</blockquote>`; }
    else if (!l.trim()) { flushP(); flushL(); }
    else para.push(l.trim());
  }
  flushP(); flushL(); flushT(); if (inCode) out += "</code></pre>";
  return out;
}

function transcriptHtml(text, hl = "") {
  const rx = hl ? new RegExp(hl.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi") : null;
  const mark = (s) => rx ? s.replace(rx, (x) => `<mark>${x}</mark>`) : s;
  let fileIdx = 0;
  return text.split("\n").map((l) => {
    const fm = l.match(/^### Файл (\d+):/);
    if (fm) { fileIdx = +fm[1] - 1; return `<h4>${esc(l.replace(/^###\s*/, ""))}</h4>`; }
    const m = l.match(/^\[(\d{1,2}):(\d{2}):(\d{2})\]\s*(.*)$/) || l.match(/^\[(\d{1,2}):(\d{2})\]\s*(.*)$/);
    if (m) {
      const secs = m.length === 5 ? +m[1] * 3600 + +m[2] * 60 + +m[3] : +m[1] * 60 + +m[2];
      const label = m.length === 5 ? `${m[1]}:${m[2]}:${m[3]}` : `${m[1]}:${m[2]}`;
      return `<p><button class="ts" data-seek="${secs}" data-f="${fileIdx}" title="Перейти в аудіо">${label}</button>${mark(esc(m[m.length - 1]))}</p>`;
    }
    return l.trim() ? `<p>${mark(esc(l))}</p>` : "";
  }).join("");
}

const PRACTICE = ["L", "P", "C", "S"];
const OUT_LABEL = { W: "Конспект", L: "Конспект", P: "Журнал проєкту", C: "Розв'язання", S: "Конспект" };
async function viewLecture(lid, q = {}) {
  let L = await GET(`/api/lectures/${enc(lid)}`);
  let tab = "";  // яку секцію зараз будує tabContent() (див. content() нижче)
  let seekTo = q.t != null ? +q.t : null;
  let editingTranscript = false;
  const fileUrl = (f, dl) => `/api/lectures/${enc(L.id)}/files/${f.kind}/${enc(f.name)}${dl ? "?download=1" : ""}`;
  const outUrl = (n, dl) => `/api/lectures/${enc(L.id)}/output/${enc(n)}?${dl ? "download=1&" : ""}t=${Math.round(L.output.pdf_mtime || 0)}`;

  const stepper = () => {
    const tr = L.transcribe || {}; const files = L.files.length > 0;
    const s1 = files ? "done" : "";
    const s2 = L.has_transcript ? "done" : tr.state === "running" || tr.state === "queued" ? "active" : tr.state === "error" ? "err" : "";
    const s3 = L.status === "done" ? "done" : L.status === "waiting_claude" ? "active" : L.status === "error" ? "err" : "";
    const s4 = L.status === "done" ? "done" : "";
    const step = (cls, n, t, d) => `<div class="step ${cls}"><span class="n">${cls === "done" ? icon("check") : cls === "err" ? "!" : n}</span><div class="st">${t}</div><div class="sd">${d}</div></div>`;
    const trDesc = L.has_transcript ? (tr.source === "local" ? "Локально (Whisper)" : tr.source === "manual" ? "Вручну" : "Готово") :
      tr.state === "running" ? esc(tr.message || "Іде розшифровка") + (tr.progress ? "" : "") : tr.state === "queued" ? "У черзі" :
      tr.state === "error" ? esc(tr.message || "Помилка") : "Зробить Claude";
    return `<div class="card stepper">
      ${step(s1, 1, "Файли", files ? `${L.files.length} шт.` : "Немає файлів")}
      ${step(s2, 2, "Розшифровка", trDesc)}
      ${step(s3, 3, "Конспект Claude", L.status === "done" ? "Зроблено " + relTime(L.output.result?.completed_at) : L.status === "waiting_claude" ? "Чекає на обробку" : L.status === "error" ? esc(L.output.result?.message || "Помилка") : "Не запитано")}
      ${step(s4, 4, "PDF", L.output.pdf ? "Готовий" : "—")}
    </div>${tr.state === "running" && tr.progress ? `<div class="progress" style="margin-top:-1px"><i style="width:${tr.progress}%"></i></div>` : ""}`;
  };

  const checkBox = () => {
    const c = L.schedule_check || {};
    if (c.status !== "mismatch") return "";
    const sg = c.suggestion;
    const at = c.at_time ? `За розкладом ${fmtDate(L.date, true)} о ${esc(L.time)} — <b>${esc(c.at_time.subject)}</b> (${esc(typeLabel(c.at_time.type))}).` :
      `За розкладом ${fmtDate(L.date, true)}${L.time ? " о " + esc(L.time) : ""} цього предмета немає (тиждень ${c.week?.week}, ${esc(c.week?.label || "")}).`;
    return `<div class="callout warn" style="margin-top:14px">${icon("alert")}<div class="c-body"><div class="c-title">Не збігається з розкладом</div>${at}
      ${sg ? ` Найближче заняття «${esc(L.subject?.short || "")}»: ${fmtDate(sg.date, true)}, ${esc(sg.time)} (${esc(typeLabel(sg.type))}).` : ""}
      <div class="btn-row" style="margin-top:8px">${sg ? `<button class="btn sm primary" data-fix='${esc(JSON.stringify(sg))}'>${icon("check")} Виправити дату й час</button>` : ""}
      ${c.at_time ? `<button class="btn sm" data-fixsubj="${esc(c.at_time.subject_id)}" data-fixtype="${esc(c.at_time.type)}">Це ${esc(c.at_time.subject)}</button>` : ""}
      <button class="btn sm" data-schedok>${icon("check")} Так і є</button>
      <button class="btn sm ghost" data-act="edit">${icon("edit")} Змінити вручну</button></div></div></div>`;
  };

  const actions = () => {
    const tr = L.transcribe?.state; const hasAudio = L.files.some((f) => f.kind === "audio");
    const b = [];
    if (L.status === "recording") {
      const mine = REC.lid === L.id && REC.state !== "idle";
      return mine ? `<a class="btn primary" href="#/record">${icon("mic")} До запису</a>`
        : `<a class="btn primary" href="#/record?lecture=${enc(L.id)}">${icon("mic")} Продовжити запис</a><button class="btn" data-act="recfin">${icon("check")} Завершити запис</button>`;
    }
    if (L.output?.pdf) b.push(`<a class="btn primary" href="${outUrl(L.output.pdf)}" target="_blank">${icon("pdf")} Відкрити PDF</a>`);  // 2.2: до конспекту — один дотик
    if (L.status === "waiting_claude") b.push(`<button class="btn" data-act="uncl">${icon("x")} Скасувати запит</button>`);
    else b.push(`<button class="btn ${L.output?.pdf ? "" : "primary"}" data-act="cl">${icon("sparkles")} ${L.status === "done" ? "Переробити конспект" : "Передати Claude"}</button>`);
    if (hasAudio && S.state.whisper.available) {
      if (tr === "running" || tr === "queued") b.push(`<button class="btn" data-act="untr">${icon("x")} Зупинити розшифровку</button>`);
      else b.push(`<button class="btn" data-act="tr">${icon("wave")} ${L.has_transcript ? "Розшифрувати знову" : "Розшифрувати локально"}</button>`);
    }
    b.push(`<a class="btn" href="#/upload?lecture=${enc(L.id)}">${icon("plus")} Додати файли</a>`);
    b.push(`<button class="btn" data-act="edit">${icon("edit")} Змінити</button>`);
    if (!S.state.remote_client) b.push(`<button class="btn ghost icon" data-act="folder" title="Відкрити папку лекції">${icon("folder")}</button>`);
    b.push(`<button class="btn ghost icon danger" data-act="del" title="Видалити">${icon("trash")}</button>`);
    restActs = b.slice(1);
    // на телефоні: головна дія + «⋯» (решта — у нижній шторці)
    return b[0] + `<span class="act-rest">${b.slice(1).join("")}</span><button class="btn act-dots" data-act="more" title="Інші дії">${icon("more")} Ще</button>`;
  };
  let restActs = [];

  // 2.7: без вкладок — секції одна під одною; відкриті показують вміст, решта згорнуті (вміст будується, лише коли відкрили)
  const chatMode = PRACTICE.includes(L.type) && !L.project_meeting;
  const sections = () => {
    const cnt = (k) => L.files.filter((f) => f.kind === k).length;
    const tr = L.transcribe?.state;
    const out = OUT_LABEL[L.type] || "Конспект";
    const list = PRACTICE.includes(L.type)
      ? [["zdacha", "check", "Що здати", (L.output.deliverables || []).length], ["plan", "list", "Інструкція", L.plan?.pending ? "…" : ""],
         ["task", "file", "Завдання", cnt("task")], ["code", "code", "Мій код", cnt("code")], ["pdf", "pdf", out, ""],
         ...((L.help || []).length ? [["help", "help", "Допоможи (через чергу)", L.help.length]] : [])]
      : [["pdf", "pdf", out, ""]];
    list.push(["files", "folder", "Файли", L.files.filter((f) => !["task", "code"].includes(f.kind)).length]);
    if (L.has_transcript || tr || L.files.some((f) => f.kind === "audio")) list.push(["transcript", "wave", "Розшифровка", ""]);
    list.push(["notes", "edit", "Нотатки", ""]);
    return list;
  };
  const open = new Set(PRACTICE.includes(L.type) ? ["zdacha", ...(L.plan?.has_plan || L.plan?.pending ? ["plan"] : []), ...(L.files.some((f) => f.kind === "task") ? [] : ["task"])] : ["pdf"]);
  if (q.tab) open.add(q.tab === "lab" ? "zdacha" : q.tab);  // старі посилання ?tab=… відкривають потрібну секцію
  if (q.t != null) open.add("transcript");
  const content = (k) => { const t = tab; tab = k; try { return tabContent(); } finally { tab = t; } };
  const secHtml = ([k, ic, label, n]) => `<details class="lsec" data-sec="${k}" ${open.has(k) ? "open" : ""}><summary>${icon(ic)} <b>${label}</b>${n ? `<span class="cnt">${n}</span>` : ""}</summary>
    <div class="sec-body" id="sec-${k}">${open.has(k) ? content(k) : ""}</div></details>`;
  const redrawSec = (k) => { const el = $(`#sec-${k}`); if (el) { el.innerHTML = content(k); bind(); } };
  const tabBody = () => sections().map(secHtml).join("");

  const tabContent = () => {
    if (tab === "pdf") {
      if (!L.output.pdf) {
        return `${PRACTICE.includes(L.type) ? "" : checklistHtml(L)}<div class="card"><div class="empty">${icon("pdf")}<b>${L.status === "waiting_claude" ? `${OUT_LABEL[L.type] || "Конспект"} ще готується` : `${OUT_LABEL[L.type] || "Конспект"} поки немає`}</b>
          ${L.status === "waiting_claude" ? "Надішліть Claude повідомлення нижче — PDF з'явиться тут автоматично." : "Натисніть «Передати Claude», щоб поставити лекцію в чергу."}</div>
          ${L.status === "waiting_claude" ? `<div style="padding:0 20px 20px">${claudeCallout(claudeWaiting() || 1)}</div>` : ""}</div>`;
      }
      const r = L.output.result || {};
      return `${PRACTICE.includes(L.type) ? "" : checklistHtml(L)}${r.summary || r.topics ? `<div class="card pad" style="margin-bottom:14px">${r.summary ? `<div>${esc(r.summary)}</div>` : ""}
          ${r.topics?.length ? `<div class="topics">${r.topics.map((t) => `<span>${esc(t)}</span>`).join("")}</div>` : ""}
          ${r.subject_check && r.subject_check !== "ok" ? `<div class="callout warn" style="margin-top:12px">${icon("alert")}<div class="c-body">Claude вважає, що предмет може бути іншим: ${esc(r.subject_check)}</div></div>` : ""}</div>` : ""}
        <div class="btn-row" style="margin-bottom:10px">
          <a class="btn primary" href="${outUrl(L.output.pdf, 1)}">${icon("download")} Завантажити PDF</a>
          <a class="btn" href="${outUrl(L.output.pdf)}" target="_blank">${icon("external")} Відкрити в новій вкладці</a>
          ${L.output.files.filter((f) => f.name !== L.output.pdf && !["result.json", "quiz.json", "plan.json", "plan.md"].includes(f.name) && !(PRACTICE.includes(L.type) && (L.output.deliverables || []).some((d) => d.name === f.name))).map((f) => `<a class="btn ghost sm" href="${outUrl(f.name, 1)}">${icon("file")} ${esc(f.name)}</a>`).join("")}
        </div>
        <iframe class="pdf-frame" src="${outUrl(L.output.pdf)}#view=FitH" title="PDF"></iframe>
        ${L.notes_md ? `<details class="card pad" style="margin-top:14px"><summary style="cursor:pointer;font-weight:600">Текстова версія конспекту</summary><div class="md">${renderMarkdown(L.notes_md)}</div></details>` : ""}`;
    }
    if (tab === "plan") return planHtml(L, outUrl);
    if (tab === "zdacha") {  // 2.2: звіт, код, документація до здачі
      const ds = L.output.deliverables || [];
      const rep = L.project_meeting ? "" : chatMode && !L.report?.req && !L.report?.result  // 2.7: звіт через чергу — запасний шлях
        ? `<details class="lsec" style="margin:0 0 12px"><summary>${icon("sparkles")} <b>Звіт через чергу Claude Code</b> <span class="small muted">або попроси в чаті</span></summary>${reportHtml(L)}</details>` : reportHtml(L);
      return `${rep}${checklistHtml(L) || (L.submitted_at ? "" : `<div class="card pad" data-lid="${esc(L.id)}" style="margin-bottom:14px"><button class="btn sm primary" data-submit="1">${icon("check")} Здано</button></div>`)}
        <div class="card list">${ds.length ? ds.map((f) => `<div class="row"><div class="body"><div class="title">${esc(f.title)}</div><div class="meta">${fmtSize(f.size)}</div></div>
          <div class="right"><a class="btn sm" href="${outUrl(f.name)}" target="_blank">${icon("external")} Відкрити</a><a class="btn ghost icon sm" href="${outUrl(f.name, 1)}" title="Завантажити">${icon("download")}</a></div></div>`).join("")
        : `<div class="empty">${icon("file")}<b>Файлів до здачі ще немає</b><span class="small">Звіт, код чи документацію, які підготує Claude, ви побачите тут.</span></div>`}</div>`;
    }
    if (tab === "task" || tab === "code") return practiceFilesHtml(L, tab, fileUrl);
    if (tab === "help") return helpHtml(L);
    if (tab === "transcript") {
      if (editingTranscript) return `<div class="card pad"><textarea class="input mono" id="tr-edit" style="min-height:60vh">${esc(L.transcript)}</textarea>
        <div class="btn-row" style="margin-top:10px"><button class="btn primary" id="tr-save">${icon("check")} Зберегти</button><button class="btn ghost" id="tr-cancel">Скасувати</button></div></div>`;
      if (!L.has_transcript) {
        const tr = L.transcribe || {};
        return `<div class="card"><div class="empty">${icon("wave")}<b>${tr.state === "running" ? esc(tr.message) : tr.state === "queued" ? "У черзі на розшифровку" : "Розшифровки ще немає"}</b>
          ${tr.state === "error" ? `<div style="color:var(--err)">${esc(tr.message)}</div>` : S.state.whisper.available ? "Запустіть локальну розшифровку або доручіть це Claude." : "Її зробить Claude під час обробки, або ввімкніть локальну розшифровку в налаштуваннях."}
          <div class="btn-row" style="justify-content:center;margin-top:12px"><button class="btn sm" id="tr-manual">${icon("edit")} Вставити текст вручну</button></div></div></div>`;
      }
      const audios = L.files.filter((f) => f.kind === "audio");
      return `<div class="card pad">
        ${audios.length ? `<audio id="tr-audio" controls preload="metadata" src="${fileUrl(audios[0])}" style="width:100%;margin-bottom:12px"></audio>` : ""}
        <div class="btn-row" style="margin-bottom:12px"><input class="input" id="tr-q" placeholder="Пошук у розшифровці…" style="max-width:300px">
          <span class="small muted" id="tr-n"></span><span style="flex:1"></span>
          <button class="btn sm" id="tr-copy">${icon("copy")} Копіювати</button><button class="btn sm" id="tr-ed">${icon("edit")} Редагувати</button></div>
        <div class="transcript" id="tr-body">${transcriptHtml(L.transcript)}</div></div>`;
    }
    if (tab === "files") {
      const g = (k) => L.files.filter((f) => f.kind === k);
      const del = (f) => `<button class="btn ghost icon sm" data-delf="${f.kind}|${esc(f.name)}" title="Видалити файл">${icon("trash")}</button>`;
      return `<div style="display:flex;flex-direction:column;gap:18px">
        ${g("audio").length ? `<div><h3>${icon("mic")} Аудіо</h3><div class="grid">${g("audio").map((f) => `<div class="audio-card"><div style="display:flex;align-items:center;gap:8px"><b style="flex:1;overflow:hidden;text-overflow:ellipsis">${esc(f.name)}</b><span class="small muted">${fmtSize(f.size)}${f.duration ? " · " + fmtDur(f.duration) : ""}</span><a class="btn ghost icon sm" href="${fileUrl(f, 1)}" title="Завантажити">${icon("download")}</a>${del(f)}</div><audio controls preload="none" src="${fileUrl(f)}"></audio></div>`).join("")}</div></div>` : ""}
        ${g("slides").length ? `<div><h3>${icon("slides")} Презентації та документи</h3><div class="card list">${g("slides").map((f) => `<div class="row"><div class="body"><div class="title">${esc(f.name)}</div><div class="meta">${fmtSize(f.size)} · додано ${relTime(f.added_at)}</div></div><div class="right"><a class="btn sm" href="${fileUrl(f)}" target="_blank">${icon("external")} Відкрити</a><a class="btn ghost icon sm" href="${fileUrl(f, 1)}">${icon("download")}</a>${del(f)}</div></div>`).join("")}</div></div>` : ""}
        ${g("video").length ? `<div><h3>${icon("video")} Відео</h3><div class="card list">${g("video").map((f) => { const v = (L.video || {})[f.name] || {};
          const st = v.state === "processing" || v.state === "queued" ? `<div class="progress" style="margin-top:6px"><i style="width:${v.progress || 2}%"></i></div><div class="meta"><span class="spinner"></span> ${v.state === "queued" ? "У черзі на обробку" : `Обробка: ${esc(v.step || "")} ${v.progress || 0}%`}</div>`
            : v.state === "error" ? `<div class="meta" style="color:var(--err)">${icon("alert")} ${esc(v.message || "Помилка")} <button class="btn sm" data-vproc="${esc(f.name)}">${icon("refresh")} Повторити</button></div>`
            : v.state === "done" ? `<div class="meta" style="color:var(--ok)">${icon("check")} ${esc(v.message || "Оброблено")}</div>` : `<div class="meta"><button class="btn sm" data-vproc="${esc(f.name)}">${icon("wave")} Витягти аудіо й кадри</button></div>`;
          return `<div class="row" style="align-items:flex-start"><div class="body"><div class="title">${esc(f.name)}</div><div class="meta">${fmtSize(f.size)}${f.duration ? " · " + fmtDur(f.duration) : ""}</div>${st}</div>
            <div class="right"><a class="btn sm" href="${fileUrl(f)}" target="_blank">${icon("external")} Відкрити</a>${del(f)}</div></div>`; }).join("")}</div>
          <div class="small muted" style="margin-top:6px">${icon("info")} Після обробки відео можна видалити, щоб звільнити місце: аудіо й кадри залишаться.</div></div>` : ""}
        ${g("image").length ? `<div><h3>${icon("image")} ${g("image").some((f) => f.source === "video") ? "Фото та кадри з відео" : "Фото"}</h3><div class="img-grid">${g("image").map((f) => `<div style="position:relative"><a href="${fileUrl(f)}" target="_blank"><img loading="lazy" src="${fileUrl(f)}" alt="${esc(f.name)}" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'empty small',textContent:'${esc(f.name)}'}))"></a><div style="position:absolute;top:4px;right:4px">${del(f)}</div>${f.t != null ? `<div class="frame-t">${fmtClock(f.t)}</div>` : ""}</div>`).join("")}</div></div>` : ""}
        ${g("other").length ? `<div><h3>${icon("file")} Інше</h3><div class="card list">${g("other").map((f) => `<div class="row"><div class="body"><div class="title">${esc(f.name)}</div><div class="meta">${fmtSize(f.size)}</div></div><div class="right"><a class="btn ghost icon sm" href="${fileUrl(f, 1)}">${icon("download")}</a>${del(f)}</div></div>`).join("")}</div></div>` : ""}
        ${!L.files.length ? `<div class="card"><div class="empty">${icon("folder")}<b>Файлів немає</b></div></div>` : ""}
        <div id="ep-cands"></div>
        <a class="dropzone" href="#/upload?lecture=${enc(L.id)}" style="display:block;padding:20px;text-decoration:none"><div class="t">${icon("plus")} Додати файли до цієї лекції</div></a>
      </div>`;
    }
    if (tab === "notes") {
      return `<div class="card pad"><div class="field"><label>Мої нотатки (Claude їх теж прочитає)</label><textarea class="input" id="n-text" style="min-height:200px">${esc(L.user_notes)}</textarea></div>
        <div class="field" style="margin-top:12px"><label>Побажання до наступного конспекту</label><textarea class="input" id="n-instr" style="min-height:70px">${esc(L.claude?.instructions || "")}</textarea><span class="hint">Застосуються, коли ви натиснете «${L.status === "done" ? "Переробити конспект" : "Передати Claude"}».</span></div>
        <div class="btn-row" style="margin-top:12px"><button class="btn primary" id="n-save">${icon("check")} Зберегти нотатки</button><span class="small muted" id="n-st"></span></div>
        <dl class="kv" style="margin-top:22px"><dt>Папка</dt><dd class="mono">${esc(L.folder)}</dd><dt>ID</dt><dd class="mono">${esc(L.id)}</dd>
          <dt>Створено</dt><dd>${new Date(L.created_at).toLocaleString("uk-UA")}</dd><dt>Змінено</dt><dd>${new Date(L.updated_at).toLocaleString("uk-UA")}</dd></dl></div>`;
    }
    return "";
  };

  const draw = () => {
    const s = L.subject;
    const cls = S.schedule.classes.find((c) => c.subject_id === L.subject_id && c.type === L.type && c.day === (parseDate(L.date).getDay() + 6) % 7);
    setView(`
      <a class="small muted" href="${s ? `#/subject/${enc(s.id)}` : "#/lectures"}" style="display:inline-flex;align-items:center;gap:4px">${icon("left")} ${s ? esc(s.short || s.name) : "Усі лекції"}</a>
      <div class="lec-head" style="margin-top:8px"><div style="min-width:0;flex:1">
        <div class="btn-row">${subjChip(s)}${statusBadge(L.status, L.status_label)}</div>
        <h1>${esc(L.display_title || (s ? s.name : "Лекція без предмета"))}</h1>
        <div class="lec-meta">${L.display_title && s ? `<span>${icon("book")} ${esc(s.name)}</span>` : ""}
          <span>${icon("calendar")} ${fmtDate(L.date, true)}</span>${L.time ? `<span>${icon("clock")} ${esc(L.time)}</span>` : ""}
          <span>${esc(typeLabel(L.type))}</span>${cls ? `<span>${icon("pin")} ${esc(cls.room)}</span>` : ""}
          <span title="Мова аудіо → конспекту">${LANG_SHORT[L.audio_language]} → ${LANG_SHORT[L.notes_language]}</span>${L.shared ? `<span title="Імпортовано з пакета">${icon("archive")} від ${esc(L.shared.from)}</span>` : ""}</div>
        ${L.plan_item ? `<div class="small" style="margin-top:6px;color:var(--text-2)">${icon("list")} За планом: <b>${esc(L.plan_item.title)}</b>${L.plan_item.topics?.length ? " — " + esc(L.plan_item.topics.join("; ")) : ""}</div>` : ""}
      </div></div>
      <div class="btn-row" style="margin-top:16px" id="lec-actions">${actions()}</div>
      <div id="lec-check">${projectMeetingBox(L)}${checkBox()}${epNewBox(L)}</div>
      <div id="lec-stepper" style="margin-top:16px">${stepper()}</div>
      ${chatMode ? `<div class="section" id="lec-chat">${chatPanel("lecture", L.id, L.chat)}</div>` : ""}
      <div class="section" id="lec-body">${tabBody()}</div>`,
      refresh);
    bind();
    if (open.has("files")) loadEpCands(L);
  };

  const refresh = async () => {
    const prev = JSON.stringify([L.status, L.transcribe, L.output, L.has_transcript, L.files.length, L.subject_id, L.title, L.date, L.time, L.schedule_check, L.video, L.help, L.checklist, L.plan, L.eportal_new, L.submitted_at, L.report, L.chat?.journal]);
    try { L = await GET(`/api/lectures/${enc(lid)}`); } catch (e) { if (/знайдено/.test(e.message)) { location.hash = "#/lectures"; } return; }
    const now = JSON.stringify([L.status, L.transcribe, L.output, L.has_transcript, L.files.length, L.subject_id, L.title, L.date, L.time, L.schedule_check, L.video, L.help, L.checklist, L.plan, L.eportal_new, L.submitted_at, L.report, L.chat?.journal]);
    if (prev === now) return;
    const playing = $$("audio").some((a) => !a.paused);
    const typing = document.activeElement && /TEXTAREA|INPUT/.test(document.activeElement.tagName);
    if (playing || typing || editingTranscript) {
      $("#lec-stepper").innerHTML = stepper(); $("#lec-actions").innerHTML = actions(); $("#lec-check").innerHTML = checkBox() + epNewBox(L); bindActions();
    } else {
      if (L.output.pdf && !JSON.parse(prev)[2]?.pdf) open.add("pdf");
      draw();
    }
  };

  const bindActions = () => {
    $$("[data-act]").forEach((b) => (b.onclick = async () => {
      const a = b.dataset.act;
      try {
        if (a === "cl") {
          const r = await modal({ title: L.status === "done" ? "Переробити конспект?" : "Передати Claude", okText: "У чергу",
            body: `<div class="field"><label>Побажання (необов'язково)</label><textarea class="input" name="instructions" placeholder="Напр.: детальніше про алгоритми планування">${esc(L.claude?.instructions || "")}</textarea></div>
              <div class="field" style="margin-top:10px"><label>Мова конспекту</label><select class="input" name="lang">${["pl", "uk", "ru"].map((l) => `<option value="${l}" ${L.notes_language === l ? "selected" : ""}>${S.state.langs[l]}</option>`).join("")}</select></div>` });
          if (!r) return;
          if (r.lang !== L.notes_language) await PATCH(`/api/lectures/${enc(L.id)}`, { notes_language: r.lang });
          await POST(`/api/lectures/${enc(L.id)}/claude`, { instructions: r.instructions });
          toast("Лекцію поставлено в чергу для Claude");
        } else if (a === "more") {
          openSheet("Дії з лекцією", `<div class="sheet-actions">${restActs.join("").replace(/btn ghost icon( danger)?" data-act="(\w+)" title="([^"]+)">(<svg[\s\S]*?<\/svg>)/g, (m, d, act, t, svg) => `btn${d || ""}" data-act="${act}">${svg} ${t}`)}</div>`, () => bindActions());
          return;
        } else if (a === "plan" || a === "replan") {
          let note = "";
          if (a === "replan") {
            const r = await modal({ title: "Оновити інструкцію", okText: "У чергу", body: `<p class="small muted" style="margin-top:0">Claude оновить <b>цю саму</b> інструкцію: допише, що змінилось, а кроки, які ти вже відмітив у «Що здати», не повторюватиме.</p><div class="field"><label>Що змінилось або що потрібно</label><textarea class="input" name="note" placeholder="Напр.: крок 3 не працює — помилка «Permission denied»; викладач додав вимогу окремого звіту"></textarea></div>` });
            if (!r) return; note = r.note || "";
          }
          await POST(`/api/lectures/${enc(L.id)}/plan`, { note }); toast("Інструкція в черзі Claude"); open.add("plan");
        } else if (a === "unplan") { await DEL(`/api/lectures/${enc(L.id)}/plan`); toast("Запит плану скасовано", "info"); }
        else if (a === "epnew-up") { await POST(`/api/lectures/${enc(L.id)}/eportal-new`, { action: "update" }); toast("Конспект поставлено на оновлення"); }
        else if (a === "epnew-x") { await POST(`/api/lectures/${enc(L.id)}/eportal-new`, { action: "dismiss" }); }
        else if (a === "recfin") { await POST(`/api/record/${enc(L.id)}/finish`, {}); toast("Запис завершено"); }
        else if (a === "uncl") { await DEL(`/api/lectures/${enc(L.id)}/claude`); toast("Запит скасовано", "info"); }
        else if (a === "tr") { await POST(`/api/lectures/${enc(L.id)}/transcribe`); toast("Розшифровку запущено", "info"); }
        else if (a === "untr") { await POST(`/api/lectures/${enc(L.id)}/transcribe/cancel`); toast("Розшифровку зупинено", "info"); }
        else if (a === "folder") { await POST(`/api/lectures/${enc(L.id)}/open-folder`); }
        else if (a === "del") {
          if (!(await confirmBox("Видалити лекцію?", `Лекцію буде переміщено в кошик (Налаштування → Кошик). Протягом ${S.state?.settings?.trash_days || 14} днів її можна відновити.`, "Видалити", true))) return;
          await DEL(`/api/lectures/${enc(L.id)}`); toast("Переміщено в кошик", "info"); location.hash = "#/lectures"; return;
        } else if (a === "edit") {
          const r = await modal({ title: "Змінити лекцію", okText: "Зберегти", body: `<div class="form-grid">
            <div class="field full"><label>Предмет</label><select class="input" name="subject_id"><option value="">— Не вибрано —</option>${S.schedule.subjects.map((s) => `<option value="${s.id}" ${L.subject_id === s.id ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</select></div>
            <div class="field full"><label>Тема</label><input class="input" name="title" value="${esc(L.title)}" placeholder="${esc(L.display_title || "")}"></div>
            <div class="field"><label>Дата</label><input class="input" type="date" name="date" value="${esc(L.date)}"></div>
            <div class="field"><label>Час</label><input class="input" type="time" name="time" value="${esc(L.time)}"></div>
            <div class="field"><label>Тип</label><select class="input" name="type">${Object.entries(S.state.types).map(([k, v]) => `<option value="${k}" ${L.type === k ? "selected" : ""}>${v}</option>`).join("")}</select></div>
            <div class="field"><label>Мова аудіо</label><select class="input" name="audio_language">${["pl", "uk", "ru", "en"].map((l) => `<option value="${l}" ${L.audio_language === l ? "selected" : ""}>${S.state.langs[l]}</option>`).join("")}</select></div>
            <div class="field"><label>Мова конспекту</label><select class="input" name="notes_language">${["pl", "uk", "ru"].map((l) => `<option value="${l}" ${L.notes_language === l ? "selected" : ""}>${S.state.langs[l]}</option>`).join("")}</select></div></div>` });
          if (!r) return;
          await PATCH(`/api/lectures/${enc(L.id)}`, r); toast("Збережено");
        }
        await refreshForce();
      } catch (e) { handleErr(e); }
    }));
  };
  const refreshForce = async () => { L = await GET(`/api/lectures/${enc(lid)}`); draw(); };

  const bind = () => {
    bindActions();
    bindPractice(L, refreshForce);
    if ($("#lec-body")) bindTodos($("#lec-body"), refreshForce);  // «Здано» у вкладці «Здача»
    bindReport(L, refreshForce);
    if (seekTo != null && $("#tr-body")) {
      const t0 = seekTo; seekTo = null;
      const btns = $$("#tr-body [data-seek]"); const b = btns.reduce((best, x) => (+x.dataset.seek <= t0 ? x : best), btns[0]);
      if (b) { b.scrollIntoView({ block: "center" }); b.closest("p")?.classList.add("hl-line"); const a = $("#tr-audio"); if (a) { const go = () => { a.currentTime = t0; }; a.readyState >= 1 ? go() : a.addEventListener("loadedmetadata", go, { once: true }); } }
    }
    $$("[data-fix]").forEach((b) => (b.onclick = async () => {
      const sg = JSON.parse(b.dataset.fix);
      try { await PATCH(`/api/lectures/${enc(L.id)}`, { date: sg.date, time: sg.time, type: sg.type }); toast("Дату й час виправлено"); await refreshForce(); } catch (e) { handleErr(e); }
    }));
    $$("[data-schedok]").forEach((b) => (b.onclick = async () => {
      try { await PATCH(`/api/lectures/${enc(L.id)}`, { schedule_ok: true }); toast("Добре, більше не нагадую"); await refreshForce(); } catch (e) { handleErr(e); }
    }));
    $$("[data-fixsubj]").forEach((b) => (b.onclick = async () => {
      try { await PATCH(`/api/lectures/${enc(L.id)}`, { subject_id: b.dataset.fixsubj, type: b.dataset.fixtype }); toast("Предмет змінено"); await refreshForce(); } catch (e) { handleErr(e); }
    }));
    bindCopyPrompt();
    bindChat(refreshForce);
    const openSec = (k) => { const d = $(`details[data-sec="${k}"]`); if (!d) return; if (!d.open) d.open = true; d.scrollIntoView({ block: "start", behavior: "smooth" }); };
    $$("[data-tabgo]").forEach((b) => (b.onclick = () => openSec(b.dataset.tabgo)));
    $$("details[data-sec]").forEach((d) => (d.ontoggle = () => {
      const k = d.dataset.sec;
      if (!d.open) { open.delete(k); return; }
      if (open.has(k)) return;
      open.add(k); redrawSec(k);
      if (k === "files") loadEpCands(L);
    }));
    $$("[data-vproc]").forEach((b) => (b.onclick = async () => { b.disabled = true; try { L = await POST(`/api/lectures/${enc(L.id)}/video/${enc(b.dataset.vproc)}/process`); toast("Обробку відео запущено", "info"); draw(); } catch (e) { handleErr(e); b.disabled = false; } }));
    $$("[data-delf]").forEach((b) => (b.onclick = async () => {
      const [kind, name] = b.dataset.delf.split("|");
      if (!(await confirmBox("Видалити файл?", `«${esc(name)}» буде переміщено в кошик.`, "Видалити", true))) return;
      try { await DEL(`/api/lectures/${enc(L.id)}/files/${kind}/${enc(name)}`); toast("Файл видалено", "info"); await refreshForce(); } catch (e) { handleErr(e); }
    }));
    const body = $("#tr-body");
    if (body) {
      body.onclick = (e) => {
        const t = e.target.closest("[data-seek]"); if (!t) return;
        const audios = L.files.filter((f) => f.kind === "audio"); const a = $("#tr-audio"); if (!a) return;
        const want = fileUrl(audios[+t.dataset.f] || audios[0]);
        if (!a.src.endsWith(want)) a.src = want;
        const go = () => { a.currentTime = +t.dataset.seek; a.play().catch(() => {}); };
        a.readyState >= 1 ? go() : a.addEventListener("loadedmetadata", go, { once: true });
      };
      $("#tr-q").oninput = debounce((e) => {
        const v = e.target.value.trim(); body.innerHTML = transcriptHtml(L.transcript, v.length > 1 ? v : "");
        const n = $$("mark", body).length; $("#tr-n").textContent = v.length > 1 ? `${n} збігів` : "";
        $("mark", body)?.scrollIntoView({ block: "center", behavior: "smooth" });
      }, 200);
      $("#tr-copy").onclick = () => copyText(L.transcript);
      $("#tr-ed").onclick = () => { editingTranscript = true; redrawSec("transcript"); };
    }
    if ($("#tr-manual")) $("#tr-manual").onclick = () => { editingTranscript = true; redrawSec("transcript"); };
    if ($("#tr-save")) {
      $("#tr-edit").oninput = () => (S.dirty = true);
      $("#tr-save").onclick = async () => {
        try { await PUT(`/api/lectures/${enc(L.id)}/transcript`, { text: $("#tr-edit").value }); S.dirty = false; editingTranscript = false; toast("Розшифровку збережено"); await refreshForce(); } catch (e) { handleErr(e); }
      };
      $("#tr-cancel").onclick = () => { S.dirty = false; editingTranscript = false; redrawSec("transcript"); };
    }
    if ($("#n-save")) {
      const mark = () => { S.dirty = true; $("#n-st").textContent = "Є незбережені зміни"; };
      $("#n-text").oninput = mark; $("#n-instr").oninput = mark;
      $("#n-save").onclick = async () => {
        try {
          await PATCH(`/api/lectures/${enc(L.id)}`, { user_notes: $("#n-text").value });
          L.claude = { ...(L.claude || {}), instructions: $("#n-instr").value };
          if (L.status === "waiting_claude") await POST(`/api/lectures/${enc(L.id)}/claude`, { instructions: $("#n-instr").value });
          S.dirty = false; $("#n-st").textContent = "Збережено ✓"; toast("Нотатки збережено");
        } catch (e) { handleErr(e); }
      };
    }
  };
  draw();
}

// ============================================================ SCHEDULE
async function viewSchedule() {
  let monday = null, showAll = false;
  let draft = JSON.parse(JSON.stringify(S.schedule));
  const settings = { ...S.state.settings };

  const gridHtml = (wk) => {
    const days = wk.days.slice(0, wk.days.slice(5).some((d) => d.classes.length) ? 7 : 5);
    const allCls = draft.classes;
    let minH = 24, maxH = 0;
    (showAll ? allCls : days.flatMap((d) => d.classes)).forEach((c) => { minH = Math.min(minH, Math.floor(minutes(c.start) / 60)); maxH = Math.max(maxH, Math.ceil(minutes(c.end) / 60)); });
    if (minH > maxH) { minH = 8; maxH = 16; }
    const HOUR = 52, top = (t) => ((minutes(t) - minH * 60) / 60) * HOUR;
    const now = new Date(), nowM = now.getHours() * 60 + now.getMinutes();
    const cols = days.map((d, i) => {
      const isToday = d.date === S.state.today;
      let evs = d.classes.map((c) => ({ ...c, ghost: false }));
      if (showAll) {
        const ids = new Set(evs.map((e) => e.id)), keys = new Set(evs.map((e) => `${e.subject_id}|${e.start}|${e.type}`));
        allCls.filter((c) => c.day === i && !ids.has(c.id) && !keys.has(`${c.subject_id}|${c.start}|${c.type}`)).forEach((c) => evs.push({ ...c, subject: subjById(c.subject_id), ghost: true }));
      }
      // розкладка паралельних занять
      evs.sort((a, b) => minutes(a.start) - minutes(b.start));
      const lanes = [];
      evs.forEach((e) => { let l = lanes.findIndex((end) => end <= minutes(e.start)); if (l < 0) { l = lanes.length; lanes.push(0); } lanes[l] = minutes(e.end); e.lane = l; });
      evs.forEach((e) => { e.lanes = Math.max(1, ...evs.filter((o) => minutes(o.start) < minutes(e.end) && minutes(o.end) > minutes(e.start)).map((o) => o.lane + 1)); });
      return `<div class="wg-col ${isToday ? "today" : ""}" style="height:${(maxH - minH) * HOUR}px">
        ${evs.map((e) => `<div class="wg-ev ${e.ghost ? "ghost" : ""}" style="--c:${e.subject?.color || "#999"};top:${top(e.start)}px;height:${Math.max(24, top(e.end) - top(e.start) - 2)}px;left:calc(${(e.lane / e.lanes) * 100}% + 3px);width:calc(${100 / e.lanes}% - 6px);right:auto"
          title="${esc(e.subject?.name)}\n${e.start}–${e.end} · ${typeLabel(e.type)}${e.group ? ", гр. " + esc(e.group) : ""}\n${esc(e.room)}${e.lecturers?.length ? "\n" + esc(e.lecturers.join(", ")) : ""}${e.parity !== "all" ? "\n" + PARITY[e.parity] : ""}">
          <b>${esc(e.subject?.short || "?")} · ${e.type}</b>${e.start}–${e.end}<div class="r">${esc(e.room)}${e.parity !== "all" ? " · " + (e.parity === "even" ? "парн." : "непарн.") : ""}</div></div>`).join("")}
        ${isToday && nowM > minH * 60 && nowM < maxH * 60 ? `<div class="wg-now" style="top:${top(`${now.getHours()}:${now.getMinutes()}`)}px"></div>` : ""}
      </div>`;
    }).join("");
    const times = Array.from({ length: maxH - minH + 1 }, (_, i) => `<div style="top:${i * HOUR}px;${i === 0 ? "transform:none" : ""}">${String(minH + i).padStart(2, "0")}:00</div>`).join("");
    return `<div class="week-grid" style="--days:${days.length};--hour:${HOUR}px">
      <div class="wg-head"></div>${days.map((d, i) => `<div class="wg-head ${d.date === S.state.today ? "today" : ""}">${DAYS[i]}<div class="dt">${parseDate(d.date).getDate()} ${MONTHS[parseDate(d.date).getMonth()]}</div></div>`).join("")}
      <div class="wg-times">${times}</div>${cols}</div>
      <div class="wk-agenda">${days.map((d, i) => `<div class="ag-day ${d.date === S.state.today ? "today" : ""}">
        <div class="ag-head">${DAYS[i]}<span>${parseDate(d.date).getDate()} ${MONTHS[parseDate(d.date).getMonth()]}</span></div>
        ${d.classes.length ? d.classes.map((c) => `<div class="ag-cls" style="--c:${c.subject?.color || "#999"}"><div class="ag-t">${c.start}<span>${c.end}</span></div>
          <div class="ag-i"><b>${esc(c.subject?.name || "?")}</b><div class="small muted">${esc(typeLabel(c.type))}${c.group ? ", гр. " + esc(c.group) : ""} · ${esc(c.room || "")}${c.lecturers?.length ? " · " + esc(c.lecturers.join(", ")) : ""}</div></div></div>`).join("")
          : `<div class="ag-free">Пар немає</div>`}</div>`).join("")}</div>`;
  };

  const drawGrid = async () => {
    const wk = await GET(`/api/week${monday ? "?start=" + monday : ""}`);
    monday = wk.monday;
    $("#wk-label").innerHTML = `${fmtDate(wk.days[0].date)} – ${fmtDate(wk.days[6].date)} · <b>тиждень ${wk.week.week}, ${wk.week.label}</b>`;
    $("#wk-grid").innerHTML = gridHtml(wk);
  };

  const editorHtml = () => `
    <div class="card pad"><div class="section-head"><h2>Предмети</h2><button class="btn sm" id="add-subj">${icon("plus")} Предмет</button></div>
      <div class="table-wrap"><table class="tbl"><thead><tr><th>Колір</th><th>Скорочення</th><th style="width:60%">Назва</th><th></th></tr></thead><tbody>
      ${draft.subjects.map((s, i) => `<tr><td><input type="color" class="input" data-s="${i}" data-k="color" value="${s.color}"></td>
        <td><input class="input" data-s="${i}" data-k="short" value="${esc(s.short)}" style="width:100px"></td>
        <td><input class="input" data-s="${i}" data-k="name" value="${esc(s.name)}"></td>
        <td><button class="btn ghost icon sm danger" data-rms="${i}" title="Видалити">${icon("trash")}</button></td></tr>`).join("")}
      </tbody></table></div></div>
    <div class="card pad" style="margin-top:14px"><div class="section-head"><h2>Заняття</h2><button class="btn sm" id="add-cls">${icon("plus")} Заняття</button></div>
      <div class="table-wrap"><table class="tbl"><thead><tr><th>Предмет</th><th>День</th><th>Початок</th><th>Кінець</th><th>Тип</th><th>Аудиторія</th><th>Тижні</th><th></th></tr></thead><tbody>
      ${draft.classes.map((c, i) => `<tr>
        <td><select class="input" data-c="${i}" data-k="subject_id" style="min-width:160px">${draft.subjects.map((s) => `<option value="${s.id}" ${c.subject_id === s.id ? "selected" : ""}>${esc(s.short)} — ${esc(s.name)}</option>`).join("")}</select></td>
        <td><select class="input" data-c="${i}" data-k="day" style="min-width:68px">${DAYS.map((d, k) => `<option value="${k}" ${c.day === k ? "selected" : ""}>${DAYS_SHORT[k]}</option>`).join("")}</select></td>
        <td><input class="input" type="time" data-c="${i}" data-k="start" value="${c.start}"></td>
        <td><input class="input" type="time" data-c="${i}" data-k="end" value="${c.end}"></td>
        <td><select class="input" data-c="${i}" data-k="type" style="min-width:62px">${Object.keys(S.state.types).map((t) => `<option ${c.type === t ? "selected" : ""}>${t}</option>`).join("")}</select></td>
        <td><input class="input" data-c="${i}" data-k="room" value="${esc(c.room)}" style="min-width:130px"></td>
        <td><select class="input" data-c="${i}" data-k="parity" style="min-width:140px">${Object.entries(PARITY).map(([k, v]) => `<option value="${k}" ${c.parity === k ? "selected" : ""}>${v}</option>`).join("")}</select></td>
        <td><button class="btn ghost icon sm danger" data-rmc="${i}">${icon("trash")}</button></td></tr>`).join("")}
      </tbody></table></div>
      <div class="small muted" style="margin-top:8px">Типи: ${Object.entries(S.state.types).map(([k, v]) => `<b>${k}</b> — ${v}`).join(", ")}</div></div>`;

  const bindEditor = () => {
    const mark = () => { S.dirty = true; $("#save-sched").disabled = false; $("#save-hint").textContent = "Є незбережені зміни"; };
    $$("[data-s]").forEach((i) => (i.oninput = () => { draft.subjects[+i.dataset.s][i.dataset.k] = i.value; mark(); }));
    $$("[data-c]").forEach((i) => (i.onchange = i.oninput = () => { const v = i.dataset.k === "day" ? +i.value : i.value; draft.classes[+i.dataset.c][i.dataset.k] = v; mark(); }));
    $$("[data-rms]").forEach((b) => (b.onclick = async () => {
      const s = draft.subjects[+b.dataset.rms];
      const n = draft.classes.filter((c) => c.subject_id === s.id).length;
      if (!(await confirmBox("Видалити предмет?", `«${esc(s.name)}» і ${n} занять у розкладі. Лекції залишаться, але без предмета.`, "Видалити", true))) return;
      draft.subjects.splice(+b.dataset.rms, 1); draft.classes = draft.classes.filter((c) => c.subject_id !== s.id); redrawEditor(); mark();
    }));
    $$("[data-rmc]").forEach((b) => (b.onclick = () => { draft.classes.splice(+b.dataset.rmc, 1); redrawEditor(); mark(); }));
    $("#add-subj").onclick = () => { draft.subjects.push({ id: "s" + Math.random().toString(36).slice(2, 7), name: "Новий предмет", short: "NEW", color: ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#a855f7", "#ec4899", "#14b8a6"][draft.subjects.length % 8] }); redrawEditor(); mark(); };
    $("#add-cls").onclick = () => { if (!draft.subjects.length) return toast("Спочатку додайте предмет", "err"); draft.classes.push({ id: Math.random().toString(36).slice(2, 10), subject_id: draft.subjects[0].id, day: 0, start: "09:15", end: "11:00", type: "W", room: "", parity: "all" }); redrawEditor(); mark(); };
  };
  const redrawEditor = () => { $("#editor").innerHTML = editorHtml(); bindEditor(); };

  setView(`
    <div class="page-head"><div><h1>Розклад</h1><div class="sub">Використовується для автоматичного визначення предмета</div></div></div>
    <div id="usos-hint"></div>
    <div class="btn-row" style="margin-bottom:12px">
      <button class="btn icon" id="wk-prev">${icon("left")}</button><button class="btn sm" id="wk-today">Цей тиждень</button><button class="btn icon" id="wk-next">${icon("right")}</button>
      <span class="small" id="wk-label"></span><span style="flex:1"></span>
      <label class="small" style="display:flex;gap:6px;align-items:center;cursor:pointer"><input type="checkbox" id="wk-all"> Показати заняття іншого тижня</label>
    </div>
    <div id="wk-grid"></div>
    <div class="card pad section">
      <h2>Парні / непарні тижні</h2>
      <div class="form-grid">
        <div class="field"><label>Як рахувати тижні</label><select class="input" id="p-mode"><option value="semester" ${settings.parity_mode === "semester" ? "selected" : ""}>Від початку семестру (1-й тиждень — непарний)</option><option value="iso" ${settings.parity_mode === "iso" ? "selected" : ""}>За номером тижня в календарі (ISO)</option></select></div>
        <div class="field"><label>Початок семестру</label><input class="input" type="date" id="p-start" value="${esc(settings.semester_start)}"></div>
        <label class="check full"><input type="checkbox" id="p-inv" ${settings.parity_invert ? "checked" : ""}><div><b>Поміняти парні й непарні місцями</b><span>Якщо застосунок показує «парний», а в університеті зараз непарний — увімкніть.</span></div></label>
      </div>
      <div class="small" id="p-preview" style="margin-top:10px"></div>
    </div>
    <div class="section" id="editor"></div>
    <div class="btn-row section save-bar" style="position:sticky;bottom:12px;padding:12px;border-radius:14px;background:var(--bg-elev);border:1px solid var(--border);box-shadow:var(--shadow)">
      <button class="btn primary" id="save-sched" disabled>${icon("check")} Зберегти розклад</button><span class="small muted" id="save-hint"></span>
      <span style="flex:1"></span><button class="btn ghost sm" id="reset-sched">${icon("undo")} Повернути розклад зі скріншоту</button></div>`);

  const savePar = async () => {
    try {
      S.state.settings = await PUT("/api/settings", { parity_mode: $("#p-mode").value, semester_start: $("#p-start").value, parity_invert: $("#p-inv").checked });
      S.state = await GET("/api/state"); renderNav();
      $("#p-preview").innerHTML = `${icon("check")} Збережено. Зараз: <b>тиждень ${S.state.week.week}, ${S.state.week.label}</b>.`;
      drawGrid();
    } catch (e) { handleErr(e); }
  };
  $("#p-mode").onchange = savePar; $("#p-start").onchange = savePar; $("#p-inv").onchange = savePar;
  $("#p-preview").innerHTML = `Зараз: <b>тиждень ${S.state.week.week}, ${S.state.week.label}</b>. Перевірте, чи збігається з університетом.`;
  const shift = (d) => { const m = parseDate(monday); m.setDate(m.getDate() + d); monday = isoDate(m); drawGrid(); };
  $("#wk-prev").onclick = () => shift(-7); $("#wk-next").onclick = () => shift(7);
  $("#wk-today").onclick = () => { monday = null; drawGrid(); };
  $("#wk-all").onchange = (e) => { showAll = e.target.checked; drawGrid(); };
  $("#save-sched").onclick = async () => {
    try {
      S.schedule = await PUT("/api/schedule", draft); draft = JSON.parse(JSON.stringify(S.schedule));
      S.dirty = false; $("#save-sched").disabled = true; $("#save-hint").textContent = "Збережено ✓"; toast("Розклад збережено"); redrawEditor(); drawGrid();
    } catch (e) { handleErr(e); }
  };
  $("#reset-sched").onclick = async () => {
    if (!(await confirmBox("Повернути початковий розклад?", "Поточний розклад буде замінено розкладом зі скріншоту (резервну копію буде створено).", "Повернути", true))) return;
    S.schedule = await POST("/api/schedule/reset"); draft = JSON.parse(JSON.stringify(S.schedule)); S.dirty = false; redrawEditor(); drawGrid(); toast("Розклад відновлено");
  };
  redrawEditor();
  GET("/api/usos").then((u) => { const el = $("#usos-hint"); if (!el) return; el.innerHTML = u.connected
      ? `<div class="callout ok" style="margin-bottom:14px">${icon("check")}<div class="c-body"><div class="c-title">Синхронізовано з USOS</div>${u.synced_at ? "Оновлено " + relTime(u.synced_at) + ". " : ""}Сітка тижня показує точні дати з USOS. Ручні зміни таблиці «Заняття» перезапишуться при наступній синхронізації. <a href="#/settings">Керувати</a></div></div>`
      : `<div class="callout info" style="margin-bottom:14px">${icon("info")}<div class="c-body">Можна не вводити розклад вручну — <a href="#/settings">підключіть USOS</a>, і застосунок сам його завантажить.</div></div>`; }).catch(() => {});
  await drawGrid();
}

// ============================================================ SEARCH
async function viewSearch(q) {
  setView(`<div class="page-head"><div><h1>Пошук</h1><div class="sub">По темах, конспектах, розшифровках і нотатках</div></div></div>
    <div class="search-big">${icon("search")}<input class="input" id="s-q" placeholder="Напр.: TCP, планування процесів, normalizacja…" value="${esc(q.q || "")}" autofocus></div>
    <div class="card list section" id="s-res"><div class="empty">${icon("search")}<b>Введіть щонайменше 2 символи</b></div></div>`);
  const run = debounce(async () => {
    const v = $("#s-q").value.trim();
    history.replaceState(null, "", "#/search" + (v ? "?q=" + enc(v) : ""));
    if (v.length < 2) { $("#s-res").innerHTML = `<div class="empty">${icon("search")}<b>Введіть щонайменше 2 символи</b></div>`; return; }
    try {
      const res = await GET(`/api/search?q=${enc(v)}`);
      const rx = new RegExp(v.split(/\s+/).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "gi");
      $("#s-res").innerHTML = res.length ? res.map((r) => `<a class="hit" href="#/lecture/${enc(r.lecture.id)}">
        <div class="btn-row">${subjChip(r.lecture.subject)}<b>${esc(r.lecture.display_title || r.lecture.subject?.name || "Лекція")}</b><span class="small muted">${fmtDate(r.lecture.date)}</span></div>
        ${r.hits.slice(0, 2).map((x) => `<div class="snip"><span class="where">${x.where}</span>${esc(x.snippet).replace(rx, (m) => `<mark>${m}</mark>`)}</div>`).join("")}</a>`).join("")
        : `<div class="empty">${icon("search")}<b>Нічого не знайдено</b></div>`;
    } catch (e) { handleErr(e); }
  }, 250);
  $("#s-q").oninput = run; if (q.q) run();
}

// ============================================================ SETTINGS
async function viewSettings() {
  const render = async () => {
    const [st, backups, trash, disk] = await Promise.all([GET("/api/state"), GET("/api/backups"), GET("/api/trash"), GET("/api/disk")]);
    S.state = st; const s = st.settings, w = st.whisper;
    const opt = (v, cur, t) => `<option value="${v}" ${v === cur ? "selected" : ""}>${t}</option>`;
    setView(`
      <div class="page-head"><div><h1>Налаштування</h1><div class="sub">Усе зберігається на вашому ПК і переживає перезапуск</div></div>
        <div><div class="label-t" style="margin-bottom:4px">Мова інтерфейсу</div>${langPickerHtml(s.ui_language || "uk")}</div></div>
      <div class="card pad" id="remote-card" style="margin-bottom:14px"><h2>${icon("phone")} Доступ з телефона (Tailscale)</h2><div class="small muted"><span class="spinner"></span> Перевіряю Tailscale…</div></div>
      <div class="card pad" id="ios-card" style="margin-bottom:14px"></div>
      <div class="grid cols-2" style="margin-bottom:14px"><div class="card pad" id="claude-card"></div><div class="card pad" id="share-card"></div></div>
      <div class="grid cols-2" id="integr" style="margin-bottom:14px">
        <div class="card pad" id="usos-card"><h2>${icon("calendar")} USOS — розклад</h2><div class="small muted"><span class="spinner"></span></div></div>
        <div class="card pad" id="ep-card"><h2>${icon("folder")} ePortal — матеріали</h2><div class="small muted"><span class="spinner"></span></div></div>
      </div>
      <div class="grid cols-2" style="margin-bottom:14px"><div class="card pad" id="cal-card"><h2>${icon("calendar")} Календар у телефоні</h2><div class="small muted"><span class="spinner"></span></div></div>
        <div class="card pad" id="push-card"><h2>${icon("phone")} Сповіщення</h2><div class="small muted"><span class="spinner"></span></div></div></div>
      <div class="card pad" id="health-card" style="margin-bottom:14px"><h2>${icon("cpu")} Стан застосунку</h2><div class="small muted"><span class="spinner"></span></div></div>
      <div class="grid cols-2">
        <div class="card pad"><h2>${icon("sparkles")} Обробка за замовчуванням</h2>
          <div style="display:flex;flex-direction:column;gap:12px">
            <div class="field"><label>Мова конспектів</label><select class="input" data-set="default_notes_language">${["pl", "uk", "ru"].map((l) => opt(l, s.default_notes_language, st.langs[l])).join("")}</select></div>
            <div class="field"><label>Мова лекцій (аудіо)</label><select class="input" data-set="default_audio_language">${["pl", "uk", "ru", "en"].map((l) => opt(l, s.default_audio_language, st.langs[l])).join("")}</select></div>
            <label class="check"><input type="checkbox" data-set="auto_request_claude" ${s.auto_request_claude ? "checked" : ""}><div><b>Одразу ставити в чергу для Claude</b><span>Галочка на сторінці завантаження буде ввімкнена</span></div></label>
            <label class="check"><input type="checkbox" data-set="auto_plan" ${s.auto_plan ? "checked" : ""}><div><b>Інструкція до лаби через чергу</b><span>Нова умова завдання сама ставить запит інструкції в чергу. Вимкнено: інструкцію робиш у чаті («Робота в чаті»)</span></div></label>
            <label class="check"><input type="checkbox" data-set="auto_transcribe" ${s.auto_transcribe ? "checked" : ""}><div><b>Одразу розшифровувати локально</b><span>Якщо Whisper встановлено</span></div></label>
            <div class="field"><label>Тема оформлення</label><select class="input" data-set="theme">${opt("auto", s.theme, "Як у системі")}${opt("light", s.theme, "Світла")}${opt("dark", s.theme, "Темна")}</select></div>
          </div></div>
        <div class="card pad"><h2>${icon("wave")} Локальна розшифровка (Whisper)</h2>
          ${w.available ? `<div class="callout ok">${icon("check")}<div class="c-body"><div class="c-title">Встановлено</div>${w.cuda && w.gpu_libs ? "Працює на відеокарті — швидко." : "Працює на процесорі. Лекція 90 хв ≈ 30–90 хв залежно від моделі й ПК."}</div></div>` :
            `<div class="callout info">${icon("info")}<div class="c-body"><div class="c-title">Не встановлено (необов'язково)</div>Безкоштовна розшифровка на вашому ПК. Без неї аудіо розшифрує Claude. Потрібно ~200 МБ + модель ~0,5–1,6 ГБ (завантажиться під час першої розшифровки).
              <div style="margin-top:10px"><button class="btn primary sm" id="w-install" ${w.install.state === "running" ? "disabled" : ""}>${w.install.state === "running" ? '<span class="spinner"></span> Встановлення…' : icon("download") + " Встановити"}</button></div></div></div>`}
          ${w.install.log ? `<div class="log">${esc(w.install.log)}</div>` : ""}
          ${w.available && w.gpu_name ? (w.gpu_libs
            ? (w.gpu_install.state === "done"
                ? `<div class="callout warn" style="margin-top:12px">${icon("refresh")}<div class="c-body"><div class="c-title">Бібліотеки NVIDIA встановлено</div>Перезапустіть «Конспект» (закрийте вікно й запустіть start.bat), щоб розшифровка пішла на відеокарті ${esc(w.gpu_name)}.</div></div>`
                : `<div class="small" style="margin-top:10px;color:var(--ok)">${icon("check")} Відеокарта: ${esc(w.gpu_name)} — бібліотеки NVIDIA встановлено.</div>`)
            : `<div class="callout warn" style="margin-top:12px">${icon("cpu")}<div class="c-body"><div class="c-title">Відеокарта не використовується</div>
                Знайдено <b>${esc(w.gpu_name)}</b>, але бракує бібліотек NVIDIA (cuBLAS, cuDNN), тому розшифровка йде на процесорі — повільно (лекція 90 хв ≈ 40–90 хв). З відеокартою — у 5–10 разів швидше.
                <div style="margin-top:10px"><button class="btn primary sm" id="gpu-install" ${w.gpu_install.state === "running" ? "disabled" : ""}>${w.gpu_install.state === "running" ? '<span class="spinner"></span> Встановлення…' : icon("download") + " Увімкнути відеокарту (~1 ГБ)"}</button></div></div></div>`) : ""}
          ${w.gpu_install && w.gpu_install.log ? `<div class="log" id="gpu-log">${esc(w.gpu_install.log)}</div>` : ""}
          ${s.whisper_model === "large-v3" ? `<div class="small muted" style="margin-top:10px">${icon("info")} Порада: модель <b>large-v3-turbo</b> майже така ж точна, але в 3–4 рази швидша.</div>` : ""}
          <div class="form-grid" style="margin-top:14px">
            <div class="field"><label>Модель</label><select class="input" data-set="whisper_model">
              ${opt("small", s.whisper_model, "small — швидко, гірша якість")}${opt("medium", s.whisper_model, "medium — баланс")}${opt("large-v3-turbo", s.whisper_model, "large-v3-turbo — рекомендовано")}${opt("large-v3", s.whisper_model, "large-v3 — найточніша, повільна")}</select></div>
            <div class="field"><label>Пристрій</label><select class="input" data-set="whisper_device">${opt("auto", s.whisper_device, "Автоматично")}${opt("cuda", s.whisper_device, "Відеокарта (CUDA)")}${opt("cpu", s.whisper_device, "Процесор")}</select></div>
          </div>
          <label class="check" style="margin-top:12px"><input type="checkbox" data-set="audio_enhance" ${s.audio_enhance !== false ? "checked" : ""}><div><b>Покращувати звук перед розшифровкою</b><span>Шумозаглушення, прибирання гулу й вирівнювання гучності — допомагає, коли викладач далеко від телефона. Якщо мовлення не знайдено — автоматична друга спроба без фільтра тиші.</span></div></label>
          <label class="check" style="margin-top:8px"><input type="checkbox" data-set="video_keep" ${s.video_keep ? "checked" : ""}><div><b>Зберігати відео після обробки</b><span>Вимкнено: коли з відео витягнуто аудіо й ключові кадри, сам відеофайл видаляється — запис зустрічі займає 0,5–1 ГБ.</span></div></label>
          ${w.current ? `<div class="small" style="margin-top:10px"><span class="spinner"></span> Зараз розшифровується: <a href="#/lecture/${enc(w.current)}">${esc(w.current)}</a> · у черзі: ${w.queue_size}</div>` : ""}
        </div>
        <div class="card pad"><h2>${icon("sparkles")} Зв'язок з Claude</h2>
          <p class="small" style="color:var(--text-2);margin-top:0">Застосунок і Claude обмінюються файлами через папку даних. Щоб Claude міг її бачити, у Claude (Cowork) натисніть <b>«Add folder»</b> і виберіть папку застосунку «Konspekt». Потім просто пишіть: <i>«Оброби нові лекції»</i>.</p>
          <dl class="kv"><dt>Папка даних</dt><dd class="mono">${esc(st.data_dir)}</dd></dl>
          <div class="btn-row" style="margin-top:12px">${st.remote_client ? "" : `<button class="btn sm" id="open-data">${icon("folder")} Відкрити папку</button>`}<button class="btn sm" id="copy-path">${icon("copy")} Копіювати шлях</button></div>
        </div>
        <div class="card pad"><h2>${icon("cpu")} Сервер</h2>
          <p class="small muted" style="margin-top:0">Дані зберігаються одразу після кожної дії, тож сервер можна просто закрити. Якщо його запущено без вікна (ярлик «Konspekt»), вимкніть тут.</p>
          <button class="btn sm danger" id="shutdown">${icon("x")} Вимкнути сервер</button></div>
        <div class="card pad"><h2>${icon("archive")} Резервні копії</h2>
          <p class="small muted" style="margin-top:0">Щодня автоматично зберігається архів усіх метаданих, розшифровок і конспектів (без важких аудіо). Зберігаються 20 останніх.</p>
          <div class="btn-row" style="margin-bottom:10px"><button class="btn sm" id="bk-now">${icon("plus")} Створити зараз</button><span class="small muted">Дані: ${fmtSize(disk.data_bytes)} · вільно на диску: ${fmtSize(disk.free_bytes)}</span></div>
          <div class="list" style="max-height:200px;overflow:auto">${backups.map((b) => `<div class="row" style="padding:8px 4px"><div class="body"><div class="small">${new Date(b.created).toLocaleString("uk-UA")}</div><div class="meta">${fmtSize(b.size)} · ${esc(b.name.includes("manual") ? "вручну" : b.name.includes("reset") ? "перед скиданням" : "авто")}</div></div><a class="btn ghost icon sm" href="/api/backups/${enc(b.name)}">${icon("download")}</a></div>`).join("") || '<div class="small muted">Ще немає</div>'}</div>
        </div>
        <div class="card pad" style="grid-column:1/-1" id="stor-card"><h2>${icon("archive")} Сховище</h2><div class="small muted"><span class="spinner"></span></div></div>
        <div class="card pad" style="grid-column:1/-1"><h2>${icon("trash")} Кошик</h2>
          <p class="small muted" style="margin-top:0">Видалені лекції та файли зберігаються ${s.trash_days || 14} днів, потім видаляються остаточно.</p>
          ${trash.length ? `<div class="list">${trash.map((t) => `<div class="row" style="padding:8px 4px"><div class="body"><div class="title">${esc(t.title || subjById(t.subject_id)?.name || t.id)}</div><div class="meta">${fmtDate(t.date)}</div></div><button class="btn sm" data-restore="${esc(t.trash_id)}">${icon("undo")} Відновити</button></div>`).join("")}</div>` : '<div class="small muted">Кошик порожній</div>'}
        </div>
      </div>`, render);
    $$("[data-set]").forEach((i) => (i.onchange = async () => {
      try {
        S.state.settings = await PUT("/api/settings", { [i.dataset.set]: i.type === "checkbox" ? i.checked : i.value });
        if (i.dataset.set === "theme") { applyTheme(i.value); renderNav(); }
        toast("Збережено", "ok", 1500);
      } catch (e) { handleErr(e); }
    }));
    $("#w-install") && ($("#w-install").onclick = async () => { await POST("/api/whisper/install"); toast("Встановлення почалося — це займе кілька хвилин", "info"); const t = setInterval(async () => { const ws = await GET("/api/whisper"); if (ws.install.state !== "running") { clearInterval(t); S.state.whisper = ws; render(); toast(ws.install.state === "done" ? "Whisper встановлено!" : "Не вдалося встановити — див. журнал", ws.install.state === "done" ? "ok" : "err"); } else { const lg = $(".log"); if (lg) { lg.textContent = ws.install.log; lg.scrollTop = 1e9; } else render(); } }, 2000); });
    loadRemote();
    loadIntegrations();
    loadHealth();
    loadShare(st);
    bindLangPicker();
    loadCalPush();
    loadIosCard();
    loadStorageCard();
    $("#shutdown").onclick = async () => { if (!(await confirmBox("Вимкнути сервер?", "Щоб знову відкрити застосунок, запустіть start.bat або ярлик «Konspekt».", "Вимкнути", true))) return; await POST("/api/shutdown").catch(() => {}); setView(`<div class="empty">${icon("check")}<b>Сервер вимкнено</b>Усі дані збережено. Цю вкладку можна закрити.</div>`); };
    $("#gpu-install") && ($("#gpu-install").onclick = async () => {
      await POST("/api/whisper/install-gpu"); toast("Встановлення почалося — це займе кілька хвилин", "info");
      const t = setInterval(async () => {
        const ws = await GET("/api/whisper");
        if (ws.gpu_install.state !== "running") { clearInterval(t); render(); toast(ws.gpu_install.state === "done" ? "Готово! Перезапустіть «Конспект»" : "Не вдалося — див. журнал", ws.gpu_install.state === "done" ? "ok" : "err", 8000); }
        else { const lg = $("#gpu-log"); if (lg) { lg.textContent = ws.gpu_install.log; lg.scrollTop = 1e9; } else render(); }
      }, 2500);
    });
    $("#open-data") && ($("#open-data").onclick = () => POST("/api/open-data-folder").catch(handleErr));
    $("#copy-path").onclick = () => copyText(st.data_dir);
    $("#bk-now").onclick = async () => { try { await POST("/api/backups"); toast("Резервну копію створено"); render(); } catch (e) { handleErr(e); } };
    $$("[data-restore]").forEach((b) => (b.onclick = async () => { try { const r = await POST(`/api/trash/${enc(b.dataset.restore)}/restore`); toast("Лекцію відновлено"); location.hash = `#/lecture/${enc(r.id)}`; } catch (e) { handleErr(e); } }));
  };
  await render();
}

// ============================================================ RECORDING IN THE APP
// Запис іде незалежно від сторінки: можна переходити між розділами, запис триває.
// Шматки по 5 с спершу кладемо в IndexedDB, потім надсилаємо на ПК; при обриві мережі — досилаємо пізніше.
const REC = { state: "idle", lid: null, sid: null, mr: null, stream: null, seq: 0, t0: 0, acc: 0, bytesSent: 0, queued: 0,
  net: true, level: 0, wake: null, ctx: null, an: null, subject: null, err: "", marks: 0, pumping: false, memStore: [] };
const RIDB = { db: null, failed: false };
function ridb() {
  return new Promise((res) => {
    if (RIDB.db || RIDB.failed) return res(RIDB.db);
    try {
      const r = indexedDB.open("konspekt-rec", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("q", { keyPath: "k" });
      r.onsuccess = () => res((RIDB.db = r.result));
      r.onerror = () => { RIDB.failed = true; res(null); };
    } catch { RIDB.failed = true; res(null); }
  });
}
async function rqPut(o) {
  const db = await ridb();
  if (!db) { REC.memStore.push(o); return; }
  await new Promise((res, rej) => { const tx = db.transaction("q", "readwrite"); tx.objectStore("q").put(o); tx.oncomplete = res; tx.onerror = () => rej(tx.error); })
    .catch(() => REC.memStore.push(o));
}
async function rqAll() {
  const db = await ridb();
  let items = [...REC.memStore];
  if (db) items = items.concat(await new Promise((res) => { const tx = db.transaction("q"); const r = tx.objectStore("q").getAll(); r.onsuccess = () => res(r.result || []); r.onerror = () => res([]); }));
  return items.sort((a, b) => (a.k < b.k ? -1 : 1));
}
async function rqDel(k) {
  REC.memStore = REC.memStore.filter((o) => o.k !== k);
  const db = await ridb(); if (!db) return;
  await new Promise((res) => { const tx = db.transaction("q", "readwrite"); tx.objectStore("q").delete(k); tx.oncomplete = res; tx.onerror = res; });
}
const ckey = (lid, sid, seq) => `${lid}|${sid}|${String(seq).padStart(6, "0")}`;

async function recPump() {
  if (REC.pumping) return; REC.pumping = true;
  try {
    for (;;) {
      const items = await rqAll();
      REC.queued = items.filter((o) => o.blob).length;
      recUi();
      if (!items.length) break;
      const o = items[0];
      try {
        if (o.blob) {
          const url = `/api/record/${enc(o.lid)}/${enc(o.sid)}/chunk?seq=${o.seq}${o.force ? "&force=1" : ""}`;
          const r = await fetch(url, { method: "POST", body: o.blob, headers: { "Content-Type": "application/octet-stream" } });
          if (r.status === 409) {
            const j = await r.json();
            if (j.next > o.seq) { await rqDel(o.k); continue; }                      // уже є на ПК
            const has = items.some((x) => x.lid === o.lid && x.sid === o.sid && x.seq === j.next);
            if (!has) { o.force = true; await rqPut(o); continue; }                  // шматок втрачено — пишемо далі
            await rqDel(o.k); await rqPut(o); continue;
          }
          if (r.status === 404) { await rqDel(o.k); continue; }                       // лекцію видалено
          if (!r.ok) throw new Error("HTTP " + r.status);
          REC.bytesSent += o.blob.size; REC.net = true;
          await rqDel(o.k);
        } else if (o.finish) {
          if (items.some((x) => x.blob && x.lid === o.lid && x.sid === o.sid)) { await rqDel(o.k); await rqPut({ ...o, k: o.k.replace("|~", "|~~") }); continue; }
          const r = await fetch(`/api/record/${enc(o.lid)}/finish`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session: o.sid, duration: o.duration }) });
          if (!r.ok && r.status !== 404) throw new Error("HTTP " + r.status);
          await rqDel(o.k);
          toast("Запис збережено на ПК", "ok", 4000);
        } else await rqDel(o.k);
      } catch (e) {
        REC.net = false; recUi();
        await new Promise((r) => setTimeout(r, 4000));
      }
    }
  } finally { REC.pumping = false; recUi(); }
}

function recElapsed() { return REC.acc + (REC.state === "recording" ? (Date.now() - REC.t0) / 1000 : 0); }

async function recWake() {
  try { if ("wakeLock" in navigator && REC.state === "recording" && !document.hidden) REC.wake = await navigator.wakeLock.request("screen"); } catch { }
}
async function recAutoResume() {
  const lid = REC.autoResume;
  if (!lid || REC.state !== "idle" || document.hidden) return;
  REC.autoResume = null;
  try {
    await recStart({ lecture_id: lid });
    toast("Запис продовжено новою частиною (поки екран був вимкнений, звук не писався)", "info", 7000);
    if (location.hash.startsWith("#/record")) viewRecord({});
  } catch (e) {
    toast("Не вдалося продовжити запис автоматично — натисніть «Дописати ще частину»", "err", 8000);
  }
}
document.addEventListener("visibilitychange", () => { if (!document.hidden) { recWake(); recPump(); setTimeout(recAutoResume, 600); } });
window.addEventListener("online", () => recPump());
window.addEventListener("beforeunload", (e) => { if (REC.state !== "idle" || REC.queued) { e.preventDefault(); e.returnValue = ""; } });

function pickMime() {
  const opts = ["audio/webm;codecs=opus", "audio/mp4;codecs=mp4a.40.2", "audio/mp4", "audio/ogg;codecs=opus", "audio/webm"];
  return opts.find((m) => window.MediaRecorder?.isTypeSupported?.(m)) || "";
}

async function recStart(opts) {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error("Запис мікрофона працює лише через захищену адресу: на ПК — http://127.0.0.1, з телефона — https-адреса Tailscale.");
  if (!window.MediaRecorder) throw new Error("Цей браузер не вміє записувати звук. Оновіть браузер (Chrome / Safari).");
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: true, channelCount: 1 } });
  const mime = pickMime();
  let r;
  try { r = await POST("/api/record/start", { ...opts, mime }); }
  catch (e) { stream.getTracks().forEach((t) => t.stop()); throw e; }
  const mr = new MediaRecorder(stream, mime ? { mimeType: mime, audioBitsPerSecond: 48000 } : { audioBitsPerSecond: 48000 });
  Object.assign(REC, { state: "recording", lid: r.lecture.id, sid: r.session, mr, stream, seq: 0, t0: Date.now(), acc: 0, bytesSent: 0, err: "", marks: 0,
    subject: r.lecture.subject, lecture: r.lecture });
  mr.ondataavailable = async (e) => {
    if (!e.data || !e.data.size) return;
    const seq = REC.seq++;
    await rqPut({ k: ckey(r.lecture.id, r.session, seq), lid: r.lecture.id, sid: r.session, seq, blob: e.data });
    recPump();
  };
  mr.onstop = async () => {
    const dur = Math.round(recElapsed());
    await new Promise((res) => setTimeout(res, 300));  // останній ondataavailable
    await rqPut({ k: `${r.lecture.id}|${r.session}|~`, lid: r.lecture.id, sid: r.session, finish: true, duration: dur });
    stream.getTracks().forEach((t) => t.stop());
    try { REC.ctx?.close(); } catch { }
    try { REC.wake?.release(); } catch { }
    Object.assign(REC, { state: "idle", mr: null, stream: null, ctx: null, an: null, lastLid: r.lecture.id, acc: dur });
    renderNav(); recPump();
    if (location.hash.startsWith("#/record")) viewRecord({}); else toast("Запис зупинено — зберігаю на ПК", "info", 3000);
  };
  mr.onerror = (e) => { REC.err = String(e.error?.message || e.error || "помилка запису"); toast("Помилка запису: " + esc(REC.err), "err", 8000); };
  stream.getAudioTracks()[0].onended = () => {
    if (REC.state === "idle") return;
    REC.autoResume = r.lecture.id;  // iPhone вимкнув мікрофон (екран заблоковано / дзвінок) — продовжимо, щойно повернетесь
    if (!document.hidden) toast("Мікрофон від'єднано — частину збережено, продовжую запис…", "info", 6000);
    try { mr.stop(); } catch { }
    if (!document.hidden) setTimeout(recAutoResume, 1200);
  };
  mr.start(5000);
  // індикатор рівня звуку
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const src = ctx.createMediaStreamSource(stream); const an = ctx.createAnalyser(); an.fftSize = 1024; src.connect(an);
    REC.ctx = ctx; REC.an = an;
  } catch { }
  recWake(); renderNav(); recTick();
}
function recPause() { if (REC.state !== "recording") return; REC.mr.pause(); REC.acc += (Date.now() - REC.t0) / 1000; REC.state = "paused"; recUi(true); }
function recResume() { if (REC.state !== "paused") return; REC.mr.resume(); REC.t0 = Date.now(); REC.state = "recording"; recWake(); recUi(true); }
function recStop() { if (REC.state === "idle") return; if (REC.state === "recording") REC.acc += (Date.now() - REC.t0) / 1000; REC.state = "stopping"; try { REC.mr.requestData(); } catch { } REC.mr.stop(); recUi(true); }
async function recMark() {
  if (!REC.lid) return; const t = Math.round(recElapsed());
  try { await POST(`/api/record/${enc(REC.lid)}/mark`, { t }); REC.marks++; toast(`Позначено ${fmtClock(t)} як важливе`, "ok", 1800); recUi(); } catch (e) { handleErr(e); }
}

let recTickT = null;
function recTick() {
  clearTimeout(recTickT);
  if (REC.an) {
    const a = new Uint8Array(REC.an.fftSize); REC.an.getByteTimeDomainData(a);
    let sum = 0; for (const v of a) sum += ((v - 128) / 128) ** 2;
    REC.level = Math.min(1, Math.sqrt(sum / a.length) * 4);
  }
  recUi();
  const pill = $("#rec-pill");
  const bt = $("#bn-rec-t"); if (bt) bt.textContent = fmtClock(recElapsed());
  if (pill) {
    pill.hidden = REC.state === "idle" || location.hash.startsWith("#/record");
    pill.innerHTML = `<span class="rec-dot"></span> ${REC.state === "paused" ? "Пауза" : "Запис"} ${fmtClock(recElapsed())}`;
  }
  if (REC.state !== "idle") recTickT = setTimeout(recTick, 200);
}
const fmtClock = (s) => { s = Math.floor(s); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60; return (h ? h + ":" : "") + String(m).padStart(h ? 2 : 1, "0") + ":" + String(x).padStart(2, "0"); };

// оновлення сторінки запису без повного перемальовування
function recUi(full = false) {
  const box = $("#rec-view"); if (!box) return;
  if (full) { box.innerHTML = recViewHtml(); bindRecView(); return; }
  const t = $("#rec-time"); if (t) t.textContent = fmtClock(recElapsed());
  const lv = $("#rec-level"); if (lv) lv.style.transform = `scaleX(${REC.state === "recording" ? Math.max(0.02, REC.level) : 0})`;
  const up = $("#rec-up"); if (up) up.innerHTML = recUpHtml();
}
const recUpHtml = () => `${REC.net ? icon("check") : icon("alert")} На ПК збережено ${fmtSize(REC.bytesSent)}${REC.queued ? ` · чекає відправки: ${REC.queued} шм. (${REC.net ? "надсилаю…" : "немає зв'язку з ПК — запис іде далі, досилатиму сам"})` : ""}`;

function recViewHtml() {
  if (REC.state === "idle") return "";
  const s = REC.subject;
  return `<div class="card pad rec-live ${REC.state}">
      <div class="btn-row" style="justify-content:center">${subjChip(s)}<span class="small muted">${esc(s ? s.name : "Предмет визначиться пізніше")}</span></div>
      <div class="rec-time" id="rec-time">${fmtClock(recElapsed())}</div>
      <div class="rec-level"><div id="rec-level"></div></div>
      <div class="small muted" style="text-align:center;margin:6px 0 16px">${REC.state === "paused" ? "Пауза — натисніть «Продовжити»" : REC.state === "stopping" ? "Зберігаю…" : "Іде запис. Тримайте екран увімкненим і телефон ближче до викладача."}</div>
      <div class="btn-row" style="justify-content:center">
        ${REC.state === "recording" ? `<button class="btn lg" id="rec-pause">⏸ Пауза</button>` : REC.state === "paused" ? `<button class="btn lg primary" id="rec-resume">● Продовжити</button>` : ""}
        <button class="btn lg" id="rec-mark" title="Викладач каже, що це буде на іспиті?">⭐ Важливо${REC.marks ? ` (${REC.marks})` : ""}</button>
        <button class="btn lg danger" id="rec-stop" ${REC.state === "stopping" ? "disabled" : ""}>■ Завершити</button>
      </div>
      <div class="small" id="rec-up" style="text-align:center;margin-top:14px;color:var(--text-2)">${recUpHtml()}</div>
    </div>`;
}
function bindRecView() {
  $("#rec-pause") && ($("#rec-pause").onclick = recPause);
  $("#rec-resume") && ($("#rec-resume").onclick = recResume);
  $("#rec-mark") && ($("#rec-mark").onclick = recMark);
  $("#rec-stop") && ($("#rec-stop").onclick = async () => { if (await confirmBox("Завершити запис?", "Запис збережеться на ПК, далі — розшифровка і конспект.", "Завершити")) recStop(); });
}

async function viewRecord(q) {
  if (REC.state !== "idle") {
    setView(`<div class="page-head"><div><h1>Запис лекції</h1></div><a class="btn ghost" href="#/lecture/${enc(REC.lid)}">${icon("external")} Лекція</a></div><div id="rec-view"></div>`, null);
    recUi(true); return;
  }
  const [wk, items] = await Promise.all([GET("/api/week"), GET("/api/lectures")]);
  const st = S.state, today = st.today;
  const now = new Date(), nowM = now.getHours() * 60 + now.getMinutes();
  const todayCls = (wk.days.find((d) => d.date === today) || { classes: [] }).classes;
  const cur = todayCls.find((c) => minutes(c.start) - 20 <= nowM && nowM <= minutes(c.end) + 10);
  const cont = q.lecture ? items.find((m) => m.id === q.lecture) : null;
  const subj0 = q.subject || cont?.subject_id || cur?.subject_id || "";
  const type0 = q.type || cont?.type || cur?.type || "W";
  const last = REC.lastLid ? items.find((m) => m.id === REC.lastLid) : null;
  const secure = window.isSecureContext && !!navigator.mediaDevices?.getUserMedia;
  setView(`
    <div class="page-head"><div><h1>Запис лекції</h1><div class="sub">Запис одразу зберігається на ПК — шматками кожні 5 секунд</div></div></div>
    ${/iPhone|iPad|iPod/.test(navigator.userAgent) ? `<div class="callout info" style="margin-bottom:14px">${icon("lock")}<div class="c-body"><div class="c-title">Хочете заблокувати телефон під час пари?</div>На iPhone браузер призупиняє мікрофон із вимкненим екраном (якщо так станеться — запис сам продовжиться новою частиною, щойно відкриєте застосунок). Для запису в кишені: «Диктофон» + команда «Конспект» — <a href="#/settings?ios">як налаштувати (2 хв)</a>.</div></div>` : ""}
    ${!secure ? `<div class="callout warn">${icon("alert")}<div class="c-body"><div class="c-title">Тут запис недоступний</div>Браузер дозволяє мікрофон лише на захищеній адресі. На телефоні відкрийте застосунок через <b>https-адресу Tailscale</b> (Налаштування → Доступ з телефона), а не через http://192.168…</div></div>` : ""}
    ${last ? `<div class="callout ok" style="margin-bottom:14px">${icon("check")}<div class="c-body"><div class="c-title">Попередній запис збережено (${fmtClock(REC.acc)})</div>
      ${REC.queued ? `Ще досилаю ${REC.queued} шм. на ПК — не закривайте сторінку.` : "Далі — розшифровка і конспект, автоматично."}
      <div class="btn-row" style="margin-top:8px"><a class="btn sm" href="#/lecture/${enc(last.id)}">${icon("external")} Відкрити лекцію</a><button class="btn sm" id="rec-cont">${icon("mic")} Дописати ще частину (після перерви)</button></div></div></div>` : ""}
    <div class="grid cols-2">
      <div class="card pad">
        ${cont ? `<div class="callout info" style="margin-bottom:12px">${icon("info")}<div class="c-body">Нова частина до лекції <b>${esc(cont.display_title || cont.subject?.name || cont.id)}</b> (${fmtDate(cont.date)})</div></div>` :
          cur ? `<div class="label-t">Зараз за розкладом</div><div class="class-card now" style="--c:${cur.subject.color};margin:6px 0 14px"><div class="bar"></div><div class="time">${cur.start}–${cur.end}</div><div class="info"><div class="name">${esc(cur.subject.name)}</div><div class="sub">${esc(typeLabel(cur.type))} · ${esc(cur.room)}</div></div></div>` :
          `<div class="small muted" style="margin-bottom:12px">${icon("info")} Зараз за розкладом занять немає — оберіть предмет або залиште «автоматично».</div>`}
        ${cont ? "" : `<div class="form-grid">
          <div class="field"><label>Предмет</label><select class="input" id="r-subj"><option value="">Автоматично (за розкладом)</option>${S.schedule.subjects.map((s) => `<option value="${s.id}" ${s.id === subj0 ? "selected" : ""}>${esc(s.short)} — ${esc(s.name)}</option>`).join("")}</select></div>
          <div class="field"><label>Тип</label><select class="input" id="r-type">${Object.entries(st.types).map(([k, v]) => `<option value="${k}" ${k === type0 ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></div>
          <div class="field"><label>Мова лекції</label><select class="input" id="r-alang">${["pl", "uk", "ru", "en"].map((l) => `<option value="${l}" ${l === st.settings.default_audio_language ? "selected" : ""}>${st.langs[l]}</option>`).join("")}</select></div>
          <div class="field"><label>Мова конспекту</label><select class="input" id="r-nlang">${["pl", "uk", "ru"].map((l) => `<option value="${l}" ${l === st.settings.default_notes_language ? "selected" : ""}>${st.langs[l]}</option>`).join("")}</select></div>
        </div>`}
        <div style="display:flex;justify-content:center;margin:22px 0 6px"><button class="rec-big" id="rec-go" ${secure ? "" : "disabled"}><span></span></button></div>
        <div class="small muted" style="text-align:center">Почати запис</div>
      </div>
      <div class="card pad"><h2>${icon("info")} Щоб запис вийшов якісним</h2>
        <ol class="small" style="margin:0;padding-left:18px;color:var(--text-2);display:flex;flex-direction:column;gap:8px">
          <li>Покладіть телефон <b>ближче до викладача</b>, мікрофоном догори (не в кишеню).</li>
          <li><b>Не блокуйте екран</b> і не перемикайтесь в інші застосунки — на iPhone запис у браузері зупиняється у фоні. Застосунок сам не дає екрану згаснути; яскравість можна зменшити.</li>
          <li>Поставте телефон на <b>зарядку</b> або перевірте батарею — 1,5 год запису ≈ 10–15%.</li>
          <li>Якщо зник інтернет — запис триває, а шматки досилаються, щойно зв'язок з'явиться. <b>Не закривайте вкладку</b>, поки не побачите «Запис збережено на ПК».</li>
          <li>Кнопка <b>⭐ Важливо</b> — коли викладач каже «це буде на колоквіумі». Claude зверне на це увагу в конспекті.</li>
        </ol></div>
    </div>
    <div id="rec-view"></div>`, null);
  const go = async (lectureId) => {
    const b = $("#rec-go"); if (b) b.disabled = true;
    try {
      await recStart(lectureId ? { lecture_id: lectureId } : { subject_id: $("#r-subj").value, type: $("#r-type").value, audio_language: $("#r-alang").value, notes_language: $("#r-nlang").value });
      viewRecord({});
    } catch (e) {
      if (b) b.disabled = false;
      const msg = e.name === "NotAllowedError" ? "Немає дозволу на мікрофон. Дозвольте доступ у налаштуваннях браузера для цього сайту." : e.name === "NotFoundError" ? "Мікрофон не знайдено." : e.message;
      toast(esc(msg), "err", 9000);
    }
  };
  $("#rec-go").onclick = () => go(cont?.id);
  $("#rec-cont") && ($("#rec-cont").onclick = () => go(REC.lastLid));
}

// ============================================================ DEADLINES
const dueText = (iso) => {
  const d = new Date(iso), now = new Date();
  const days = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 86400000);
  const hm = d.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" });
  if (d < now) return { t: `прострочено (${fmtDate(isoDate(d))})`, cls: "late" };
  if (days === 0) return { t: `сьогодні до ${hm}`, cls: "soon" };
  if (days === 1) return { t: `завтра до ${hm}`, cls: "soon" };
  if (days <= 6) return { t: `через ${days} дн. (${DAYS_SHORT[(d.getDay() + 6) % 7]}, ${hm})`, cls: days <= 3 ? "soon" : "" };
  return { t: `${fmtDate(isoDate(d))}, ${hm}`, cls: "" };
};
async function loadDeadlines(box, subjectId = null) {
  if (!box) return;
  let list = [];
  try { list = await GET("/api/deadlines"); } catch (e) { box.innerHTML = `<h2>${icon("clock")} Дедлайни</h2><div class="small" style="color:var(--err)">${esc(e.message)}</div>`; return; }
  const now = Date.now();
  let items = list.filter((x) => !subjectId || x.subject_id === subjectId);
  const open = items.filter((x) => !x.done && new Date(x.due).getTime() > now - 7 * 86400000);
  const shown = subjectId ? open : open.filter((x) => new Date(x.due).getTime() < now + 21 * 86400000);
  const row = (x) => {
    const s = subjById(x.subject_id), dt = dueText(x.due);
    return `<div class="row dl-row" style="padding:8px 2px"><button class="btn ghost icon sm" data-dldone="${esc(x.id)}" title="Позначити виконаним">${icon("check")}</button>
      <div class="body"><div class="title">${x.url ? (x.source === "lecture" ? `<a href="${esc(x.url)}">${esc(x.title)}</a>` : `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>`) : esc(x.title)}</div>
        <div class="meta">${s ? subjChip(s) + " " : x.course ? esc(x.course) + " · " : ""}<span class="dl-${dt.cls}">${dt.t}</span>${x.what && x.what !== x.title ? " · " + esc(x.what) : ""}</div></div>
      ${x.source === "manual" ? `<button class="btn ghost icon sm danger" data-dldel="${esc(x.id)}" title="Видалити">${icon("trash")}</button>` : ""}</div>`;
  };
  const epConnected = list.some((x) => x.source === "eportal");
  box.innerHTML = `<div class="section-head"><h2>${icon("clock")} Дедлайни</h2><button class="btn sm" id="dl-add">${icon("plus")} Додати</button></div>
    ${shown.length ? `<div class="list">${shown.map(row).join("")}</div>` : `<div class="empty" style="padding:14px">${icon("check")}<b>Найближчим часом нічого не треба здавати</b>${epConnected ? "" : `<span class="small">Завдання з ePortalu з'являться тут автоматично, коли <a href="#/settings">підключите ePortal</a>. Колоквіуми й екзамени можна додати вручну.</span>`}</div>`}
    ${!subjectId && open.length > shown.length ? `<div class="small muted" style="margin-top:6px">Ще ${open.length - shown.length} пізніше</div>` : ""}`;
  $$("[data-dldone]", box).forEach((b) => (b.onclick = async () => { await POST(`/api/deadlines/${enc(b.dataset.dldone)}`, { done: true }); toast("Виконано ✓", "ok", 1500); loadDeadlines(box, subjectId); }));
  $$("[data-dldel]", box).forEach((b) => (b.onclick = async () => { await DEL(`/api/deadlines/${enc(b.dataset.dldel)}`); loadDeadlines(box, subjectId); }));
  $("#dl-add", box).onclick = async () => {
    const r = await modal({ title: "Новий дедлайн", okText: "Додати", body: `
      <div class="field"><label>Що</label><input class="input" name="title" placeholder="Напр.: Kolokwium 1 / Sprawozdanie lab 3" required></div>
      <div class="form-grid" style="margin-top:10px"><div class="field"><label>Дата</label><input class="input" type="date" name="date" value="${S.state.today}"></div>
        <div class="field"><label>Час</label><input class="input" type="time" name="time" value="23:59"></div></div>
      <div class="field" style="margin-top:10px"><label>Предмет</label><select class="input" name="subject_id"><option value="">—</option>${S.schedule.subjects.map((s) => `<option value="${s.id}" ${s.id === subjectId ? "selected" : ""}>${esc(s.short)} — ${esc(s.name)}</option>`).join("")}</select></div>` });
    if (!r || !r.title) return;
    try { await POST("/api/deadlines", { title: r.title, due: `${r.date}T${r.time || "23:59"}`, subject_id: r.subject_id }); loadDeadlines(box, subjectId); } catch (e) { handleErr(e); }
  };
}

// ============================================================ ePortal slides for a lecture
async function loadEpCands(L) {
  const box = $("#ep-cands"); if (!box || !L.subject_id) return;
  let c = [];
  try { c = await GET(`/api/lectures/${enc(L.id)}/eportal`); } catch { return; }
  c = c.filter((x) => !x.attached);
  if (!c.length) return;
  const top = c.filter((x) => x.score > 0).slice(0, 5), rest = c.filter((x) => x.score <= 0);
  const row = (x) => `<div class="row" style="padding:8px 4px"><div class="body"><div class="title">${esc(x.file)}</div>
      <div class="meta">${esc([x.section, x.module].filter(Boolean).join(" · "))}${x.why.length ? ` · <span style="color:var(--ok)">${esc(x.why.join(", "))}</span>` : ""}</div></div>
      <div class="right"><a class="btn ghost icon sm" href="/api/subjects/${enc(L.subject_id)}/files/${enc(x.file)}" target="_blank" title="Відкрити">${icon("external")}</a><button class="btn sm" data-epatt="${esc(x.key)}" title="${x.as_task ? "Покласти в «Завдання» — Claude складе план" : "Додати до файлів заняття"}">${icon("plus")} ${x.as_task ? "До завдання" : "До лекції"}</button></div></div>`;
  box.innerHTML = `<div><h3>${icon("folder")} Файли з ePortalu для цього предмета</h3>
    <div class="small muted" style="margin:-4px 0 8px">Застосунок сам прикріплює файли, які явно підходять (за датою, номером заняття або змістом)${top.length ? " · вгорі — найімовірніші для цього заняття" : ""}.</div>
    <div class="card list">${(top.length ? top : rest.slice(0, 6)).map(row).join("")}</div>
    ${top.length && rest.length ? `<details style="margin-top:6px"><summary class="small">Інші файли (${rest.length})</summary><div class="card list">${rest.map(row).join("")}</div></details>` : ""}</div>`;
  $$("[data-epatt]", box).forEach((b) => (b.onclick = async () => { b.disabled = true; try { await POST(`/api/lectures/${enc(L.id)}/eportal`, { key: b.dataset.epatt }); toast(/завдання/.test(b.textContent) ? "Додано в «Завдання» — план у черзі Claude" : "Додано до лекції"); } catch (e) { handleErr(e); b.disabled = false; } }));
}

// ============================================================ сховище: скільки займають дані, стиснення, кошик
const STOR_COLORS = { audio: "#6366f1", video: "#a855f7", images: "#ec4899", slides: "#f59e0b", subjects: "#10b981", notes: "#0ea5e9", trash: "#ef4444", backups: "#64748b", other: "#94a3b8" };
async function loadStorageCard() {
  const box = $("#stor-card"); if (!box) return;
  let r;
  try { r = await GET("/api/storage"); } catch (e) { box.innerHTML = `<h2>${icon("archive")} Сховище</h2><div class="small" style="color:var(--err)">${esc(e.message)}</div>`; return; }
  const s = r.settings, cats = r.cats.filter((c) => c.bytes > 0), tot = r.total || 1, run = r.job.state === "running";
  const trashB = (r.cats.find((c) => c.key === "trash") || {}).bytes || 0;
  box.innerHTML = `<h2>${icon("archive")} Сховище</h2>
    <div class="stor-head"><b>${fmtSize(r.total)}</b><span class="small muted">займають дані · вільно на диску ${fmtSize(r.free)}</span></div>
    <div class="stor-bar">${cats.map((c) => `<i style="width:${Math.max(0.6, (c.bytes / tot) * 100)}%;background:${STOR_COLORS[c.key]}" title="${esc(c.label)}: ${fmtSize(c.bytes)}"></i>`).join("")}</div>
    <div class="stor-legend">${cats.map((c) => `<span><i style="background:${STOR_COLORS[c.key]}"></i>${esc(c.label)} <b>${fmtSize(c.bytes)}</b></span>`).join("")}</div>
    <div style="display:flex;flex-direction:column;gap:8px;margin-top:14px">
      <label class="check"><input type="checkbox" data-sset="compact_audio" ${s.compact_audio !== false ? "checked" : ""}><div><b>Стискати аудіо після розшифровки</b><span>AAC 48 кбіт/с моно: лекція 90 хв ≈ 32 МБ замість 80–250 МБ. Для мовлення різниці майже не чути; розшифровка й конспект не змінюються.</span></div></label>
      <label class="check"><input type="checkbox" data-sset="compact_images" ${s.compact_images !== false ? "checked" : ""}><div><b>Зменшувати великі фото</b><span>До 2200 px (дошку й текст добре видно), 3–4 МБ → ~0,5 МБ. Однакові файли (слайди з ePortalu в предметі й лекції) зберігаються один раз.</span></div></label>
      <div class="field" style="max-width:260px"><label>Кошик очищати через</label><select class="input" data-sset="trash_days">${[7, 14, 30, 60].map((d) => `<option value="${d}" ${+s.trash_days === d ? "selected" : ""}>${d} днів</option>`).join("")}</select></div>
    </div>
    <div class="btn-row" style="margin-top:12px">
      <button class="btn sm primary" id="st-run" ${run ? "disabled" : ""}>${run ? '<span class="spinner"></span> ' + esc(r.job.message || "Стискаю…") : icon("sparkles") + " Стиснути зараз"}</button>
      <button class="btn sm danger" id="st-trash" ${trashB ? "" : "disabled"}>${icon("trash")} Очистити кошик${trashB ? " (" + fmtSize(trashB) + ")" : ""}</button>
    </div>
    ${r.job.last ? `<div class="small muted" style="margin-top:8px">Останнє стиснення: ${relTime(r.job.last.at)} · звільнено ${fmtSize(r.job.last.saved || 0)}. Застосунок робить це сам раз на годину.</div>` : `<div class="small muted" style="margin-top:8px">Застосунок стискає дані сам раз на годину.</div>`}`;
  $$("[data-sset]", box).forEach((i) => (i.onchange = async () => {
    try { S.state.settings = await PUT("/api/settings", { [i.dataset.sset]: i.type === "checkbox" ? i.checked : +i.value }); toast("Збережено", "ok", 1500); } catch (e) { handleErr(e); }
  }));
  $("#st-run").onclick = async () => { await POST("/api/storage/compact"); loadStorageCard(); };
  $("#st-trash").onclick = async () => {
    if (!(await confirmBox("Очистити кошик?", "Видалені лекції та файли буде стерто остаточно — відновити їх уже не вийде.", "Очистити", true))) return;
    try { const x = await POST("/api/storage/empty-trash"); toast(`Звільнено ${fmtSize(x.freed)}`); route(); } catch (e) { handleErr(e); }
  };
  if (run) setTimeout(() => { if ($("#stor-card") === box) loadStorageCard(); }, 2500);
}

// ============================================================ iPhone: запис із заблокованим екраном (Диктофон + «Команди»)
async function loadIosCard() {
  const box = $("#ios-card"); if (!box) return;
  let r = {}, log = [];
  try { [r, log] = await Promise.all([GET("/api/remote").catch(() => ({})), GET("/api/quick-upload/log").catch(() => [])]); } catch { }
  const base = r.url || (location.protocol === "https:" ? location.origin : "");
  const url = base ? `${base}/api/quick-upload` : "";
  const open = location.hash.includes("ios") || (log[0] && !log[0].ok);
  const row = (x) => {
    const cut = x.raw && x.declared && x.bytes != null && x.bytes < x.declared;
    return `<div class="row" style="padding:7px 2px;align-items:flex-start"><div style="color:${x.ok ? "var(--ok)" : "var(--err)"};padding-top:2px">${icon(x.ok ? "check" : "alert")}</div><div class="body">
      <div class="small">${esc(x.result || "")}</div>
      <div class="meta">${relTime(x.at)} · ${x.bytes != null ? fmtSize(x.bytes) : "—"}${cut ? " з " + fmtSize(x.declared) : ""} · ${esc(x.type || "")}</div>
      ${cut ? `<div class="small" style="color:var(--warn,#d97706)">Передача обірвалась — схоже на тайм-аут «Команд» або слабкий інтернет. Надішліть через Wi-Fi або зменште запис (див. порада нижче).</div>` : ""}</div></div>`;
  };
  box.innerHTML = `<details ${open ? "open" : ""}><summary style="cursor:pointer;list-style:none"><h2 style="margin:0">${icon("lock")} Запис із заблокованим екраном (iPhone)</h2>
      <div class="small muted" style="margin-top:4px">Браузер на iPhone зупиняє мікрофон, коли екран гасне. Стандартний «Диктофон» пише й із заблокованим екраном — а команда «Конспект» одним дотиком надсилає запис сюди.</div></summary>
    ${url ? `<div class="field" style="margin-top:12px"><label>Адреса для команди</label><div class="btn-row"><input class="input mono" readonly value="${esc(url)}" style="flex:1;min-width:0"><button class="btn sm" id="ios-copy">${icon("copy")} Копіювати</button></div>
        <div class="small muted" style="margin-top:4px">Перевірка зв'язку: відкрийте цю адресу в Safari на iPhone — має з'явитись «✓ Конспект … на зв'язку». Якщо ні — увімкніть Tailscale на телефоні.</div></div>`
      : `<div class="callout warn" style="margin-top:12px">${icon("alert")}<div class="c-body">Спершу ввімкніть «Доступ з телефона (Tailscale)» вище — команда надсилає файл на https-адресу вашого ПК.</div></div>`}
    ${log.length ? `<div class="label-t" style="margin-top:14px">Останні спроби надсилання</div><div class="list">${log.slice(0, 5).map(row).join("")}</div>`
      : `<div class="small muted" style="margin-top:12px">${icon("info")} Жодна спроба надсилання ще не дійшла до ПК. Якщо команда показує помилку, а тут порожньо — запит не доходить: перевірте Tailscale на телефоні й адресу.</div>`}
    <div class="label-t" style="margin-top:14px">Команда для iOS 26–27 (простіша — без форми)</div>
    ${steps([
      "<b>«Команди»</b> → <b>+</b> → назва <b>Конспект</b>. Відкрийте деталі команди (назва вгорі → <b>ⓘ / Деталі</b>) → увімкніть <b>«Показувати в меню Поширити»</b>; типи вхідних даних — <b>Медіа</b> і <b>Файли</b>.",
      "Дія <b>«Отримати вміст URL»</b> (Get Contents of URL) → вставте адресу вище → розгорніть параметри: Метод <b>POST</b>, Тіло запиту <b>Файл</b> (File) → значення <b>«Вхідні дані Команди»</b> (Shortcut Input).",
      "Дія <b>«Показати сповіщення»</b> з текстом <b>«Вміст URL»</b> — побачите, на який предмет потрапив запис, або причину помилки.",
      "Стара команда з тілом «Форма» теж працює — переробляти не обов'язково, якщо вона не дає помилок.",
    ])}
    <div class="label-t" style="margin-top:14px">На парі</div>
    ${steps([
      "Запишіть лекцію у <b>«Диктофоні»</b> — екран можна блокувати.",
      "Після пари: запис → <b>⋯</b> → <b>Поширити</b> → <b>Конспект</b>. Предмет визначиться за часом запису й розкладом USOS.",
      "Довгі записи (60+ хв) краще надсилати через <b>Wi-Fi</b>: «Команди» обривають дуже довгі передачі. Щоб файли були меншими: <b>Параметри → Програми → Диктофон → Якість аудіо → Стиснена</b>.",
      "Запасний шлях без «Команд»: <b>Поширити → Зберегти у Файли</b>, потім у «Конспекті» на телефоні — <b>Завантажити</b> і виберіть файл.",
    ])}</details>`;
  $("#ios-copy") && ($("#ios-copy").onclick = () => copyText(url));
  if (location.hash.includes("ios")) box.scrollIntoView({ block: "start" });
}

// ============================================================ 2.2: стан застосунку (data/logs)
async function loadHealth() {
  const hc = $("#health-card"); if (!hc) return;
  let h;
  try { h = await GET("/api/health"); } catch (er) { hc.querySelector(".small").textContent = er.message; return; }
  const names = { eportal_sync: "ePortal — файли", eportal_deadlines: "ePortal — дедлайни", usos_sync: "USOS — розклад" };
  const syncRow = (k) => {
    const x = h.syncs[k];
    if (!x.last_ok && !x.last_error) return `<li>${names[k]}: <span class="muted">ще не було від оновлення</span></li>`;
    const ok = x.last_ok ? `вдало ${relTime(x.last_ok)}` : "вдалих ще не було";
    const bad = !x.ok && x.last_error ? ` · <span style="color:var(--err)">помилка ${relTime(x.last_error)}: ${esc(x.error_msg)}</span>` : "";
    return `<li>${names[k]}: ${ok}${bad}</li>`;
  };
  const errs = h.errors_24h ? `<div class="callout warn" style="margin-top:10px">${icon("alert")}<div class="c-body"><div class="c-title">Помилок за добу: ${h.errors_24h}</div>
      ${h.last_errors.map((e) => `<div class="small">${esc(new Date(e.t).toLocaleTimeString("uk", { hour: "2-digit", minute: "2-digit" }))} · ${esc(e.src)}: ${esc(e.msg)}</div>`).join("")}</div></div>`
    : `<div class="small" style="margin-top:10px">${icon("check")} За добу помилок немає</div>`;
  const tr = h.transcribe.count ? `Розшифровка: ${h.transcribe.count} за 30 днів${h.transcribe.speed_x ? `, у ${h.transcribe.speed_x}× швидше за запис` : ""}.` : "";
  const cl = h.claude.count ? ` Claude обробив ${h.claude.count}, у середньому через ${h.claude.avg_wait_h} год після запиту.` : "";
  hc.innerHTML = `<h2>${icon("cpu")} Стан застосунку</h2>
    <ul class="small" style="margin:0;padding-left:18px;display:flex;flex-direction:column;gap:4px">${Object.keys(names).map(syncRow).join("")}</ul>
    ${errs}
    ${tr || cl ? `<div class="small muted" style="margin-top:8px">${tr}${cl}</div>` : ""}
    <div class="small muted" style="margin-top:8px">Журнал лежить у data/logs на цьому ПК і нікуди не надсилається.</div>`;
}

// ============================================================ USOS / ePortal
const steps = (items) => `<ol class="small" style="margin:8px 0 0;padding-left:18px;color:var(--text-2);display:flex;flex-direction:column;gap:6px">${items.map((i) => `<li>${i}</li>`).join("")}</ol>`;
const syncedLine = (r) => r.synced_at ? `Оновлено ${relTime(r.synced_at)}` : "Ще не синхронізовано";
let integrTimer = null;
async function loadIntegrations() {
  const uc = $("#usos-card"), ec = $("#ep-card"); if (!uc || !ec) return;
  let u, e;
  try { [u, e] = await Promise.all([GET("/api/usos"), GET("/api/eportal")]); } catch (er) { uc.innerHTML += `<div class="small" style="color:var(--err)">${esc(er.message)}</div>`; return; }
  const errBox = (r) => r.status === "error" || r.status === "expired" ? `<div class="callout warn" style="margin-top:10px">${icon("alert")}<div class="c-body">${esc(r.message)}</div></div>` : "";
  const spin = (r) => r.running ? `<div class="small" style="margin-top:8px"><span class="spinner"></span> Синхронізую…</div>` : "";
  // ---- USOS
  uc.innerHTML = `<h2>${icon("calendar")} USOS — розклад</h2>` + (u.connected ? `
      <div class="callout ok">${icon("check")}<div class="c-body"><div class="c-title">Розклад береться з USOS</div>
        ${u.events ? `${u.events} занять (${fmtDate(u.first)} – ${fmtDate(u.last)}). Точні дати: перенесення, свята й парність тижнів ураховано.` : ""}
        <div class="small muted">${syncedLine(u)} · автоматично двічі на добу</div></div></div>${errBox(u)}${spin(u)}
      <div class="btn-row" style="margin-top:12px"><button class="btn sm" id="usos-sync" ${u.running ? "disabled" : ""}>${icon("refresh")} Оновити зараз</button><button class="btn sm ghost danger" id="usos-off">Відключити</button></div>` : `
      <p class="small" style="color:var(--text-2);margin-top:0">Застосунок сам завантажить розклад (з точними датами, аудиторіями й викладачами) і оновлюватиме його.</p>
      ${steps(["У USOSweb відкрийте <b>Mój USOSweb → Plan zajęć</b> і натисніть <b>«Udostępnij plan»</b> (або «Link do planu»).", "Скопіюйте посилання й вставте нижче."])}
      <div class="btn-row" style="margin-top:10px"><input class="input" id="usos-url" placeholder="https://web.usos.pwr.edu.pl/kontroler.php?…&token=…" style="flex:1;min-width:200px"><button class="btn primary sm" id="usos-on">${icon("check")} Підключити</button></div>
      ${errBox(u)}
      <div class="small muted" style="margin-top:8px">${icon("info")} Посилання зберігається лише на цьому ПК. Поточний розклад буде збережено в резервну копію перед заміною.</div>`);
  // ---- ePortal
  const subjOpts = (cur) => `<option value="">— не прив'язувати —</option>` + (S.schedule?.subjects || []).map((s) => `<option value="${s.id}" ${s.id === cur ? "selected" : ""}>${esc(s.short)} — ${esc(s.name)}</option>`).join("");
  ec.innerHTML = `<h2>${icon("folder")} ePortal — матеріали</h2>` + (e.connected ? `
      <div class="callout ok">${icon("check")}<div class="c-body"><div class="c-title">Підключено${e.user ? ": " + esc(e.user) : ""}</div>
        ${esc(e.message || "")}<div class="small muted">${syncedLine(e)} · файлів завантажено: ${e.files}</div></div></div>${spin(e)}
      ${e.courses.length ? `<div class="label-t" style="margin:12px 0 4px">Курси → предмети</div><div class="list">${e.courses.map((c) => `<div class="row" style="padding:6px 2px;gap:8px"><div class="body"><div class="small">${esc(c.fullname)}</div></div><select class="input" data-epc="${c.id}" style="max-width:190px">${subjOpts(c.subject_id)}</select></div>`).join("")}</div>` : ""}
      <div class="small muted" style="margin-top:8px">Файли й план тем з'являються на сторінці предмета. Захищені PDF (без завантаження) не беруться — для них, як і раніше, скріншоти.</div>
      <div class="btn-row" style="margin-top:12px"><button class="btn sm" id="ep-sync" ${e.running ? "disabled" : ""}>${icon("refresh")} Оновити зараз</button><button class="btn sm ghost danger" id="ep-off">Відключити</button></div>` : `
      ${errBox(e)}
      <p class="small" style="color:var(--text-2);margin-top:0">Вхід — як у мобільному застосунку Moodle: пароль вводите лише на сайті ePortalu, застосунок отримує тільки ключ доступу.</p>
      ${S.state?.remote_client ? `<div class="callout warn">${icon("alert")}<div class="c-body">Підключайте ePortal <b>на ПК</b>, а не з телефона.</div></div>` : ""}
      ${steps(["Натисніть «Підключити» — відкриється ePortal у браузері (увійдіть, якщо треба).", "Браузер спитає, чи відкрити посилання в іншій програмі (pythonw / Konspekt) — дозвольте.", "За кілька секунд тут з'явиться «Підключено»."])}
      <div class="btn-row" style="margin-top:10px"><button class="btn primary sm" id="ep-on">${icon("check")} Підключити ePortal</button></div>
      ${e.pending ? `<div class="small" style="margin-top:8px"><span class="spinner"></span> Чекаю підтвердження з браузера…</div>` : ""}
      <details style="margin-top:12px"><summary class="small">Не спрацювало? Вставити посилання вручну</summary>
        <p class="small muted">Якщо браузер нічого не запропонував: у вкладці ePortalu натисніть F12 → Console, знайдіть рядок <span class="mono">moodlemobile://token=…</span> (помилка «Failed to launch») і скопіюйте його.</p>
        <div class="btn-row"><input class="input" id="ep-link" placeholder="moodlemobile://token=…" style="flex:1;min-width:200px"><button class="btn sm" id="ep-paste">Зберегти</button></div></details>`);
  const busy = (b) => { b.disabled = true; b.innerHTML = '<span class="spinner"></span>'; };
  $("#usos-on") && ($("#usos-on").onclick = async (ev) => { busy(ev.target); try { await POST("/api/usos/connect", { url: $("#usos-url").value }); toast("USOS підключено — завантажую розклад…", "info"); } catch (er) { handleErr(er); } loadIntegrations(); });
  $("#usos-sync") && ($("#usos-sync").onclick = async (ev) => { busy(ev.target); await POST("/api/usos/sync").catch(handleErr); loadIntegrations(); });
  $("#usos-off") && ($("#usos-off").onclick = async () => { if (!(await confirmBox("Відключити USOS?", "Розклад залишиться як є, але більше не оновлюватиметься автоматично.", "Відключити", true))) return; await POST("/api/usos/disconnect"); loadIntegrations(); });
  $("#ep-on") && ($("#ep-on").onclick = async () => { try { const r = await POST("/api/eportal/connect"); window.open(r.launch_url, "_blank", "noopener"); loadIntegrations(); } catch (er) { handleErr(er); } });
  $("#ep-paste") && ($("#ep-paste").onclick = async (ev) => { busy(ev.target); try { await POST("/api/eportal/token", { link: $("#ep-link").value }); toast("ePortal підключено"); } catch (er) { handleErr(er); } loadIntegrations(); });
  $("#ep-sync") && ($("#ep-sync").onclick = async (ev) => { busy(ev.target); await POST("/api/eportal/sync").catch(handleErr); loadIntegrations(); });
  $("#ep-off") && ($("#ep-off").onclick = async () => { if (!(await confirmBox("Відключити ePortal?", "Завантажені файли залишаться в предметах.", "Відключити", true))) return; await POST("/api/eportal/disconnect"); loadIntegrations(); });
  $$("[data-epc]").forEach((sel) => (sel.onchange = async () => { try { await POST("/api/eportal/course", { course_id: Number(sel.dataset.epc), subject_id: sel.value }); toast("Збережено — синхронізую", "ok", 1800); } catch (er) { handleErr(er); } }));
  clearTimeout(integrTimer);
  if (u.running || e.running || e.pending) integrTimer = setTimeout(() => { if ($("#usos-card")) loadIntegrations(); }, 2500);
}

// ============================================================ remote access (Tailscale)
async function loadRemote(extra = null) {
  const box = $("#remote-card"); if (!box) return;
  let r;
  try { r = extra || (await GET("/api/remote")); } catch (e) { box.innerHTML += `<div class="small" style="color:var(--err)">${esc(e.message)}</div>`; return; }
  const head = `<h2>${icon("phone")} Доступ з телефона (Tailscale)</h2>`;
  const steps = (items) => `<ol class="small" style="margin:8px 0 0;padding-left:18px;color:var(--text-2);display:flex;flex-direction:column;gap:6px">${items.map((i) => `<li>${i}</li>`).join("")}</ol>`;
  const out = extra?.output ? `<div class="log">${esc(extra.output)}</div>` : "";
  const hint = extra?.hint ? `<div class="callout warn" style="margin-top:10px">${icon("alert")}<div class="c-body">${esc(extra.hint)}</div></div>` : "";
  let body;
  if (!r.installed) {
    body = `<p class="small" style="color:var(--text-2);margin:0">Tailscale — безкоштовна приватна мережа між вашими пристроями. Застосунок відкриватиметься з телефона будь-де (університет, мобільний інтернет), а сторонні його не побачать.</p>
      ${steps(["У папці застосунку запустіть <b>tailscale-setup.bat</b> — він встановить Tailscale, попросить увійти (Google / Microsoft / GitHub) і все налаштує.",
        "На телефон поставте застосунок <b>Tailscale</b> (App Store / Google Play) і увійдіть <b>тим самим акаунтом</b>.",
        "Поверніться сюди — з'явиться адреса для телефона."])}`;
  } else if (!r.logged_in) {
    body = `<div class="callout warn">${icon("alert")}<div class="c-body"><div class="c-title">Tailscale встановлено, але не підключено</div>${esc(r.message || "")}<br>Або запустіть <b>tailscale-setup.bat</b>.</div></div>`;
  } else if (!r.serve) {
    body = `<p class="small" style="color:var(--text-2);margin:0">Tailscale працює (${esc(r.dns || r.ip || "")}). Залишилось відкрити застосунок для ваших пристроїв:</p>
      <div class="btn-row" style="margin-top:10px"><button class="btn primary" id="rm-on">${icon("lock")} Увімкнути доступ з телефона</button><button class="btn ghost sm" id="rm-re">${icon("refresh")} Перевірити ще раз</button></div>${hint}${out}`;
  } else {
    body = `<div class="callout ok">${icon("check")}<div class="c-body"><div class="c-title">Доступ увімкнено — лише для ваших пристроїв у Tailscale</div>
        <div class="prompt-box"><code style="font-size:14px">${esc(r.url)}</code><button class="btn sm" id="rm-copy">${icon("copy")} Копіювати</button><a class="btn sm" href="${esc(r.url)}" target="_blank">${icon("external")}</a></div></div></div>
      ${steps(["На телефоні увімкніть Tailscale (той самий акаунт) і відкрийте цю адресу.",
        "Додайте сторінку на головний екран: <b>Android</b> — меню ⋮ → «Додати на головний екран»; <b>iPhone</b> — «Поділитися» → «На екран Додому».",
        "ПК має бути увімкнений, а застосунок запущений. Зручно: <b>create-shortcut.bat</b> → автозапуск, і в налаштуваннях живлення Windows вимкніть сон під час живлення від мережі."])}
      <div class="btn-row" style="margin-top:12px"><button class="btn ghost sm danger" id="rm-off">${icon("x")} Вимкнути доступ</button>${r.port !== 8765 ? `<span class="small" style="color:var(--warn)">Застосунок працює на порту ${r.port}, а не 8765 — після перезапуску може знадобитися натиснути «Увімкнути» знову.</span>` : ""}</div>${out}`;
  }
  box.innerHTML = head + body;
  $("#rm-on") && ($("#rm-on").onclick = async (e) => { e.target.disabled = true; e.target.innerHTML = '<span class="spinner"></span> Налаштовую…'; try { const res = await POST("/api/remote/enable"); loadRemote(res); if (res.ok) toast("Доступ з телефона увімкнено"); } catch (er) { handleErr(er); loadRemote(); } });
  $("#rm-re") && ($("#rm-re").onclick = () => { box.innerHTML = head + '<div class="small muted"><span class="spinner"></span> Перевіряю…</div>'; loadRemote(); });
  $("#rm-off") && ($("#rm-off").onclick = async () => { if (!(await confirmBox("Вимкнути доступ з телефона?", "Застосунок залишиться доступним лише на цьому ПК.", "Вимкнути", true))) return; loadRemote(await POST("/api/remote/disable")); });
  $("#rm-copy") && ($("#rm-copy").onclick = () => copyText(r.url));
}

// ============================================================ global drag & drop
let dragDepth = 0;
const hideOverlay = () => { dragDepth = 0; $("#drop-overlay").hidden = true; };
window.addEventListener("dragenter", (e) => { if (![...(e.dataTransfer?.types || [])].includes("Files")) return; e.preventDefault(); dragDepth++; $("#drop-overlay").hidden = false; });
window.addEventListener("dragleave", () => { if (--dragDepth <= 0) hideOverlay(); });
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => {
  e.preventDefault(); hideOverlay();
  const files = e.dataTransfer?.files; if (!files?.length) return;
  if (S.onGlobalDrop) return S.onGlobalDrop(files);
  const m = location.hash.match(/^#\/lecture\/([^/?]+)/);
  pendingDrop.files = files;
  location.hash = m ? `#/upload?lecture=${m[1]}` : "#/upload";
});
// Вставка скриншотів з буфера (Win+Shift+S → Ctrl+V): на сторінці додавання — у список файлів,
// на сторінці лекції — до цієї лекції, деінде — нова лекція.
let pasteSeq = 0;
window.addEventListener("paste", (e) => {
  if (/INPUT|TEXTAREA/.test(document.activeElement?.tagName)) return;
  const items = [...(e.clipboardData?.items || [])].filter((it) => it.kind === "file" && it.type.startsWith("image/"));
  if (!items.length) return;
  e.preventDefault();
  const d = new Date(), p2 = (n) => String(n).padStart(2, "0");
  const stamp = `${p2(d.getHours())}${p2(d.getMinutes())}${p2(d.getSeconds())}`;
  const files = items.map((it) => {
    const blob = it.getAsFile(); pasteSeq++;
    const ext = (blob.type.split("/")[1] || "png").replace("jpeg", "jpg");
    return new File([blob], `zrzut_${stamp}_${String(pasteSeq).padStart(3, "0")}.${ext}`, { type: blob.type, lastModified: Date.now() });
  });
  toast(`Скріншот додано (${pasteSeq})`, "info", 1500);
  if (S.onGlobalDrop) return S.onGlobalDrop(files);
  const m = location.hash.match(/^#\/lecture\/([^/?]+)/);
  pendingDrop.files = files;
  location.hash = m ? `#/upload?lecture=${m[1]}` : "#/upload";
});
window.addEventListener("beforeunload", (e) => { if (S.uploading || S.dirty) { e.preventDefault(); e.returnValue = ""; } });
window.addEventListener("hashchange", () => { if (!location.hash.startsWith("#/upload")) S.onGlobalDrop = null; if (S.state) route(); });
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); location.hash = "#/search"; }
});

// ============================================================ planner (вільні дні, свята, праця, план дня)
function fmtMins(m) { const h = Math.floor(m / 60), mm = m % 60; return h ? `${h} год${mm ? " " + mm + " хв" : ""}` : `${mm} хв`; }
const PL_SRC = { osrm: "маршрут OSM", estimate: "оцінка за відстанню", manual: "ваш час", default: "типово, адресу не задано", near: "поруч" };
const plLoc = { get() { try { return JSON.parse(sessionStorage.getItem("pl-loc") || "null"); } catch (e) { return null; } },
  set(v) { try { v ? sessionStorage.setItem("pl-loc", JSON.stringify(v)) : sessionStorage.removeItem("pl-loc"); } catch (e) {} } };

async function viewPlanner(q = {}) {
  let weeks = Number(q.weeks) || 4;
  let useDevice = !!plLoc.get(), settingsOpen = false;
  const today = parseDate(S.state.today);
  const monday = new Date(today); monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));

  const load = async () => {
    const loc = useDevice ? plLoc.get() : null;
    const qs = new URLSearchParams({ start: isoDate(monday), days: String(weeks * 7) });
    if (loc) { qs.set("lat", loc.lat); qs.set("lon", loc.lon); }
    return GET(`/api/planner?${qs}`);
  };

  const pill = (w) => `<span class="pl-win ${w.work ? "work" : w.where === "campus" ? "campus" : "short"}" title="${w.work ? "Підходить для праці" : w.where === "campus" ? "Перерва на кампусі — для навчання/карток" : "Коротке вікно"}">${icon(w.where === "campus" ? "pin" : "clock")} ${w.from}–${w.to} · ${fmtMins(w.minutes)}${w.where === "campus" ? " · кампус" : ""}</span>`;
  const kindBadge = (d) => d.holiday ? `<span class="badge pl-hol" title="${esc(d.holiday.pl)}">${icon("sparkles")} Свято: ${esc(d.holiday.uk)}</span>` :
    d.kind === "weekend" ? `<span class="badge">Вихідний</span>` : d.kind === "free" ? `<span class="badge s-done">${icon("check")} Вільний від пар</span>` :
    `<span class="badge">${d.classes.length} ${d.classes.length === 1 ? "заняття" : d.classes.length < 5 ? "заняття" : "занять"}</span>`;
  const travelTxt = (t, modes, mode) => `${t.minutes} хв${t.km ? ` · ${t.km} км` : ""} <span class="muted">(${esc(t.src === "manual" ? PL_SRC.manual : modes[mode].toLowerCase() + ", " + (PL_SRC[t.src] || t.src))})</span>`;

  const dayPlanCard = (d, data) => {
    const p = d.plan, mode = data.settings.planner_mode;
    if (!p) return `<div class="empty" style="padding:14px">${icon("sun")}<b>${d.holiday ? "Свято — пар немає" : "Пар немає"}</b>${d.windows.filter((w) => w.work).map(pill).join(" ") || "Відпочинок"}</div>`;
    const steps = [
      ["moon", p.bed, "Лягти спати", `щоб виспатися ${data.settings.planner_sleep_h} год`],
      ["sun", p.wake, "Підйом", `${data.settings.planner_morning_min} хв на ранок${p.early ? " · <b style='color:var(--warn)'>рано!</b>" : ""}`],
      ["right", p.leave, "Вийти з дому", `дорога ${travelTxt(p.travel_in, data.modes, mode)} + ${data.settings.planner_buffer_min} хв запасу`],
      ["pin", p.first, "Перша пара", `${esc(d.classes[0].subject)} · ${esc(d.classes[0].room || p.first_building)}`],
      ["clock", p.last_end, "Кінець пар", d.classes.length > 1 ? `${d.classes.length} заняття` : ""],
      ["home", p.home, "Удома", `дорога назад ${p.travel_out.minutes} хв`],
    ];
    return `<div class="pl-steps">${steps.map(([ic, t, title, sub]) => `<div class="pl-step">${icon(ic)}<b>${t}</b><div><div>${title}</div><div class="small muted">${sub}</div></div></div>`).join("")}</div>
      ${d.windows.length ? `<div class="pl-wins" style="margin-top:10px">${d.windows.map(pill).join("")}</div>` : ""}`;
  };

  const dayRow = (d, data, best) => {
    const x = parseDate(d.date), isToday = d.date === S.state.today, past = d.date < S.state.today;
    return `<div class="row pl-day ${past ? "past" : ""} ${isToday ? "today" : ""}" id="d-${d.date}">
      <div class="date-box"><div class="d">${x.getDate()}</div><div class="m">${MONTHS[x.getMonth()]}</div></div>
      <div class="body">
        <div class="pl-title"><b>${DAYS[d.weekday]}${isToday ? " · сьогодні" : ""}</b>${kindBadge(d)}${best.has(d.date) ? `<span class="badge s-done" title="Один із найкращих днів для праці">${icon("check")} добрий для праці</span>` : ""}${d.work_minutes ? `<span class="small muted">для праці: <b>${fmtMins(d.work_minutes)}</b></span>` : ""}</div>
        ${d.note ? `<div class="small" style="color:var(--warn)">${icon("info")} ${esc(d.note)}</div>` : ""}
        ${d.classes.length ? `<div class="pl-cls">${d.classes.map((c) => `<span class="pl-cl" style="--c:${c.color}" title="${esc(c.subject_name)} · ${esc(c.room)}">${c.start}–${c.end} <b>${esc(c.subject)}</b> ${c.type}${c.building ? " · " + esc(c.building) : ""}</span>`).join("")}</div>` : ""}
        ${d.plan ? `<div class="small pl-planline">${icon("sun")} підйом <b>${d.plan.wake}</b> · вихід <b>${d.plan.leave}</b> · дорога ${d.plan.travel_in.minutes} хв · удома ~${d.plan.home}</div>` : ""}
        ${d.windows.length ? `<div class="pl-wins">${d.windows.map(pill).join("")}</div>` : ""}
        ${d.windows.map(plTasksHtml).join("")}
      </div></div>`;
  };

  const settingsCard = (s, modes) => {
    const num = (k, label, hint, min, max, step = 5) => `<div class="field"><label>${label}</label><input class="input" type="number" min="${min}" max="${max}" step="${step}" data-pl="${k}" value="${esc(s[k])}">${hint ? `<span class="hint">${hint}</span>` : ""}</div>`;
    return `<details class="card pad pl-settings" ${s.planner_lat == null || settingsOpen ? "open" : ""}><summary><h2 style="display:inline">${icon("settings")} Налаштування планера</h2></summary>
      <div class="field" style="margin-top:14px"><label>Домашня адреса</label>
        <div class="btn-row" style="flex-wrap:nowrap"><input class="input" id="pl-addr" placeholder="напр. ul. Grunwaldzka 10, Wrocław" value="${esc(s.planner_address)}"><button class="btn primary" id="pl-geo">${icon("search")} Знайти</button></div>
        <span class="hint">${s.planner_lat != null ? `${icon("check")} ${esc(s.planner_place)}` : "Адресу шукаємо в OpenStreetMap (Nominatim); зберігається лише на вашому ПК."}</span></div>
      <div class="form-grid" style="margin-top:12px">
        <div class="field"><label>Як добираюся</label><select class="input" data-pl="planner_mode">${Object.entries(modes).map(([k, t]) => `<option value="${k}" ${k === s.planner_mode ? "selected" : ""}>${t}</option>`).join("")}</select>
          <span class="hint">Для трамвая/автобуса час — оцінка; точний перевірте в Jakdojade</span></div>
        ${num("planner_travel_override", "Мій час дороги, хв", "0 — рахувати автоматично", 0, 240)}
        ${num("planner_morning_min", "Ранок до виходу, хв", "душ, сніданок, збори", 0, 240)}
        ${num("planner_buffer_min", "Запас до пари, хв", "знайти аудиторію, затримка трамвая", 0, 60)}
        ${num("planner_sleep_h", "Скільки спати, год", "", 4, 12, 1)}
        ${num("planner_min_block", "Мінімальний блок праці, хв", "коротші вікна — для навчання", 30, 600, 15)}
        <div class="field"><label>Можу працювати з</label><input class="input" type="time" data-pl="planner_work_from" value="${esc(s.planner_work_from)}"></div>
        <div class="field"><label>до</label><input class="input" type="time" data-pl="planner_work_to" value="${esc(s.planner_work_to)}"></div>
      </div>
      <div style="display:flex;flex-direction:column;gap:10px;margin-top:12px">
        <label class="check"><input type="checkbox" data-pl="planner_campus_gaps" ${s.planner_campus_gaps ? "checked" : ""}><div><b>Працюю віддалено між парами</b><span>Перерви на кампусі (з ноутбуком) теж рахувати як час для праці</span></div></label>
        <label class="check"><input type="checkbox" data-pl="planner_weekends" ${s.planner_weekends ? "checked" : ""}><div><b>Можу працювати у вихідні</b><span>Субота й неділя з'являться у вікнах для праці</span></div></label>
      </div></details>`;
  };

  const render = async () => {
    let data;
    try { data = await load(); } catch (e) { setView(errorBox(e)); return; }
    const s = data.settings, days = data.days, best = new Set(data.best);
    const upcoming = days.filter((d) => d.date >= S.state.today);
    const now = new Date(), nowM = now.getHours() * 60 + now.getMinutes();
    let focus = upcoming.find((d) => d.plan && (d.date > S.state.today || minutes(d.plan.leave) > nowM)) || upcoming[0];
    const freeDays = upcoming.filter((d) => !d.classes.length && d.weekday < 5);
    const hols = upcoming.filter((d) => d.holiday);
    const byWeek = [];
    for (let i = 0; i < days.length; i += 7) byWeek.push({ wi: days[i].week, days: days.slice(i, i + 7) });
    const o = data.origin;
    const originTxt = o.src === "device" ? `${icon("pin")} Поточне місце телефона` : o.src === "home" ? `${icon("home")} ${esc(o.place || "Дім")}` : `${icon("alert")} Адресу не задано — дорогу рахую як 30 хв`;
    const noBld = Object.entries(data.buildings).filter(([, b]) => b.src === "campus").map(([k]) => k);

    setView(`
      <div class="page-head"><div><h1>Планер</h1><div class="sub">Вільні дні, свята в Польщі, час для праці та план дня</div></div>
        <div class="btn-row"><div class="seg" id="pl-weeks">${[2, 4, 8, 16].map((w) => `<button data-w="${w}" class="${w === weeks ? "on" : ""}">${w} тиж.</button>`).join("")}</div></div></div>

      <div class="card pad pl-origin" style="margin-bottom:14px">
        <div><div class="label-t">Звідки рахувати дорогу</div><div style="margin-top:4px">${originTxt}</div>
          ${noBld.length ? `<div class="small muted" style="margin-top:4px">${icon("info")} Будинки ${noBld.join(", ")} не знайдено в OpenStreetMap — рахую до центру кампусу (±5 хв).</div>` : ""}</div>
        <div class="seg"><button id="pl-home" class="${!useDevice ? "on" : ""}">${icon("home")} Дім</button><button id="pl-here" class="${useDevice ? "on" : ""}">${icon("pin")} Де я зараз</button></div>
      </div>

      <div class="grid cols-2" style="margin-bottom:14px">
        <div class="card pad"><div class="section-head"><h2>${icon("sun")} ${focus ? (focus.date === S.state.today ? "Сьогодні" : DAYS[focus.weekday] + ", " + fmtDate(focus.date)) : "План дня"}</h2>
          ${focus?.plan ? `<a class="small" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1${o.lat != null ? `&origin=${o.lat},${o.lon}` : ""}&destination=${focus.plan.travel_in.dest ? focus.plan.travel_in.dest.lat + "," + focus.plan.travel_in.dest.lon : data.campus.lat + "," + data.campus.lon}&travelmode=${{ transit: "transit", foot: "walking", bike: "bicycling", car: "driving" }[s.planner_mode]}">${icon("external")} Маршрут</a>` : ""}</div>
          ${focus ? dayPlanCard(focus, data) : `<div class="empty">Немає даних</div>`}</div>
        <div class="card pad"><div class="section-head"><h2>${icon("clock")} Найкращі дні для праці</h2></div>
          ${data.best.length ? `<div class="pl-best">${data.best.map((ds) => { const d = days.find((x) => x.date === ds); return `<a href="#d-${ds}" class="pl-bestrow" data-jump="${ds}"><span><b>${DAYS_SHORT[d.weekday]}, ${fmtDate(ds)}</b>${d.holiday ? ` <span class="small muted">· ${esc(d.holiday.uk)}</span>` : ""}</span><span class="pl-hrs">${fmtMins(d.work_minutes)}</span><div class="small muted" style="grid-column:1/-1">${d.windows.filter((w) => w.work).map((w) => `${w.from}–${w.to}`).join(" і ")}</div></a>`; }).join("")}</div>`
            : `<div class="empty" style="padding:14px">Немає вікон ≥ ${fmtMins(s.planner_min_block)} — зменште мінімальний блок у налаштуваннях</div>`}
          <div class="small muted" style="margin-top:10px">Вільних від пар буднів: <b>${freeDays.length}</b>${hols.length ? ` · свят: <b>${hols.length}</b> (${hols.map((h) => `${parseDate(h.date).getDate()} ${MONTHS[parseDate(h.date).getMonth()]} — ${esc(h.holiday.uk)}`).join("; ")})` : ""}</div></div>
      </div>

      ${settingsCard(s, data.modes)}
      <div class="section"></div>${plUnplacedHtml(data.tasks)}

      ${byWeek.map((w) => `<div class="section-head" style="margin-top:20px"><h2>Тиждень ${w.wi.week} · ${w.wi.label}</h2>
          <span class="small muted">${fmtDate(w.days[0].date)} – ${fmtDate(w.days[w.days.length - 1].date)} · для праці: <b>${fmtMins(w.days.reduce((a, d) => a + d.work_minutes, 0))}</b></span></div>
        <div class="card">${w.days.map((d) => dayRow(d, data, best)).join("")}</div>`).join("")}
      <p class="small muted" style="margin-top:14px">${icon("info")} Свята — дні, вільні від праці за польським законом (включно з Wigilią з 2025 р.). Якщо свято випадає на суботу, роботодавець має дати інший вільний день. Розклад — з USOS, якщо синхронізовано, інакше з тижневого шаблону. Маршрути — OpenStreetMap; час у трамваї/автобусі орієнтовний.</p>`, render);

    $$("#pl-weeks button").forEach((b) => (b.onclick = () => { weeks = Number(b.dataset.w); history.replaceState(null, "", `#/planner?weeks=${weeks}`); render(); }));
    $$("[data-jump]").forEach((a) => (a.onclick = (e) => { e.preventDefault(); const el = $(`#d-${a.dataset.jump}`); if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1600); } }));
    bindPlTasks(render);
    $("#pl-home").onclick = () => { useDevice = false; render(); };
    $("#pl-here").onclick = () => {
      if (!navigator.geolocation) { toast("Цей браузер не дає геолокацію", "err"); return; }
      if (!window.isSecureContext) { toast("Геолокація працює лише через https (адреса Tailscale …ts.net) або на цьому ПК", "err", 6000); return; }
      toast("Визначаю місце…", "info", 2000);
      navigator.geolocation.getCurrentPosition((p) => {
        plLoc.set({ lat: +p.coords.latitude.toFixed(5), lon: +p.coords.longitude.toFixed(5) }); useDevice = true; render();
      }, (e) => toast(e.code === 1 ? "Доступ до місця заборонено в браузері" : "Не вдалося визначити місце", "err"), { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 });
    };
    $("#pl-geo").onclick = async () => {
      const b = $("#pl-geo"); b.disabled = true; b.innerHTML = `<span class="spinner"></span> Шукаю…`;
      try { const r = await POST("/api/planner/geocode", { address: $("#pl-addr").value }); S.state.settings = r.settings; toast(`Знайдено: ${esc(r.place)}`, "ok", 4000); useDevice = false; render(); }
      catch (e) { handleErr(e); b.disabled = false; b.innerHTML = `${icon("search")} Знайти`; }
    };
    $(".pl-settings").ontoggle = (e) => { settingsOpen = e.target.open; };
    $("#pl-addr").onkeydown = (e) => { if (e.key === "Enter") $("#pl-geo").click(); };
    $$("[data-pl]").forEach((i) => (i.onchange = async () => {
      const v = i.type === "checkbox" ? i.checked : i.type === "number" ? Number(i.value) : i.value;
      try { S.state.settings = await PUT("/api/settings", { [i.dataset.pl]: v }); toast("Збережено", "ok", 1200); render(); } catch (e) { handleErr(e); }
    }));
  };
  await render();
}

// ============================================================ boot
(async function boot() {
  for (let i = 0; ; i++) {
    try { await loadBase(); break; }
    catch (e) { setOffline(true); $("#view").innerHTML = `<div class="empty">${icon("refresh")}<b>Підключення до сервера…</b>Переконайтесь, що запущено start.bat</div>`; await new Promise((r) => setTimeout(r, Math.min(5000, 800 * (i + 1)))); }
  }
  setOffline(false);
  // досилаємо шматки запису, що залишились після закриття/перезавантаження сторінки
  try {
    const pend = await rqAll();
    const sess = new Set(pend.filter((o) => o.blob).map((o) => o.lid + "|" + o.sid));
    for (const k of sess) if (!pend.some((o) => o.finish && o.lid + "|" + o.sid === k)) {
      const [lid, sid] = k.split("|"); await rqPut({ k: `${lid}|${sid}|~`, lid, sid, finish: true });
    }
    if (pend.length) { toast("Досилаю збережений запис на ПК…", "info", 4000); recPump(); }
  } catch { }
  await route();
  setTimeout(poll, 3000);
  setupServiceWorker();  // 2.3: офлайн і сповіщення
  flushOfflineAnswers();
})();
