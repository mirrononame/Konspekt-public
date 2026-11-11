"use strict";
// ============================================================ НАВЧАННЯ 2.0
// Картки 6 типів (mcq, cloze, tf, order, code, flip), FSRS з 4 кнопками, режими «Сьогодні», «Тест до колоквіуму»,
// «Бліц», «Складні»; свайпи на телефоні, клавіші на ПК; прогрес, керування картками.
// Файл підключається перед app.js і використовує його помічники ($, GET, icon, esc…) лише під час виклику.

const RATE = { 1: "Знову", 2: "Важко", 3: "Добре", 4: "Легко" };
const RATE_CLS = { 1: "r-again", 2: "r-hard", 3: "r-good", 4: "r-easy" };
const TYPE_LABEL = { mcq: "Вибір", cloze: "Впиши", tf: "Правда / ні", order: "Порядок", code: "Код", flip: "Картка" };
const MODE_LABEL = { today: "Сьогодні", test: "Тест до колоквіуму", blitz: "Бліц", hard: "Складні", all: "Усі картки", new: "Нові" };
const LETTERS = "ABCDEF";

// ---------- перевірка відповідей (без регістру/діакритики, з допуском описок)
function normAns(s) {
  return String(s ?? "").toLowerCase().replace(/ł/g, "l").normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[„”"'`«»]/g, "").replace(/[.,;:!?()]+/g, " ").replace(/\s+/g, " ").trim();
}
function lev(a, b) {
  if (a === b) return 0;
  if (Math.abs(a.length - b.length) > 3) return 99;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    prev = cur;
  }
  return prev[b.length];
}
// → { ok: bool, typo: bool }
function checkText(given, answers, { code = false } = {}) {
  const g0 = String(given || "").trim();
  if (!g0) return { ok: false, typo: false };
  const list = answers.filter(Boolean);
  if (code) {
    const sq = (s) => String(s).replace(/\s+/g, " ").replace(/\s*([;,(){}\[\]=+\-*/<>])\s*/g, "$1").trim();
    if (list.some((a) => sq(a) === sq(g0))) return { ok: true, typo: false };
    if (list.some((a) => sq(a).toLowerCase().replace(/;$/, "") === sq(g0).toLowerCase().replace(/;$/, ""))) return { ok: true, typo: true };
    return { ok: false, typo: false };
  }
  const g = normAns(g0);
  for (const a of list) if (normAns(a) === g) return { ok: true, typo: false };
  for (const a of list) {
    const n = normAns(a), tol = n.length <= 4 ? 0 : n.length <= 8 ? 1 : 2;
    if (tol && lev(n, g) <= tol) return { ok: true, typo: true };
  }
  return { ok: false, typo: false };
}

// ---------- текст картки: markdown + код + таблиці + прості формули ($x^2$, $a_i$)
function richText(t) {
  let html = renderMarkdown(String(t || ""));
  html = html.replace(/\$([^$\n]{1,200})\$/g, (_, f) => `<span class="math">${f
    .replace(/\^\{([^}]*)\}/g, "<sup>$1</sup>").replace(/\^([\w+\-−]+)/g, "<sup>$1</sup>")
    .replace(/_\{([^}]*)\}/g, "<sub>$1</sub>").replace(/_(\w+)/g, "<sub>$1</sub>")
    .replace(/\\cdot/g, "·").replace(/\\times/g, "×").replace(/\\le/g, "≤").replace(/\\ge/g, "≥").replace(/\\neq/g, "≠")
    .replace(/\\to/g, "→").replace(/\\sum/g, "∑").replace(/\\sqrt/g, "√").replace(/\\infty/g, "∞").replace(/\\pi/g, "π")}</span>`);
  return html;
}
const clozeHtml = (q, fill = null) => richText(q).replace(/_{3,}|\{\{[^}]*\}\}/, fill == null ? `<span class="cloze-gap">_____</span>` : `<span class="cloze-fill">${esc(fill)}</span>`);
const codeBlock = (c) => `<pre class="card-code"><code>${esc(c.code || "")}</code></pre>`;
const srcLink = (c) => {
  const s = c.source || {};
  if (!c.lecture_id) return "";
  const t = s.sec != null ? `?t=${s.sec}` : "";
  const what = s.t ? `${icon("play")} ${esc(s.t)}` : s.section ? `§ ${esc(s.section)}` : "конспект";
  return `<a class="src-link" href="#/lecture/${enc(c.lecture_id)}${t}" title="Відкрити джерело">${esc(c.lecture_title || fmtDate(c.date))} · ${what}</a>`;
};

// ============================================================ сторінка «Навчання»
async function viewStudy(q) {
  if (q.manage) return viewStudyManage(q);
  const filt = { subject: q.subject || "", lecture: q.lecture || "" };
  const render = async () => {
    document.body.classList.remove("study-on");
    const qs = filt.lecture ? "?lecture=" + enc(filt.lecture) : filt.subject ? "?subject=" + enc(filt.subject) : "";
    const [data, prog] = await Promise.all([GET("/api/study" + qs), GET("/api/study/progress")]);
    const cards = data.cards, all = data.stats;
    const due = cards.filter((c) => c.is_due).length, fresh = cards.filter((c) => c.is_new).length;
    const hard = cards.filter((c) => c.leech || (c.rating === 1 && !c.is_new)).length;
    const todayN = due + Math.min(fresh, prog.new_left);
    const mins = Math.max(1, Math.round((due * 12 + Math.min(fresh, prog.new_left) * 25) / 60));
    const autoN = cards.filter((c) => c.type !== "flip").length;
    const blitzN = cards.filter((c) => ["tf", "mcq", "cloze"].includes(c.type)).length;
    const lecTitle = filt.lecture && cards[0] ? (cards[0].lecture_title || cards[0].date) : "";
    const simpler = cards.filter((c) => c.simpler && c.explain_pending === false).slice(0, 3);
    const pending = cards.filter((c) => c.explain_pending).length;
    const sub = prog.subjects;
    const tempo = prog.tempo.filter((t) => !filt.subject || t.subject_id === filt.subject);
    const soonTest = tempo.filter((t) => t.days_left <= 7).sort((a, b) => a.days_left - b.days_left)[0];  // 2.2: тест — на видноті лише перед колоквіумом
    setView(`
      <div class="page-head"><div><h1>Навчання</h1><div class="sub">${prog.streak ? `<b class="streak">🔥 ${prog.streak} ${plural(prog.streak, "день", "дні", "днів")} поспіль</b> · ` : ""}${prog.learned} з ${prog.total} карток вивчено · сьогодні ${prog.today.n} повторень</div></div>
        </div>
      <div class="chips" style="margin-bottom:16px">
        <button class="cand ${!filt.subject && !filt.lecture ? "on" : ""}" data-sf="" style="--c:var(--accent)"><span class="bar"></span><span><span class="t">Усі предмети</span><br><span class="m">${all.total.due} до повторення · ${all.total.total}</span></span></button>
        ${S.schedule.subjects.filter((s) => all.subjects[s.id]).map((s) => `<button class="cand ${filt.subject === s.id && !filt.lecture ? "on" : ""}" data-sf="${s.id}" style="--c:${s.color}"><span class="bar"></span><span><span class="t">${esc(s.short)}</span><br><span class="m">${all.subjects[s.id].due} до повторення · ${all.subjects[s.id].total}</span></span></button>`).join("")}
      </div>
      ${filt.lecture ? `<div class="callout info" style="margin-bottom:14px">${icon("info")}<div class="c-body">Лише картки лекції «${esc(lecTitle)}». <a href="#/study">Показати всі</a></div></div>` : ""}
      ${cards.length ? `
      <div class="study-hero card">
        <div class="sh-main"><div class="label-t">Сьогодні</div>
          <div class="sh-n">${todayN ? `${due} ${plural(due, "повторення", "повторення", "повторень")} + ${Math.min(fresh, prog.new_left)} нових` : "На сьогодні все ✓"}</div>
          <div class="small muted">${todayN ? `≈ ${mins} хв · ліміт нових ${prog.new_per_day}/день (лишилось ${prog.new_left})` : `Завтра: ${prog.forecast.tomorrow_reviews} повторень + до ${prog.forecast.tomorrow_new} нових`}</div></div>
        <button class="btn primary lg" data-mode="today" ${todayN ? "" : "disabled"}>${icon("refresh")} Почати</button>
      </div>
      ${soonTest && autoN ? `<div class="mode-grid"><button class="mode-tile" data-mode="test">${icon("check")}<b>Тест до колоквіуму</b><span>${esc(soonTest.title)} — через ${soonTest.days_left} ${plural(soonTest.days_left, "день", "дні", "днів")} · 20 завдань</span></button></div>` : ""}
      <details class="more-modes section"><summary class="small">${icon("more")} Ще режими й керування</summary>
      <div class="mode-grid" style="margin-top:10px">
        ${soonTest ? "" : `<button class="mode-tile" data-mode="test" ${autoN ? "" : "disabled"}>${icon("check")}<b>Тест до колоквіуму</b><span>20 завдань · оцінка · помилки з посиланнями</span></button>`}
        <button class="mode-tile" data-mode="blitz" ${blitzN >= 3 ? "" : "disabled"}>${icon("clock")}<b>Бліц 60 с</b><span>правда чи ні — якнайбільше</span></button>
        <button class="mode-tile" data-mode="hard" ${hard ? "" : "disabled"}>${icon("alert")}<b>Складні${hard ? ` (${hard})` : ""}</b><span>картки, які постійно забуваєте</span></button>
        <button class="mode-tile" data-mode="all">${icon("list")}<b>Усі картки (${cards.length})</b><span>вільне повторення</span></button>
      </div>
      <div class="btn-row" style="margin-top:10px"><button class="btn sm" id="st-add">${icon("plus")} Своя картка</button><a class="btn sm ghost" href="#/study?manage=1${filt.subject ? "&subject=" + enc(filt.subject) : ""}">${icon("edit")} Керувати картками</a></div>
      </details>
      ${simpler.length || pending ? `<div class="card pad section"><h3>${icon("sparkles")} «Поясни простіше»</h3>${pending ? `<div class="small muted">${pending} ${plural(pending, "питання чекає", "питання чекають", "питань чекають")} на Claude — відповідь з'явиться на картці.</div>` : ""}
        ${simpler.map((c) => `<div class="simpler-row"><b>${esc(c.q.slice(0, 120))}</b><div class="small">${richText(c.simpler)}</div></div>`).join("")}</div>` : ""}
      <div class="grid cols-2 section">
        <div class="card pad"><div class="section-head"><h2>${icon("calendar")} Активність</h2><span class="small muted">тиждень: ${prog.week.n} повт. · ${prog.week.min} хв</span></div>
          ${heatmapHtml(prog.heatmap)}
          <div class="fc-row"><div><b>${prog.forecast.tomorrow_reviews}</b><span>повторень завтра</span></div><div><b>${prog.forecast.tomorrow_new}</b><span>нових завтра</span></div><div><b>${prog.streak}</b><span>серія днів</span></div></div></div>
        <div class="card pad"><h2>${icon("book")} Вивчено по предметах</h2>
          ${S.schedule.subjects.filter((s) => sub[s.id]).map((s) => { const x = sub[s.id]; const pl = (n) => (100 * n / Math.max(1, x.total)).toFixed(1);
            return `<div class="lp-row"><span class="subj-chip" style="--c:${s.color}">${esc(s.short)}</span><div class="lp-bar" title="вивчено ${x.learned} · вчу ${x.learning} · нові ${x.new}"><i class="l" style="width:${pl(x.learned)}%"></i><i class="m" style="width:${pl(x.learning)}%"></i></div><span class="small muted">${x.learned}/${x.total}</span></div>`; }).join("") || '<div class="small muted">Ще немає карток</div>'}
          <div class="small muted" style="margin-top:8px"><i class="lg-dot l"></i> вивчено (інтервал ≥ 3 тижні) <i class="lg-dot m"></i> вчу</div></div>
      </div>
      ${tempo.length ? `<div class="card pad section"><h2>${icon("clock")} Темп до колоквіумів</h2><div class="list">${tempo.map((t) => `<div class="row" style="padding:8px 2px"><div class="body"><div class="title">${t.subject ? `<span class="subj-chip" style="--c:${subjById(t.subject_id)?.color || "#94a3b8"}">${esc(t.subject)}</span> ` : ""}${esc(t.title)}</div>
          <div class="meta">через ${t.days_left} ${plural(t.days_left, "день", "дні", "днів")} · нових карток: ${t.new} · слабких: ${t.weak}</div></div>
          <div class="right"><span class="badge ${t.ok ? "s-done" : "s-error"}">${t.per_day ? `${t.per_day} нових/день` : "усе почато ✓"}</span></div></div>`).join("")}</div>
        <div class="small muted" style="margin-top:6px">Колоквіуми, екзамени й тести беруться з «Дедлайнів» (додайте вручну, якщо їх немає з ePortalu).</div></div>` : ""}
      ${prog.tests.length ? `<div class="card pad section"><h3>Останні тести</h3><div class="chips">${prog.tests.slice(0, 6).map((t) => `<span class="badge">${esc(subjById(t.subject_id)?.short || "усі")} · ${t.score}/${t.total} · ${fmtDate(t.at.slice(0, 10))}</span>`).join("")}</div></div>` : ""}
      <div class="small muted section">Клавіші: <b>Пробіл</b> — показати відповідь, <b>1–4</b> — Знову / Важко / Добре / Легко, <b>Enter</b> — перевірити / рекомендована оцінка, <b>H</b> — підказка. На телефоні: тап — перевернути, свайп ← знову, → добре, ↑ легко.</div>` :
      `<div class="card"><div class="empty">${icon("book")}<b>Карток ще немає</b>Claude додає завдання до кожного нового конспекту. Для старих конспектів натисніть «Переробити конспект» або додайте свою картку.</div></div>`}`, render);
    $$("[data-sf]").forEach((b) => (b.onclick = () => { filt.subject = b.dataset.sf; filt.lecture = ""; history.replaceState(null, "", "#/study" + (filt.subject ? "?subject=" + filt.subject : "")); render(); }));
    $$("[data-mode]").forEach((b) => (b.onclick = () => startSession(b.dataset.mode, filt, render)));
    $("#st-add") && ($("#st-add").onclick = () => customCardModal({ subject_id: filt.subject }).then((ok) => ok && render()));
  };
  await render();
  if (q.start) startSession(q.start, filt, render);
}

function plural(n, one, few, many) {
  const a = Math.abs(n) % 100, b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b === 1) return one;
  if (b >= 2 && b <= 4) return few;
  return many;
}

function heatmapHtml(days) {
  const max = Math.max(1, ...days.map((d) => d.n));
  const lvl = (n) => (n ? Math.min(4, Math.ceil((4 * n) / max)) : 0);
  const weeks = [];
  for (let i = 0; i < days.length; i += 7) weeks.push(days.slice(i, i + 7));
  return `<div class="heat" role="img" aria-label="Календар активності">${weeks.map((w) => `<div class="hw">${w.map((d) => `<i class="h${lvl(d.n)}" title="${fmtDate(d.date)}: ${d.n} повторень${d.min ? ", " + d.min + " хв" : ""}"></i>`).join("")}</div>`).join("")}</div>`;
}

// ============================================================ сесія
let SS = null; // поточна сесія
async function startSession(mode, filt, back) {
  const qs = new URLSearchParams({ mode });
  if (filt.lecture) qs.set("lecture", filt.lecture); else if (filt.subject) qs.set("subject", filt.subject);
  let subj = filt.subject;
  if (mode === "test" && !filt.subject && !filt.lecture) {
    const r = await modal({ title: "Тест до колоквіуму", okText: "Почати", body: `<p class="small muted">20 завдань з автоматичною перевіркою. Наприкінці — оцінка й список помилок із посиланнями на джерело.</p>
      <div class="field"><label>Предмет</label><select class="input" name="subject"><option value="">Усі предмети</option>${S.schedule.subjects.map((s) => `<option value="${s.id}">${esc(s.short)} — ${esc(s.name)}</option>`).join("")}</select></div>` });
    if (!r) return;
    subj = r.subject; if (subj) qs.set("subject", subj);
  }
  let data;
  try { data = await GET("/api/study/session?" + qs); } catch (e) { return handleErr(e); }
  if (!data.cards.length) return toast("Немає карток для цього режиму", "info");
  SS = { mode, subject: subj || "", cards: data.cards, i: 0, graded: data.graded, back, filt, t0: Date.now(), tCard: Date.now(),
    stats: { 1: 0, 2: 0, 3: 0, 4: 0 }, correct: 0, wrong: 0, mistakes: [], done: 0, seen: new Set(), st: null, seconds: data.seconds || 0 };
  document.body.classList.add("study-on");
  document.addEventListener("keydown", ssKey);
  window.addEventListener("hashchange", ssLeave);
  if (mode === "blitz") return blitzStart();
  drawCard();
}
function ssLeave() { if (!location.hash.startsWith("#/study")) ssEnd(true); }
function ssEnd(silent) {
  document.removeEventListener("keydown", ssKey);
  window.removeEventListener("hashchange", ssLeave);
  document.body.classList.remove("study-on");
  if (SS?.timer) clearInterval(SS.timer);
  const back = SS?.back; SS = null;
  if (!silent && back) back();
}

const cur = () => SS && SS.cards[SS.i];
function newState(c) {
  const st = { shown: false, answered: false, ok: null, typo: false, hints: 0, pick: null, input: "", order: [], suggest: 3 };
  if (c.type === "order") st.shuffled = shuffleKeep(c.steps.map((s, i) => i));
  if (c.type === "mcq") st.optOrder = c.options.map((_, i) => i); // порядок варіантів як у Claude (A–D)
  return st;
}
function shuffleKeep(a) {
  const b = a.slice();
  for (let t = 0; t < 6; t++) {
    for (let i = b.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [b[i], b[j]] = [b[j], b[i]]; }
    if (b.some((x, i) => x !== i)) break;
  }
  return b;
}

function drawCard() {
  const c = cur();
  if (!c) return summary();
  if (!SS.st) { SS.st = newState(c); SS.tCard = Date.now(); }
  const st = SS.st, total = SS.cards.length, test = SS.mode === "test";
  const body = cardBody(c, st);
  const showRate = SS.graded && (st.answered || st.shown);
  const next = c.next || {};
  setView(`<div class="study-wrap">
    <div class="ss-top"><button class="btn ghost sm" id="ss-exit">${icon("x")} <span class="hide-sm">Завершити</span></button>
      <span class="ss-mode">${esc(MODE_LABEL[SS.mode] || "")}</span><span style="flex:1"></span><span class="small muted">${Math.min(SS.i + 1, total)} / ${total}</span></div>
    <div class="progress ss-prog"><i style="width:${(SS.i / total) * 100}%"></i></div>
    <div class="flash-card ${st.answered || st.shown ? "is-back" : ""} ${st.ok === true ? "ok" : st.ok === false ? "bad" : ""}" id="fc" style="--c:${c.color}">
      <div class="fc-meta"><span class="subj-chip" style="--c:${c.color}">${esc(c.subject || "—")}</span><span class="badge">${TYPE_LABEL[c.type]}</span>
        ${c.important ? `<span class="badge s-error" title="Важливо на іспит">★ іспит</span>` : ""}${c.is_new ? '<span class="badge s-transcribing">нова</span>' : ""}${c.custom ? '<span class="badge">моя</span>' : ""}
        <span style="flex:1"></span>${(c.hint || []).length && !st.answered && !st.shown ? `<button class="btn ghost sm" id="ss-hint" title="Підказка (H)">${icon("info")} Підказка${c.hint.length > 1 ? ` ${st.hints}/${c.hint.length}` : ""}</button>` : ""}
        <button class="btn ghost icon sm" id="ss-menu" title="Дії з карткою">${icon("more")}</button></div>
      <div class="fc-inner">${body}</div>
      ${st.hints ? `<div class="fc-hints">${c.hint.slice(0, st.hints).map((h) => `<div>${icon("info")} ${richText(h)}</div>`).join("")}</div>` : ""}
      ${(st.answered || st.shown) ? backExtras(c, st) : ""}
    </div>
    <div class="ss-actions" id="ss-actions">${actionsHtml(c, st, showRate, next, test)}</div>
  </div>`);
  bindCard(c, st);
}

function cardBody(c, st) {
  const back = st.answered || st.shown;
  switch (c.type) {
    case "mcq":
      return `<div class="fc-q">${richText(c.q)}</div>${c.code ? codeBlock(c) : ""}<div class="mcq">${st.optOrder.map((oi, k) => {
        const cls = back ? (oi === c.correct ? "right" : oi === st.pick ? "wrong" : "dim") : "";
        return `<button class="opt ${cls}" data-opt="${oi}" ${back ? "disabled" : ""}><span class="ol">${LETTERS[k]}</span><span class="ot">${richText(c.options[oi])}</span></button>`;
      }).join("")}</div>`;
    case "cloze":
      return `<div class="fc-q">${back ? clozeHtml(c.q, c.answer) : clozeHtml(c.q)}</div>
        ${back ? (st.input ? `<div class="your ${st.ok ? "ok" : "bad"}">Ваша відповідь: <b>${esc(st.input)}</b>${st.typo ? " — зараховано з опискою" : ""}</div>` : "")
          : `<div class="ans-row"><input class="input" id="ss-in" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="Впишіть слово…" value="${esc(st.input)}"><button class="btn primary" id="ss-check">Перевірити</button></div>`}`;
    case "code":
      return `<div class="fc-q">${richText(c.q)}</div>${codeBlock(c)}
        ${back ? `<div class="your ${st.ok ? "ok" : "bad"}">${st.input ? `Ваша відповідь: <code>${esc(st.input)}</code>${st.typo ? " — майже (регістр/крапка з комою)" : ""}<br>` : ""}Правильно: <code>${esc(c.answer)}</code></div>`
          : `<div class="ans-row"><input class="input mono" id="ss-in" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="${c.mode === "complete" ? "Допишіть рядок…" : "Що виведе програма?"}" value="${esc(st.input)}"><button class="btn primary" id="ss-check">Перевірити</button></div>`}`;
    case "tf":
      return `<div class="fc-q">${richText(c.q)}</div>${c.code ? codeBlock(c) : ""}
        <div class="tf-row">${[true, false].map((v) => `<button class="opt tf ${back ? (v === c.answer ? "right" : v === st.pick ? "wrong" : "dim") : ""}" data-tf="${v}" ${back ? "disabled" : ""}>${v ? "Правда" : "Неправда"}</button>`).join("")}</div>`;
    case "order": {
      const left = st.shuffled.filter((i) => !st.order.includes(i));
      return `<div class="fc-q">${richText(c.q)}</div>
        ${back ? `<ol class="order-res">${c.steps.map((s, i) => { const okPos = st.order[i] === i; return `<li class="${okPos ? "right" : "wrong"}">${richText(s)}${!okPos && st.order.length ? `<span class="small muted"> (у вас: №${st.order.indexOf(i) + 1})</span>` : ""}</li>`; }).join("")}</ol>`
          : `<div class="small muted" style="margin:6px 0">Натискайте кроки в правильному порядку:</div>
          <ol class="order-pick">${st.order.map((i) => `<li><button class="opt picked" data-unpick="${i}">${richText(c.steps[i])}</button></li>`).join("")}</ol>
          <div class="order-pool">${left.map((i) => `<button class="opt" data-pick="${i}">${richText(c.steps[i])}</button>`).join("")}</div>`}`;
    }
    default: // flip
      return `<div class="flip3d ${back ? "flipped" : ""}"><div class="face front"><div class="fc-q">${richText(c.q)}</div>${c.code ? codeBlock(c) : ""}${back ? "" : `<div class="tap-hint">${icon("refresh")} натисніть, щоб перевернути</div>`}</div>
        <div class="face backf"><div class="fc-q small-q">${richText(c.q)}</div><div class="fc-a">${richText(c.a || "—")}</div></div></div>`;
  }
}

function backExtras(c, st) {
  const parts = [];
  if (c.type === "mcq" && st.pick != null && st.pick !== c.correct && c.traps?.[st.pick]) parts.push(`<div class="trap">${icon("alert")} <b>Пастка:</b> ${richText(c.traps[st.pick])}</div>`);
  if (c.type !== "flip" && c.a && !["mcq", "cloze", "code"].includes(c.type)) parts.push(`<div class="fc-a">${richText(c.a)}</div>`);
  if (c.explain) parts.push(`<div class="explain">${richText(c.explain)}</div>`);
  if (c.why) parts.push(`<div class="explain"><b>Чому:</b> ${richText(c.why)}</div>`);
  if (c.simpler) parts.push(`<div class="simpler">${icon("sparkles")} <b>Простіше:</b> ${richText(c.simpler)}</div>`);
  else if (c.explain_pending) parts.push(`<div class="small muted">${icon("clock")} «Поясни простіше» — чекає на Claude</div>`);
  const src = srcLink(c);
  if (src) parts.push(`<div class="fc-src">${src}</div>`);
  return parts.length ? `<div class="fc-back">${parts.join("")}</div>` : "";
}

function actionsHtml(c, st, showRate, next, test) {
  if (SS.mode === "test") {
    if (!(st.answered || st.shown)) return c.type === "flip" ? `<button class="btn primary lg wide" id="ss-show">Показати відповідь <kbd>␣</kbd></button>` : `<div class="rate-row skip"><button class="btn ghost" id="ss-show">Не знаю</button></div>`;
    if (c.type === "flip" && st.ok == null) return `<div class="rate-row two"><button class="btn lg rate r-again" data-self="0">${icon("x")} Не знав</button><button class="btn lg rate r-good" data-self="1">${icon("check")} Знав</button></div>`;
    return `<button class="btn primary lg wide" id="ss-next">Далі <kbd>Enter</kbd></button>`;
  }
  if (!showRate) {
    if (c.type === "flip") return `<button class="btn primary lg wide" id="ss-show">Показати відповідь <kbd>␣</kbd></button>`;
    return `<div class="rate-row skip"><button class="btn ghost" id="ss-show">Не знаю — показати відповідь</button></div>`;
  }
  return `<div class="rate-row">${[1, 2, 3, 4].map((g) => `<button class="btn lg rate ${RATE_CLS[g]} ${st.suggest === g && (st.answered) ? "sugg" : ""}" data-rate="${g}"><b>${RATE[g]}</b><span>${esc(next[g] || "")}</span><kbd>${g}</kbd></button>`).join("")}</div>
    <div class="swipe-hint small muted">← знову · → добре · ↑ легко</div>`;
}

function reveal(ok, extra = {}) {
  const c = cur(), st = SS.st;
  Object.assign(st, extra, { answered: true, ok });
  st.suggest = ok === false ? 1 : st.hints || st.typo ? 2 : 3;
  if (SS.mode === "test" && ok != null) testMark(c, ok);
  drawCard();
}
function testMark(c, ok) { if (ok) SS.correct++; else { SS.wrong++; SS.mistakes.push(c); } }

function bindCard(c, st) {
  $("#ss-exit").onclick = () => (SS.done || SS.correct + SS.wrong ? summary() : ssEnd());
  $("#ss-hint") && ($("#ss-hint").onclick = () => { st.hints = Math.min(c.hint.length, st.hints + 1); drawCard(); });
  $("#ss-menu").onclick = () => cardMenu(c);
  $("#ss-show") && ($("#ss-show").onclick = () => showAnswer());
  $("#ss-next") && ($("#ss-next").onclick = () => nextCard());
  $$("[data-self]").forEach((b) => (b.onclick = () => { const ok = b.dataset.self === "1"; st.ok = ok; testMark(c, ok); nextCard(); }));
  $$("[data-rate]").forEach((b) => (b.onclick = () => rate(+b.dataset.rate)));
  $$("[data-opt]").forEach((b) => (b.onclick = () => { const i = +b.dataset.opt; reveal(i === c.correct, { pick: i }); }));
  $$("[data-tf]").forEach((b) => (b.onclick = () => { const v = b.dataset.tf === "true"; reveal(v === c.answer, { pick: v }); }));
  $$("[data-pick]").forEach((b) => (b.onclick = () => { st.order.push(+b.dataset.pick); if (st.order.length === c.steps.length) return reveal(st.order.every((x, i) => x === i)); drawCard(); }));
  $$("[data-unpick]").forEach((b) => (b.onclick = () => { st.order = st.order.filter((x) => x !== +b.dataset.unpick); drawCard(); }));
  const inp = $("#ss-in");
  if (inp) {
    inp.oninput = () => (st.input = inp.value);
    const go = () => { const v = inp.value.trim(); if (!v) return; const r = checkText(v, [c.answer, ...(c.accept || [])], { code: c.type === "code" }); reveal(r.ok, { input: v, typo: r.typo }); };
    $("#ss-check").onclick = go;
    inp.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); go(); } };
    if (matchMedia("(pointer:fine)").matches) inp.focus();
  }
  const fc = $("#fc");
  if (c.type === "flip" && !st.shown) fc.querySelector(".flip3d")?.addEventListener("click", () => showAnswer());
  if (SS.graded && (st.shown || st.answered)) bindSwipe(fc, (g) => rate(g));
}

function showAnswer() {
  const c = cur(), st = SS.st;
  if (st.shown || st.answered) return;
  st.shown = true;
  if (c.type !== "flip") { st.ok = false; st.answered = true; st.suggest = 1; if (SS.mode === "test") testMark(c, false); }
  drawCard();
}

async function rate(g) {
  const c = cur(), st = SS.st;
  if (!c || !SS.graded || !(st.shown || st.answered)) return;
  const ms = Date.now() - SS.tCard;
  SS.stats[g]++; SS.done++;
  if (st.ok === true) SS.correct++; else if (st.ok === false) SS.wrong++;
  try {
    const r = await postAnswer({ key: c.key, rating: g, ms });  // 2.3: без зв'язку відповідь збережеться й досилається пізніше
    c.next = r.next;
  } catch (e) { handleErr(e); }
  if (g === 1) { // «Знову» — ще раз у цій сесії, через кілька карток
    const pos = Math.min(SS.cards.length, SS.i + 4);
    SS.cards.splice(pos, 0, { ...c, is_new: false });
  }
  nextCard();
}
function nextCard() { SS.i++; SS.st = null; drawCard(); }

function ssKey(e) {
  if (!SS) return;
  if ($(".modal-bg") || $("#sheet")) return;
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName);
  if (SS.mode === "blitz") {
    if (e.key === "ArrowRight" || e.key.toLowerCase() === "p") { e.preventDefault(); blitzAnswer(true); }
    else if (e.key === "ArrowLeft" || e.key.toLowerCase() === "n") { e.preventDefault(); blitzAnswer(false); }
    return;
  }
  if (typing) return;
  const c = cur(), st = SS.st; if (!c || !st) return;
  const k = e.key;
  if (k === "Escape") { $("#ss-exit")?.click(); return; }
  if ((k === "h" || k === "H") && $("#ss-hint")) { e.preventDefault(); $("#ss-hint").click(); return; }
  if (!(st.shown || st.answered)) {
    if (k === " ") { e.preventDefault(); showAnswer(); return; }
    if (c.type === "mcq") { const i = LETTERS.indexOf(k.toUpperCase()); if (i >= 0 && i < c.options.length) { e.preventDefault(); const oi = st.optOrder[i]; reveal(oi === c.correct, { pick: oi }); } }
    if (c.type === "tf") { if (k === "ArrowRight" || k.toLowerCase() === "p") reveal(c.answer === true, { pick: true }); if (k === "ArrowLeft" || k.toLowerCase() === "n") reveal(c.answer === false, { pick: false }); }
    if (c.type === "order" && /^[1-9]$/.test(k)) { const left = st.shuffled.filter((i) => !st.order.includes(i)); const p = left[+k - 1]; if (p != null) $(`[data-pick="${p}"]`)?.click(); }
    return;
  }
  if (SS.mode === "test") {
    if (k === "Enter" || k === " ") { e.preventDefault(); if ($("#ss-next")) nextCard(); }
    if (c.type === "flip" && st.ok == null && (k === "1" || k === "2")) $(`[data-self="${k === "2" ? 1 : 0}"]`)?.click();
    return;
  }
  if (/^[1-4]$/.test(k)) { e.preventDefault(); rate(+k); }
  else if (k === "Enter" || (k === " " && st.answered)) { e.preventDefault(); rate(st.suggest || 3); }
}

// свайпи: ← знову, → добре, ↑ легко
function bindSwipe(el, cb) {
  if (!el) return;
  let x0 = null, y0 = 0, dx = 0, dy = 0, id = null;
  el.style.touchAction = "pan-y";
  el.addEventListener("pointerdown", (e) => { if (e.pointerType === "mouse" || e.target.closest("button,a,input")) return; x0 = e.clientX; y0 = e.clientY; id = e.pointerId; dx = dy = 0; el.style.transition = "none"; });
  el.addEventListener("pointermove", (e) => {
    if (x0 == null || e.pointerId !== id) return;
    dx = e.clientX - x0; dy = e.clientY - y0;
    el.style.transform = `translate(${dx}px, ${Math.min(0, dy)}px) rotate(${dx / 25}deg)`;
    el.dataset.sw = dy < -70 && Math.abs(dy) > Math.abs(dx) ? "up" : dx > 60 ? "right" : dx < -60 ? "left" : "";
  });
  const end = () => {
    if (x0 == null) return;
    x0 = null; el.style.transition = "transform .18s ease";
    const sw = el.dataset.sw; el.dataset.sw = "";
    if (sw) { el.style.transform = sw === "up" ? "translateY(-120%)" : `translateX(${sw === "right" ? 130 : -130}%) rotate(${sw === "right" ? 12 : -12}deg)`; setTimeout(() => cb(sw === "up" ? 4 : sw === "right" ? 3 : 1), 160); }
    else el.style.transform = "";
  };
  el.addEventListener("pointerup", end); el.addEventListener("pointercancel", end);
}

// ---------- підсумок сесії
async function summary() {
  const s = SS; if (!s) return;
  const secs = Math.round((Date.now() - s.t0) / 1000);
  document.removeEventListener("keydown", ssKey);
  if (s.mode === "test") {
    const n = s.correct + s.wrong;
    POST("/api/study/activity", { mode: "test", n, correct: s.correct, ms: secs * 1000, subject_id: s.subject, mistakes: s.mistakes.map((c) => c.key) }).catch(() => {});
    const pct = n ? Math.round((100 * s.correct) / n) : 0;
    const grade = pct >= 91 ? "5.0" : pct >= 81 ? "4.5" : pct >= 71 ? "4.0" : pct >= 61 ? "3.5" : pct >= 51 ? "3.0" : "2.0";
    setView(`<div class="study-wrap"><div class="card pad sum-card">
      <div class="sum-big ${+grade >= 3 ? "ok" : "bad"}">${grade}</div><h1>Тест: ${s.correct} з ${n} (${pct}%)</h1>
      <p class="muted">${fmtClock(secs)} · ${esc(subjById(s.subject)?.name || "усі предмети")}</p>
      ${s.mistakes.length ? `<h3 style="text-align:left">Помилки — повторіть джерело</h3><div class="list mistakes">${s.mistakes.map((c) => `<div class="row" style="align-items:flex-start"><div class="body"><div class="title" style="white-space:normal">${esc(c.q.replace(/_{3,}/, "___").slice(0, 200))}</div>
        <div class="meta">Правильно: <b>${esc(c.type === "mcq" ? c.options[c.correct] : c.type === "tf" ? (c.answer ? "Правда" : "Неправда") : c.type === "order" ? c.steps.join(" → ") : (c.answer || c.a || ""))}</b></div>
        <div class="meta">${srcLink(c)}</div></div></div>`).join("")}</div>` : `<p>Без помилок 🎉</p>`}
      <div class="btn-row" style="justify-content:center;margin-top:16px"><button class="btn primary" id="sum-back">${icon("left")} До навчання</button>${s.mistakes.length ? `<button class="btn" id="sum-again">${icon("refresh")} Повторити помилки</button>` : ""}</div></div></div>`);
    $("#sum-again") && ($("#sum-again").onclick = () => { const m = s.mistakes.map((c) => ({ ...c })); SS = { ...s, mode: "all", graded: true, cards: m, i: 0, st: null, done: 0, stats: { 1: 0, 2: 0, 3: 0, 4: 0 }, correct: 0, wrong: 0, mistakes: [], t0: Date.now() }; document.addEventListener("keydown", ssKey); drawCard(); });
  } else {
    let prog = null; try { prog = await GET("/api/study/progress"); } catch { }
    const n = s.done;
    setView(`<div class="study-wrap"><div class="card pad sum-card">
      <div style="font-size:42px">🎉</div><h1>Сесію завершено</h1>
      <p class="muted">${n} ${plural(n, "картка", "картки", "карток")} · ${fmtClock(secs)}${s.correct + s.wrong ? ` · правильно ${Math.round((100 * s.correct) / (s.correct + s.wrong))}%` : ""}</p>
      <div class="sum-rates">${[1, 2, 3, 4].map((g) => `<div class="${RATE_CLS[g]}"><b>${s.stats[g]}</b><span>${RATE[g]}</span></div>`).join("")}</div>
      ${prog ? `<p class="small muted">🔥 Серія: ${prog.streak} ${plural(prog.streak, "день", "дні", "днів")} · завтра: ${prog.forecast.tomorrow_reviews} повторень + до ${prog.forecast.tomorrow_new} нових</p>` : ""}
      <div class="btn-row" style="justify-content:center;margin-top:16px"><button class="btn primary" id="sum-back">${icon("left")} До навчання</button></div></div></div>`);
  }
  $("#sum-back").onclick = () => ssEnd();
}

// ---------- бліц
function blitzStart() {
  SS.end = Date.now() + SS.seconds * 1000;
  SS.timer = setInterval(() => { const el = $("#bz-t"); const left = Math.max(0, Math.ceil((SS.end - Date.now()) / 1000)); if (el) el.textContent = left; if (left <= 0) blitzFinish(); }, 200);
  blitzDraw();
}
function blitzDraw(flash = "") {
  const c = cur();
  if (!c) return blitzFinish();
  setView(`<div class="study-wrap">
    <div class="ss-top"><button class="btn ghost sm" id="ss-exit">${icon("x")}</button><span class="ss-mode">Бліц</span><span style="flex:1"></span><span class="bz-score">✓ ${SS.correct} · ✗ ${SS.wrong}</span><span class="bz-t" id="bz-t">${Math.max(0, Math.ceil((SS.end - Date.now()) / 1000))}</span></div>
    <div class="flash-card bz ${flash}" id="fc" style="--c:${c.color}"><div class="fc-meta"><span class="subj-chip" style="--c:${c.color}">${esc(c.subject || "—")}</span></div>
      <div class="fc-inner"><div class="fc-q">${richText(c.blitz_q)}</div></div></div>
    <div class="ss-actions"><div class="rate-row two"><button class="btn lg rate r-again" data-bz="0">← Неправда</button><button class="btn lg rate r-good" data-bz="1">Правда →</button></div></div></div>`);
  $("#ss-exit").onclick = () => blitzFinish();
  $$("[data-bz]").forEach((b) => (b.onclick = () => blitzAnswer(b.dataset.bz === "1")));
  bindSwipe($("#fc"), (g) => blitzAnswer(g !== 1));
}
function blitzAnswer(v) {
  const c = cur(); if (!c || SS.finished) return;
  const ok = v === c.blitz_answer;
  ok ? SS.correct++ : (SS.wrong++, SS.mistakes.push(c));
  SS.i++;
  if (SS.i >= SS.cards.length) SS.i = 0; // коло
  blitzDraw(ok ? "flash-ok" : "flash-bad");
}
function blitzFinish() {
  if (!SS || SS.finished) return;
  SS.finished = true; clearInterval(SS.timer);
  const n = SS.correct + SS.wrong;
  POST("/api/study/activity", { mode: "blitz", n, correct: SS.correct, ms: SS.seconds * 1000 }).catch(() => {});
  document.removeEventListener("keydown", ssKey);
  setView(`<div class="study-wrap"><div class="card pad sum-card"><div style="font-size:42px">⚡</div><h1>Бліц: ${SS.correct} з ${n}</h1>
    <p class="muted">${n ? Math.round((100 * SS.correct) / n) : 0}% правильно за ${SS.seconds} с</p>
    ${SS.mistakes.length ? `<div class="list mistakes">${SS.mistakes.slice(0, 12).map((c) => `<div class="row"><div class="body"><div class="title" style="white-space:normal">${esc(c.blitz_q)}</div><div class="meta">Насправді: <b>${c.blitz_answer ? "правда" : "неправда"}</b>${c.type === "mcq" ? ` — правильно: ${esc(c.options[c.correct])}` : ""} · ${srcLink(c)}</div></div></div>`).join("")}</div>` : ""}
    <div class="btn-row" style="justify-content:center;margin-top:16px"><button class="btn primary" id="sum-back">${icon("left")} До навчання</button><button class="btn" id="bz-again">${icon("refresh")} Ще раз</button></div></div></div>`);
  const filt = SS.filt, back = SS.back;
  $("#sum-back").onclick = () => ssEnd();
  $("#bz-again").onclick = () => { ssEnd(true); startSession("blitz", filt, back); };
}

// ---------- дії з карткою: редагувати, важливо, приховати, своя, «Поясни простіше»
function cardMenu(c, after) {
  openSheet("Картка", `<div class="sheet-actions">
    <button class="btn" data-cm="edit">${icon("edit")} Редагувати</button>
    <button class="btn" data-cm="imp">★ ${c.important ? "Зняти «важливо на іспит»" : "Важливо на іспит"}</button>
    <button class="btn" data-cm="hide">${icon("x")} ${c.hidden ? "Показувати знову" : "Приховати картку"}</button>
    <button class="btn" data-cm="explain">${icon("sparkles")} ${c.explain_pending ? "Скасувати «Поясни простіше»" : "Поясни простіше (Claude)"}</button>
    <button class="btn" data-cm="add">${icon("plus")} Своя картка до цієї лекції</button>
    ${c.custom ? `<button class="btn danger" data-cm="del">${icon("trash")} Видалити мою картку</button>` : ""}
    ${c.lecture_id ? `<a class="btn" href="#/lecture/${enc(c.lecture_id)}${c.source?.sec != null ? "?t=" + c.source.sec : ""}">${icon("external")} Відкрити лекцію</a>` : ""}</div>`, (el) => {
    $$("[data-cm]", el).forEach((b) => (b.onclick = async () => {
      closeSheet();
      const a = b.dataset.cm;
      try {
        if (a === "edit") { if (await editCardModal(c)) toast("Збережено"); }
        else if (a === "imp") { await PATCH("/api/study/card", { key: c.key, important: !c.important }); c.important = !c.important; toast(c.important ? "★ Позначено: важливо на іспит" : "Позначку знято"); }
        else if (a === "hide") {
          await PATCH("/api/study/card", { key: c.key, hidden: !c.hidden }); c.hidden = !c.hidden; toast(c.hidden ? "Картку приховано" : "Картка знову в навчанні", "info");
          if (c.hidden && SS && !after) { SS.cards.splice(SS.i, 1); SS.st = null; return drawCard(); }
        } else if (a === "explain") {
          if (c.explain_pending) { await DEL(`/api/study/explain?key=${enc(c.key)}`); c.explain_pending = false; toast("Запит скасовано", "info"); }
          else {
            const r = await modal({ title: "Поясни простіше", okText: "У чергу Claude", body: `<p class="small muted">Claude пояснить цю картку простими словами під час наступної обробки — пояснення з'явиться на картці.</p><div class="field"><label>Що незрозуміло? (необов'язково)</label><textarea class="input" name="note" placeholder="Напр.: не розумію різницю між процесом і потоком"></textarea></div>` });
            if (!r) return;
            await POST("/api/study/explain", { key: c.key, note: r.note }); c.explain_pending = true; toast("Додано в чергу Claude");
          }
        } else if (a === "add") { await customCardModal({ subject_id: c.subject_id, lecture_id: c.lecture_id }); }
        else if (a === "del") { if (!(await confirmBox("Видалити картку?", "Вашу картку буде видалено разом із прогресом.", "Видалити", true))) return; await DEL(`/api/study/custom/${enc(c.custom_id)}`); toast("Видалено", "info"); if (SS && !after) { SS.cards.splice(SS.i, 1); SS.st = null; return drawCard(); } }
        if (after) after(); else if (SS) drawCard();
      } catch (e) { handleErr(e); }
    }));
  });
}

async function editCardModal(c) {
  const r = await modal({ title: "Редагувати картку", okText: "Зберегти", body: `
    <div class="field"><label>Питання / твердження</label><textarea class="input" name="q" style="min-height:80px">${esc(c.q)}</textarea></div>
    ${["flip", "tf", "order"].includes(c.type) || c.a ? `<div class="field" style="margin-top:10px"><label>Відповідь</label><textarea class="input" name="a" style="min-height:70px">${esc(c.a || "")}</textarea></div>` : ""}
    <div class="field" style="margin-top:10px"><label>Пояснення</label><textarea class="input" name="explain" style="min-height:60px">${esc(c.explain || "")}</textarea></div>
    ${c.type !== "flip" ? `<p class="small muted">Варіанти відповідей і правильну відповідь змінює Claude (попросіть у «Побажаннях» лекції).</p>` : ""}
    ${c.edited ? `<label class="check" style="margin-top:8px"><input type="checkbox" name="revert"> Повернути версію Claude</label>` : ""}` });
  if (!r) return false;
  const body = { key: c.key, q: r.q, explain: r.explain, revert: !!r.revert };
  if (r.a !== undefined) body.a = r.a;
  if (r.revert) { delete body.q; delete body.a; delete body.explain; }
  await PATCH("/api/study/card", body);
  if (!r.revert) Object.assign(c, { q: r.q, explain: r.explain }, r.a !== undefined ? { a: r.a } : {});
  return true;
}

async function customCardModal(pre = {}) {
  let lecs = [];
  try { lecs = (await GET("/api/lectures")).filter((m) => m.status === "done"); } catch { }
  const r = await modal({ title: "Своя картка", okText: "Додати", body: `
    <div class="field"><label>Питання / термін</label><textarea class="input" name="q" style="min-height:70px" required></textarea></div>
    <div class="field" style="margin-top:10px"><label>Відповідь</label><textarea class="input" name="a" style="min-height:70px"></textarea></div>
    <div class="field" style="margin-top:10px"><label>Чому / приклад (необов'язково)</label><input class="input" name="why"></div>
    <div class="form-grid" style="margin-top:10px"><div class="field"><label>Предмет</label><select class="input" name="subject_id"><option value="">—</option>${S.schedule.subjects.map((s) => `<option value="${s.id}" ${s.id === pre.subject_id ? "selected" : ""}>${esc(s.short)}</option>`).join("")}</select></div>
      <div class="field"><label>Лекція</label><select class="input" name="lecture_id"><option value="">—</option>${lecs.map((m) => `<option value="${m.id}" ${m.id === pre.lecture_id ? "selected" : ""}>${esc((m.subject?.short || "") + " · " + fmtDate(m.date) + " · " + (m.display_title || "").slice(0, 40))}</option>`).join("")}</select></div></div>
    <label class="check" style="margin-top:10px"><input type="checkbox" name="important"> ★ Важливо на іспит</label>` });
  if (!r || !r.q?.trim()) return false;
  if (!r.a?.trim()) { toast("Додайте відповідь", "err"); return false; }
  try { await POST("/api/study/custom", r); toast("Картку додано"); return true; } catch (e) { handleErr(e); return false; }
}

// ---------- керування картками
async function viewStudyManage(q) {
  const f = { subject: q.subject || "", show: "all", text: "" };
  const render = async () => {
    const data = await GET(`/api/study?hidden=1${f.subject ? "&subject=" + enc(f.subject) : ""}`);
    let list = data.cards;
    if (f.show === "hidden") list = list.filter((c) => c.hidden);
    else if (f.show === "important") list = list.filter((c) => c.important);
    else if (f.show === "custom") list = list.filter((c) => c.custom);
    else if (f.show === "leech") list = list.filter((c) => c.leech);
    if (f.text) { const t = normAns(f.text); list = list.filter((c) => normAns(c.q + " " + (c.a || "")).includes(t)); }
    setView(`<a class="small muted" href="#/study" style="display:inline-flex;align-items:center;gap:4px">${icon("left")} Навчання</a>
      <div class="page-head" style="margin-top:8px"><div><h1>Картки</h1><div class="sub">${data.cards.length} карток · ${data.cards.filter((c) => c.hidden).length} приховано · ${data.cards.filter((c) => c.custom).length} моїх</div></div>
        <button class="btn primary" id="mg-add">${icon("plus")} Своя картка</button></div>
      <div class="btn-row" style="margin-bottom:12px"><select class="input" id="mg-subj" style="max-width:220px"><option value="">Усі предмети</option>${S.schedule.subjects.map((s) => `<option value="${s.id}" ${f.subject === s.id ? "selected" : ""}>${esc(s.short)}</option>`).join("")}</select>
        <div class="seg" id="mg-show">${[["all", "Усі"], ["important", "★ Іспит"], ["leech", "Складні"], ["custom", "Мої"], ["hidden", "Приховані"]].map(([k, t]) => `<button data-show="${k}" class="${f.show === k ? "on" : ""}">${t}</button>`).join("")}</div>
        <input class="input" id="mg-q" placeholder="Пошук…" value="${esc(f.text)}" style="max-width:220px"></div>
      <div class="card list">${list.map((c) => `<div class="row mg-row ${c.hidden ? "is-hidden" : ""}" style="align-items:flex-start"><div class="body">
          <div class="title" style="white-space:normal">${c.important ? "★ " : ""}${esc(c.q.slice(0, 220))}</div>
          <div class="meta"><span class="subj-chip" style="--c:${c.color}">${esc(c.subject || "—")}</span><span class="badge">${TYPE_LABEL[c.type]}</span>${c.custom ? '<span class="badge">моя</span>' : ""}${c.edited ? '<span class="badge">змінено</span>' : ""}${c.hidden ? '<span class="badge">приховано</span>' : ""}
            <span>${c.is_new ? "нова" : c.learned ? "вивчено" : "вчу"}${c.lapses ? ` · забув ${c.lapses}×` : ""}</span>${c.explain_pending ? `<span>${icon("clock")} чекає на Claude</span>` : ""}</div></div>
          <button class="btn ghost icon sm" data-mg="${esc(c.key)}" title="Дії">${icon("more")}</button></div>`).join("") || `<div class="empty">${icon("search")}<b>Нічого не знайдено</b></div>`}</div>`, render);
    $("#mg-subj").onchange = (e) => { f.subject = e.target.value; render(); };
    $$("#mg-show [data-show]").forEach((b) => (b.onclick = () => { f.show = b.dataset.show; render(); }));
    $("#mg-q").oninput = debounce((e) => { f.text = e.target.value; render().then(() => { const i = $("#mg-q"); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }); }, 300);
    $("#mg-add").onclick = () => customCardModal({ subject_id: f.subject }).then((ok) => ok && render());
    $$("[data-mg]").forEach((b) => (b.onclick = () => cardMenu(data.cards.find((c) => c.key === b.dataset.mg), render)));
  };
  await render();
}
