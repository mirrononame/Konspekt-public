"use strict";
// ============================================================ 2.3
// E1 «Семестр» (шлях до заліку), E2 завдання у вікнах планера, E3 звіт, E6 «Готуюсь до тесту»,
// E4 календар і E5 сповіщення в налаштуваннях, E7 офлайн (service worker), E8 свайп «назад».
// Підключається перед app.js; помічники ($, GET, icon…) використовуються лише під час виклику.

const fmtGrade = (v) => v == null ? "—" : String(Math.round(v * 100) / 100).replace(".", ",");

// ---------- E1: «Шлях до заліку»
async function viewSemester() {
  const render = async () => {
    const list = await GET("/api/semester");
    const risk = list.filter((s) => s.status === "risk").length, nos = list.filter((s) => s.status === "nosetup").length;
    const card = (s) => {
      const st = s.setup;
      const badge = s.status === "risk" ? `<span class="badge s-error">${icon("alert")} ризик</span>` : s.status === "ok" ? `<span class="badge s-done">${icon("check")} у нормі</span>`
        : s.status === "nodata" ? `<span class="badge">оцінок ще немає</span>` : `<span class="badge">умови ще не складено</span>`;
      if (!st) return `<div class="card pad sem-card" style="--c:${s.color}"><div class="sem-head"><span class="subj-chip" style="--c:${s.color}">${esc(s.short)}</span><b>${esc(s.name)}</b><span style="flex:1"></span>${badge}</div>
        <div class="small muted">Claude складе умови заліку з пам’яті предмета під час наступної обробки (вони вже в черзі).</div></div>`;
      return `<div class="card pad sem-card" style="--c:${s.color}">
        <div class="sem-head"><span class="subj-chip" style="--c:${s.color}">${esc(s.short)}</span><b>${esc(s.name)}</b><span style="flex:1"></span>${badge}</div>
        ${st.formula ? `<div class="sem-formula">${esc(st.formula)}</div>` : ""}
        <div class="sem-comps">${s.components.map((c) => `<div class="sem-comp ${c.min != null && c.avg != null && c.avg < c.min ? "bad" : ""}">
          <div class="small muted">${esc(c.name)}${c.weight ? ` · ${Math.round(c.weight * 100)}%` : ""}${c.min != null ? ` · поріг ${fmtGrade(c.min)}` : ""}</div>
          <div class="sem-val">${fmtGrade(c.avg)}<span class="small muted">${c.n ? ` (${c.n})` : ""}</span></div>
          <button class="btn ghost sm" data-addg="${esc(s.subject_id)}|${esc(c.id)}|${esc(c.name)}">${icon("plus")} Оцінка</button></div>`).join("")}</div>
        ${s.current != null ? `<div class="small">Поточна зважена: <b>${fmtGrade(s.current)}</b>${s.complete ? "" : " <span class=\"muted\">(не всі частини мають оцінки)</span>"}</div>` : ""}
        ${s.risks.length ? `<div class="callout warn" style="margin-top:10px">${icon("alert")}<div class="c-body small">${s.risks.map(esc).join("<br>")}</div></div>` : ""}
        ${s.next.length || s.overdue.length ? `<div class="sem-ms">${[...s.overdue.map((m) => [m, "late"]), ...s.next.map((m) => [m, ""])].map(([m, cls]) => `<div class="sem-m ${cls}"><span>${fmtDate(m.date.slice(0, 10))}</span>${esc(m.title || "")}</div>`).join("")}</div>` : ""}
        ${s.grades.length ? `<details class="small" style="margin-top:8px"><summary class="muted" style="cursor:pointer">Мої оцінки (${s.grades.length})</summary>${s.grades.map((g) => `<div class="sem-g">${esc(g.component)} · <b>${fmtGrade(g.value)}</b> ${esc(g.title || "")}<button class="btn ghost icon sm" data-delg="${esc(s.subject_id)}|${esc(g.id)}" title="Видалити">${icon("trash")}</button></div>`).join("")}</details>` : ""}
        ${st.notes ? `<div class="small muted" style="margin-top:8px">${esc(st.notes)}</div>` : ""}
      </div>`;
    };
    setView(`<div class="page-head"><div><h1>Семестр</h1><div class="sub">Що стоїть між тобою й заліком${risk ? ` · <b style="color:var(--err)">ризик: ${risk}</b>` : ""}${nos ? ` · без умов: ${nos}` : ""}</div></div>
        <a class="btn ghost" href="#/planner">${icon("clock")} План тижня</a></div>
      <div class="grid cols-2">${list.map(card).join("")}</div>
      <div class="small muted section">Умови заліку (формулу, пороги, етапи) Claude бере з пам’яті предмета й слів викладача і оновлює після кожного заняття. Оцінки вписуєш ти — з USOS вони автоматично не підтягуються.</div>`, render);
    $$("[data-addg]").forEach((b) => (b.onclick = async () => {
      const [sid, comp, name] = b.dataset.addg.split("|");
      const v = await modal({ title: `Оцінка: ${esc(name)}`, okText: "Додати", body: `<div class="field"><label>Оцінка</label><input class="input" name="value" inputmode="decimal" placeholder="напр. 4,5"></div>
        <div class="field" style="margin-top:10px"><label>За що (необов’язково)</label><input class="input" name="title" placeholder="Lab 1, kolokwium…"></div>` });
      if (!v || !v.value) return;
      try { await POST("/api/semester/grade", { subject_id: sid, component: comp, value: v.value, title: v.title }); render(); } catch (e) { handleErr(e); }
    }));
    $$("[data-delg]").forEach((b) => (b.onclick = async () => { const [sid, gid] = b.dataset.delg.split("|"); try { await DEL(`/api/semester/grade/${enc(sid)}/${enc(gid)}`); render(); } catch (e) { handleErr(e); } }));
  };
  await render();
}

// ---------- E2: завдання у вікнах планера
const TASK_IC = { deadline: "clock", prep: "list", exam: "book", cards: "refresh" };
function plTasksHtml(w) {
  if (!w.tasks || !w.tasks.length) return "";
  return `<div class="pl-tasks">${w.tasks.map((t) => `<div class="pl-task ${t.kind}"><a href="${esc(t.href || "#/")}">${icon(TASK_IC[t.kind] || "check")} <span class="small muted">${t.from}–${t.to}</span> ${esc(t.title)}${t.part ? ' <span class="small muted">(частина)</span>' : ""}</a>
    ${t.done_api ? `<button class="btn ghost icon sm" data-tdone="${esc(t.done_api)}" title="Зроблено">${icon("check")}</button>` : ""}</div>`).join("")}</div>`;
}
function plUnplacedHtml(tasks) {
  const u = (tasks && tasks.unplaced) || [];
  if (!u.length) return "";
  return `<div class="callout warn" style="margin-bottom:14px">${icon("alert")}<div class="c-body"><div class="c-title">Не вміщається до терміну: ${u.length}</div>
    ${u.map((t) => `<div class="small">${esc(t.title)} — бракує ~${fmtMins(t.left)} до ${esc(fmtDate(t.due.slice(0, 10)))}</div>`).join("")}
    <div class="small muted" style="margin-top:4px">Звільни вікно в налаштуваннях планера (довший робочий день, вихідні) або почни раніше.</div></div></div>`;
}
function bindPlTasks(after) {
  $$("[data-tdone]").forEach((b) => (b.onclick = async (e) => { e.preventDefault(); b.disabled = true; try { await POST(b.dataset.tdone, { done: true }); toast("Позначено як зроблене"); after && after(); } catch (er) { b.disabled = false; handleErr(er); } }));
}

// ---------- E3: чернетка звіту й перевірка перед здачею (вкладка «Здача»)
function reportHtml(L) {
  const R = L.report || {}, res = R.result, req = R.req;
  const kindT = { draft: "Чернетка звіту", check: "Перевірка перед здачею" };
  return `<div class="card pad" style="margin-bottom:14px"><h3 style="margin-top:0">${icon("sparkles")} Звіт з Claude</h3>
    ${R.pending ? `<div class="small">${icon("clock")} ${kindT[req.kind]} — у черзі Claude${req.note ? `: «${esc(req.note)}»` : ""}. Файли з’являться нижче. <button class="btn ghost sm" data-repcancel>Скасувати</button></div>`
      : `<div class="small muted" style="margin-bottom:8px">Claude складе звіт за вимогами викладача (з пам’яті предмета й умови), замість скрінів і прізвищ залишить позначки. Або перевірить твій звіт перед здачею.</div>
        <textarea class="input" id="rep-note" style="min-height:56px" placeholder="Побажання (необов’язково): напр. «скріни вже є, додай висновки»"></textarea>
        <div class="btn-row" style="margin-top:8px"><button class="btn sm primary" data-rep="draft">${icon("file")} Зробити чернетку звіту</button><button class="btn sm" data-rep="check">${icon("check")} Перевірити перед здачею</button></div>`}
    ${res && !R.pending ? `<div class="rep-res" style="margin-top:10px"><div class="small muted">${kindT[res.kind] || "Результат"} · ${relTime(res.completed_at)}</div>
      ${res.summary ? `<div style="margin-top:4px">${esc(res.summary)}</div>` : ""}
      ${(res.missing || []).length ? `<div class="callout warn" style="margin-top:8px">${icon("alert")}<div class="c-body small"><b>Бракує:</b><br>${res.missing.map(esc).join("<br>")}</div></div>` : ""}</div>` : ""}
  </div>`;
}
function bindReport(L, refresh) {
  $$("[data-rep]").forEach((b) => (b.onclick = async () => { b.disabled = true; try { await POST(`/api/lectures/${enc(L.id)}/report`, { kind: b.dataset.rep, note: $("#rep-note")?.value || "" }); toast("Запит у черзі Claude", "info"); refresh(); } catch (e) { b.disabled = false; handleErr(e); } }));
  const c = $("[data-repcancel]"); if (c) c.onclick = async () => { try { await DEL(`/api/lectures/${enc(L.id)}/report`); refresh(); } catch (e) { handleErr(e); } };
}

// ---------- E6: «Готуюсь до тесту» (сторінка предмета)
function examPrepHtml(sid, sem) {
  const p = sem && sem.prep;
  if (!p) return `<button class="btn" data-prep="${esc(sid)}">${icon("book")} Готуюсь до тесту</button>`;
  return `<span class="exam-chip">${icon("book")} ${esc(p.title)} · ${fmtDate(p.date)}${p.days_left != null ? ` (через ${p.days_left} дн.)` : ""}
    ${p.ready ? `<a class="btn sm primary" href="/api/subjects/${enc(sid)}/szpargalka.pdf" target="_blank">${icon("pdf")} Шпаргалка</a>` : `<span class="small muted">шпаргалка готується</span>`}
    <button class="btn ghost icon sm" data-prepoff="${esc(sid)}" title="Скасувати">${icon("x")}</button></span>`;
}
function bindExamPrep(after) {
  $$("[data-prep]").forEach((b) => (b.onclick = async () => {
    const sid = b.dataset.prep, sem = await GET("/api/semester").catch(() => []);
    const s = sem.find((x) => x.subject_id === sid), next = (s?.next || []).find((m) => /kolok|test|egzam|zalicz/i.test(m.title || ""));
    const v = await modal({ title: "Готуюсь до тесту", okText: "Почати підготовку", body: `<p class="small muted" style="margin-top:0">Claude зробить шпаргалку на 2–3 сторінки з усіх конспектів предмета.</p>
      <div class="field"><label>Що за тест</label><input class="input" name="title" value="${esc(next?.title || "Kolokwium")}"></div>
      <div class="field" style="margin-top:10px"><label>Дата</label><input class="input" type="date" name="date" value="${esc((next?.date || "").slice(0, 10))}"></div>` });
    if (!v) return;
    try { await POST(`/api/subjects/${enc(sid)}/exam-prep`, { date: v.date, title: v.title }); toast("Підготовку почато — шпаргалка в черзі Claude", "info"); after && after(); } catch (e) { handleErr(e); }
  }));
  $$("[data-prepoff]").forEach((b) => (b.onclick = async () => { try { await DEL(`/api/subjects/${enc(b.dataset.prepoff)}/exam-prep`); after && after(); } catch (e) { handleErr(e); } }));
}

// ---------- E4 + E5: календар і сповіщення (налаштування)
async function loadCalPush() {
  const cc = $("#cal-card"), pc = $("#push-card"); if (!cc || !pc) return;
  try {
    const c = await GET("/api/calendar-info"), url = c.tailscale || c.local;
    cc.innerHTML = `<h2>${icon("calendar")} Календар у телефоні</h2>
      <div class="small muted">Пари, дедлайни (з нагадуваннями за добу й за 2 год) і етапи заліку — у календарі iPhone чи Google. Оновлюється сам.</div>
      <div class="prompt-box" style="margin-top:10px"><code style="word-break:break-all">${esc(url)}</code><button class="btn sm" data-copycal>${icon("copy")} Копіювати</button></div>
      ${c.tailscale ? "" : `<div class="small" style="color:var(--warn);margin-top:6px">${icon("info")} Увімкніть доступ з телефона (Tailscale) — тоді посилання працюватиме з телефона.</div>`}
      <ol class="small" style="margin:8px 0 0;padding-left:18px;color:var(--text-2)"><li>iPhone: Параметри → Календар → Облікові записи → Додати → Інше → «Підписний календар».</li><li>Вставте посилання й збережіть.</li></ol>
      <div class="small muted" style="margin-top:6px">Посилання містить секретний ключ — не діліться ним.</div>`;
    $("[data-copycal]", cc).onclick = () => copyText(url);
  } catch (e) { cc.innerHTML = `<h2>${icon("calendar")} Календар у телефоні</h2><div class="small" style="color:var(--err)">${esc(e.message)}</div>`; }

  const P = await GET("/api/push").catch(() => null);
  const can = "serviceWorker" in navigator && "PushManager" in window && window.isSecureContext;
  const reg = can ? await navigator.serviceWorker.getRegistration() : null;
  const sub = reg ? await reg.pushManager.getSubscription().catch(() => null) : null;
  const kinds = S.state.settings.push_kinds || {};
  const ios = /iPhone|iPad/.test(navigator.userAgent), standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  pc.innerHTML = `<h2>${icon("phone")} Сповіщення</h2>
    ${!can ? `<div class="callout info">${icon("info")}<div class="c-body small">${ios && !standalone ? "На iPhone: відкрийте «Конспект» у Safari через https-адресу Tailscale → «Поділитися» → «На екран Додому», а потім увімкніть сповіщення тут, з іконки на головному екрані." : "Тут сповіщення недоступні: потрібна https-адреса (Tailscale) або localhost."}</div></div>`
      : `<div class="btn-row">${sub ? `<span class="badge s-done">${icon("check")} увімкнено на цьому пристрої</span><button class="btn sm" id="push-test">Надіслати тестове</button><button class="btn ghost sm" id="push-off">Вимкнути</button>`
        : `<button class="btn primary sm" id="push-on">${icon("check")} Увімкнути на цьому пристрої</button>`}</div>`}
    <div class="small muted" style="margin:8px 0 4px">Підписаних пристроїв: ${P?.subscriptions ?? 0}${P?.beta ? " · у беті сповіщення не надсилаються" : ""}</div>
    <div style="display:flex;flex-direction:column;gap:6px">${Object.entries(P?.kinds || {}).map(([k, t]) => `<label class="check"><input type="checkbox" data-pk="${k}" ${kinds[k] !== false ? "checked" : ""}><div><b>${esc(t)}</b></div></label>`).join("")}</div>`;
  $$("[data-pk]", pc).forEach((i) => (i.onchange = async () => { const pk = { ...(S.state.settings.push_kinds || {}), [i.dataset.pk]: i.checked }; try { await PUT("/api/settings", { push_kinds: pk }); S.state.settings.push_kinds = pk; } catch (e) { handleErr(e); } }));
  $("#push-on", pc) && ($("#push-on", pc).onclick = async () => {
    try {
      if ((await Notification.requestPermission()) !== "granted") return toast("Сповіщення заборонено в браузері", "err");
      const r = await navigator.serviceWorker.ready;
      const key = Uint8Array.from(atob(P.public_key.replace(/-/g, "+").replace(/_/g, "/") + "==".slice(0, (4 - P.public_key.length % 4) % 4)), (c) => c.charCodeAt(0));
      const s = await r.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
      await POST("/api/push/subscribe", { subscription: s.toJSON(), device: navigator.userAgent.slice(0, 80) });
      toast("Сповіщення увімкнено"); loadCalPush();
    } catch (e) { handleErr(e); }
  });
  $("#push-test", pc) && ($("#push-test", pc).onclick = async () => { try { await POST("/api/push/test"); toast("Надіслано — має прийти за кілька секунд", "info"); } catch (e) { handleErr(e); } });
  $("#push-off", pc) && ($("#push-off", pc).onclick = async () => { try { await POST("/api/push/unsubscribe", { endpoint: sub.endpoint }); await sub.unsubscribe(); loadCalPush(); } catch (e) { handleErr(e); } });
}

// ---------- E7: офлайн — service worker, «прогрів» свіжих конспектів, відповіді на картки без зв’язку
const OFFLINE_Q = "kp_offline_answers";
const offQ = { get: () => { try { return JSON.parse(localStorage.getItem(OFFLINE_Q) || "[]"); } catch { return []; } },
  set: (a) => { try { localStorage.setItem(OFFLINE_Q, JSON.stringify(a.slice(-500))); } catch { } } };
async function postAnswer(body) {
  try { return await POST("/api/study/answer", body); }
  catch (e) {
    if (!(e instanceof ApiError) || !/зв.язку/.test(e.message)) throw e;
    offQ.set([...offQ.get(), { ...body, at: Date.now() }]);  // без зв'язку: збережемо й надішлемо пізніше
    return { offline: true };
  }
}
async function flushOfflineAnswers() {
  const q = offQ.get(); if (!q.length) return;
  let sent = 0;
  for (let i = 0; i < q.length; i++) {
    try { await POST("/api/study/answer", { key: q[i].key, rating: q[i].rating, ms: q[i].ms }); sent++; }
    catch (e) { if (/зв.язку/.test(e.message)) { offQ.set(q.slice(i)); return; } }  // знову без зв'язку — решту пізніше
  }
  offQ.set([]);
  if (sent) toast(`Надіслано відповідей, збережених без зв’язку: ${sent}`, "ok");
}
async function setupServiceWorker() {
  if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
  try {
    const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
    // «прогріваємо» конспекти й дані за 2 тижні, поки є зв'язок
    const items = await GET("/api/lectures").catch(() => []);
    const since = new Date(Date.now() - 14 * 86400000).toISOString().slice(0, 10);
    const urls = ["/api/state", "/api/schedule", "/api/lectures", "/api/week", "/api/deadlines", "/api/study", "/api/study/progress", "/api/semester", "/api/checklists"];
    for (const m of items.filter((m) => (m.date || "") >= since)) {
      urls.push(`/api/lectures/${encodeURIComponent(m.id)}`);
      if (m.output?.pdf) urls.push(`/api/lectures/${encodeURIComponent(m.id)}/output/${encodeURIComponent(m.output.pdf)}`);
    }
    (reg.active || reg.waiting || reg.installing)?.postMessage({ type: "warm", urls });
    navigator.serviceWorker.ready.then((r) => r.active && r.active.postMessage({ type: "warm", urls }));
  } catch (e) { console.warn("sw", e); }
}

// ---------- E8: свайп від лівого краю — «назад» (телефон)
(function swipeBack() {
  let x0 = null, y0 = 0, t0 = 0;
  document.addEventListener("touchstart", (e) => { const t = e.touches[0]; if (t.clientX < 24 && !document.body.classList.contains("study-on")) { x0 = t.clientX; y0 = t.clientY; t0 = Date.now(); } else x0 = null; }, { passive: true });
  document.addEventListener("touchend", (e) => {
    if (x0 == null) return; const t = e.changedTouches[0];
    if (t.clientX - x0 > 80 && Math.abs(t.clientY - y0) < 60 && Date.now() - t0 < 600 && location.hash && location.hash !== "#/") history.back();
    x0 = null;
  }, { passive: true });
})();
