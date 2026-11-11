"use strict";
// ============================================================ 2.10: мова інтерфейсу (українська · English · русский)
// Інтерфейс малюється українською, а цей шар одразу підміняє тексти за словником i18n/<мова>.json.
// Чого немає в словнику, лишається українським — нічого не ламається. Конспекти, нотатки й розшифровки не перекладаються.
// Підключається перед app.js.

const I18N = { lang: "uk", exact: new Map(), pats: [], obs: null, v: 2 };
const I18N_CYR = /[а-яіїєґА-ЯІЇЄҐ]/;
const I18N_SKIP = ".md, .transcript, textarea, input, select.no-i18n, code, pre, .chat-j, .mono, [data-noi18n]";
const I18N_ATTRS = ["placeholder", "title", "aria-label"];

function i18nBuild(dict) {
  I18N.exact = new Map(); I18N.pats = [];
  for (const [k, v] of Object.entries(dict)) {
    if (!/\{\d+\}/.test(k)) { I18N.exact.set(k, v); continue; }
    const parts = k.split(/\{\d+\}/);
    const lit = parts.reduce((a, b) => (b.length > a.length ? b : a), "");
    if (lit.trim().length < 2) continue;  // шаблон майже без тексту — надто загальний
    const rx = new RegExp("^" + parts.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("(.+?)") + "$");
    I18N.pats.push({ rx, lit, v });
  }
  I18N.pats.sort((a, b) => b.lit.length - a.lit.length);  // спершу найконкретніші
}

function i18nText(s) {
  const norm = s.replace(/\s+/g, " ").trim();
  if (!norm || !I18N_CYR.test(norm)) return null;
  let out = I18N.exact.get(norm);
  if (out == null) {
    for (const p of I18N.pats) {
      if (!norm.includes(p.lit)) continue;
      const m = p.rx.exec(norm);
      if (m) { out = p.v.replace(/\{(\d+)\}/g, (_, i) => { const g = m[+i + 1] || ""; return i18nText(g) ?? g; }); break; }
    }
  }
  if (out == null) {  // дати й дрібниці: «23 жовтня», «пн, 3 лист.» — лише якщо перекладено КОЖНЕ слово, інакше вийде суміш мов
    let miss = false;
    out = norm.replace(/[а-яіїєґА-ЯІЇЄҐ'’]+\.?/g, (w) => { const t = I18N.exact.get(w) ?? I18N.exact.get(w.replace(/\.$/, "")); if (t == null) miss = true; return t ?? w; });
    if (miss) return null;
  }
  const lead = s.match(/^\s*/)[0], tail = s.match(/\s*$/)[0];
  return lead + out + tail;
}

function i18nNode(root) {
  if (I18N.lang === "uk" || !root) return;
  if (root.nodeType === 3) return i18nTextNode(root);
  if (root.nodeType !== 1) return;
  const field = (n) => n.matches("textarea, input");  // у полях вміст — студента, але підказку (placeholder) перекладаємо
  if (root.closest && root.closest(I18N_SKIP) && !field(root)) return;
  const tw = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.nodeType === 1 && n.matches(I18N_SKIP) && !field(n) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT) });
  for (let n = root; n; n = tw.nextNode()) {
    if (n.nodeType === 3) { i18nTextNode(n); continue; }
    for (const a of I18N_ATTRS) {
      const v = n.getAttribute(a);
      if (v && I18N_CYR.test(v)) { const t = i18nText(v); if (t != null) n.setAttribute(a, t); }
    }
  }
}

function i18nTextNode(n) {
  if (n.__i18n === n.data || !I18N_CYR.test(n.data)) return;
  const p = n.parentElement;
  if (p && p.closest(I18N_SKIP)) return;
  const t = i18nText(n.data);
  if (t != null) { n.__i18n = t; n.data = t; }
}

async function i18nSet(lang) {
  lang = ["uk", "en", "ru"].includes(lang) ? lang : "uk";
  const was = I18N.lang;
  I18N.lang = lang;
  document.documentElement.lang = lang;
  if (lang === "uk") {
    if (I18N.obs) { I18N.obs.disconnect(); I18N.obs = null; }
    if (was !== "uk") location.reload();  // повернути оригінальні тексти найпростіше перезавантаженням
    return;
  }
  try {
    i18nBuild(await (await fetch(`/static/i18n/${lang}.json?v=${I18N.v}`)).json());
  } catch { I18N.lang = "uk"; return; }
  if (!I18N.obs) {
    I18N.obs = new MutationObserver((ms) => {
      for (const m of ms) {
        if (m.type === "characterData") i18nTextNode(m.target);
        else if (m.type === "attributes") i18nNode(m.target);
        else m.addedNodes.forEach(i18nNode);
      }
    });
    I18N.obs.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: I18N_ATTRS });
  }
  i18nNode(document.body);
  if (lang === "en") {  // по-російськи назва та сама — «Конспект»
    document.title = document.title.replace("Конспект", "Konspekt").replace("БЕТА", "BETA");
    $$(".brand-name").forEach((b) => (b.textContent = "Konspekt"));
  }
}

// перемикач у Налаштуваннях: прапор України, Великої Британії; для російської — сірий прямокутник без прапора
const LANG_FLAGS = {
  uk: `<span class="flag" style="background:linear-gradient(#0057b7 50%,#ffd700 50%)"></span>`,
  en: `<svg class="flag" viewBox="0 0 60 30" aria-hidden="true"><clipPath id="fl-uk"><path d="M0,0v30h60V0z"/></clipPath><g clip-path="url(#fl-uk)"><path d="M0,0v30h60V0z" fill="#012169"/><path d="M0,0 60,30M60,0 0,30" stroke="#fff" stroke-width="6"/><path d="M0,0 60,30M60,0 0,30" stroke="#C8102E" stroke-width="3"/><path d="M30,0v30M0,15h60" stroke="#fff" stroke-width="10"/><path d="M30,0v30M0,15h60" stroke="#C8102E" stroke-width="6"/></g></svg>`,
  ru: `<span class="flag" style="background:#9ca3af"></span>`,
};
const LANG_NAMES = { uk: "Українська", en: "English", ru: "Русский" };

function langPickerHtml(cur) {
  return `<div class="seg lang-pick" data-noi18n>${Object.keys(LANG_NAMES).map((l) => `<button data-uilang="${l}" class="${cur === l ? "on" : ""}">${LANG_FLAGS[l]} ${LANG_NAMES[l]}</button>`).join("")}</div>`;
}
function bindLangPicker() {
  $$("[data-uilang]").forEach((b) => (b.onclick = async () => {
    const l = b.dataset.uilang;
    try { S.state.settings = await PUT("/api/settings", { ui_language: l }); } catch (e) { return handleErr(e); }
    $$("[data-uilang]").forEach((x) => x.classList.toggle("on", x.dataset.uilang === l));
    i18nSet(l);
  }));
}
