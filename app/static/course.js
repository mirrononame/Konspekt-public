"use strict";
// ============================================================ ЗАНЯТТЯ ЗА ТИПОМ (2.0)
// Лаби / проєкт: «Завдання», «Мій код», «Допоможи з задачею», чекліст здачі; предмет: карта курсу + пам'ять предмета.
// Підключається перед app.js; помічники ($, GET, icon…) використовуються лише під час виклику.

// ---------- чекліст здачі: легкі рядки «☐ що зробити · предмет · коли»
const shortDue = (iso) => {
  const d = new Date(iso), now = new Date();
  const days = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 86400000);
  const t = days < 0 ? "прострочено" : days === 0 ? "сьогодні" : days === 1 ? "завтра" : days <= 6 ? `${DAYS_SHORT[(d.getDay() + 6) % 7]}` : `${d.getDate()} ${MONTHS[d.getMonth()]}`;
  return { t, cls: days < 0 ? "late" : days <= 3 ? "soon" : "", title: d.toLocaleString("uk-UA", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }) };
};
function todoRow(lid, i, extra = "") {
  const d = i.due ? shortDue(i.due) : null;
  return `<div class="todo ${i.done ? "done" : ""}" data-todo="${esc(lid)}|${esc(i.id)}">
    <button class="todo-check" role="checkbox" aria-checked="${i.done}" title="${i.done ? "Позначити невиконаним" : "Виконано"}">${icon("check")}</button>
    <span class="todo-body"><span class="todo-t" title="${esc(i.text)}">${esc(i.text)}</span>
      <span class="todo-meta">${extra}${d ? `<span class="todo-due ${d.cls}" title="${esc(d.title)}">${d.t}</span>` : `<span class="todo-due"></span>`}</span></span></div>`;
}
function bindTodos(root, after) {
  $$("[data-submit]", root).forEach((b) => (b.onclick = async (e) => {
    e.preventDefault(); const lid = b.closest("[data-lid]")?.dataset.lid; if (!lid) return;
    b.disabled = true;
    try { await POST(`/api/lectures/${enc(lid)}/submitted`, { done: b.dataset.submit === "1" }); toast(b.dataset.submit === "1" ? "Позначено як здане" : "Повернуто як було"); S.state = await GET("/api/state"); renderNav(); after && after(); }
    catch (er) { b.disabled = false; handleErr(er); }
  }));
  $$("[data-todo] .todo-check", root).forEach((b) => (b.onclick = async (e) => {
    e.preventDefault(); e.stopPropagation();
    const row = b.closest("[data-todo]"), [lid, cid] = row.dataset.todo.split("|"), done = !row.classList.contains("done");
    row.classList.toggle("done", done); b.setAttribute("aria-checked", done);
    try { await POST(`/api/lectures/${enc(lid)}/checklist/${enc(cid)}`, { done }); after && setTimeout(after, done ? 650 : 0); }
    catch (er) { row.classList.toggle("done", !done); handleErr(er); }
  }));
}

function checklistHtml(L) {
  const items = L.checklist || [];
  if (!items.length) return "";
  const n = items.filter((i) => i.done).length;
  const sorted = [...items.filter((i) => !i.done), ...items.filter((i) => i.done)];
  const sub = L.submitted_at
    ? `<span class="small" style="color:var(--ok)">${icon("check")} Здано ${relTime(L.submitted_at)}</span><button class="btn ghost sm" data-submit="0">Скасувати</button>`
    : `<button class="btn sm primary" data-submit="1" title="Закрити всі пункти й дедлайни цього заняття">${icon("check")} Здано</button>`;
  return `<div class="card todo-card" data-lid="${esc(L.id)}" style="margin-bottom:14px"><div class="todo-head"><b>${icon("check")} Що здати</b>
      <span class="todo-prog"><i style="width:${(100 * n) / items.length}%"></i></span><span class="small muted">${n}/${items.length}</span>${sub}</div>
    <div class="todo-list">${sorted.map((i) => todoRow(L.id, i)).join("")}</div></div>`;
}

function practiceFilesHtml(L, kind, fileUrl) {
  const files = L.files.filter((f) => f.kind === kind);
  const isTask = kind === "task";
  const preview = (f) => {
    const ext = (f.name.split(".").pop() || "").toLowerCase();
    if (["jpg", "jpeg", "png", "webp", "gif"].includes(ext)) return `<a href="${fileUrl(f)}" target="_blank"><img class="task-img" loading="lazy" src="${fileUrl(f)}" alt="${esc(f.name)}"></a>`;
    return "";
  };
  const codeExt = /\.(c|h|cpp|hpp|cc|py|js|ts|java|cs|sh|sql|vhd|vhdl|v|sv|go|rs|kt|php|rb|m|txt|md|json|xml|yml|yaml|html|css|asm|s|mk|cmake)$/i;
  return `<div style="display:flex;flex-direction:column;gap:14px">
    <div class="callout info">${icon(isTask ? "file" : "code")}<div class="c-body small">${isTask
      ? "Умова завдання: скріншот чи PDF з ePortalu, фото дошки або аркуша. Щойно додасте — Claude отримає запит на <b>план виконання</b> (вкладка «План»); потім умову використає посібник і «Допоможи з задачею»."
      : "Ваш код: окремі файли або архів (.zip). Claude перегляне його під час наступної обробки й відповість у «Допоможи» — з урахуванням стилю викладача."}</div></div>
    ${files.length ? `<div class="card list">${files.map((f) => `<div class="row" style="align-items:flex-start"><div class="body"><div class="title">${esc(f.name)}</div><div class="meta">${fmtSize(f.size)} · додано ${relTime(f.added_at)}</div>
        ${preview(f)}${!isTask && codeExt.test(f.name) && f.size < 60000 ? `<details class="code-peek" data-peek="${esc(f.name)}"><summary class="small">Переглянути</summary><pre class="card-code"><code>…</code></pre></details>` : ""}</div>
      <div class="right"><a class="btn sm" href="${fileUrl(f)}" target="_blank">${icon("external")}</a><a class="btn ghost icon sm" href="${fileUrl(f, 1)}">${icon("download")}</a><button class="btn ghost icon sm" data-delf="${f.kind}|${esc(f.name)}" title="Видалити файл">${icon("trash")}</button></div></div>`).join("")}</div>` : ""}
    <div class="dropzone pf-dz" id="pf-dz-${kind}" data-kind="${kind}" style="padding:22px"><div class="t">${icon("upload")} ${isTask ? "Додати умову завдання" : "Додати код або архів"}</div><div class="s pf-prog">${isTask ? "PDF, скріншот, фото…" : ".c, .py, .sql, .vhd, .zip…"} — перетягніть або натисніть</div><input type="file" class="pf-in" id="pf-in-${kind}" multiple hidden ${isTask ? 'accept="image/*,.pdf,.doc,.docx,.txt,.md"' : ""}></div>
  </div>`;
}

function helpHtml(L) {
  const hs = L.help || [];
  if (L.project_meeting && !hs.length) return projectMeetingBox(L);  // 2.4: для проєкту — «Наступний крок»
  return `<div style="display:flex;flex-direction:column;gap:14px">
    <div class="card pad"><h3 style="margin-top:0">${icon("help")} Допоможи з задачею</h3>
      <p class="small muted" style="margin-top:0">Опишіть, що не виходить (помилка, крок, незрозуміла вимога). Claude відповість під час наступної обробки — з урахуванням умови з «Завдання», вашого коду з «Мій код», викладів і того, як цього вимагає викладач.</p>
      <textarea class="input" id="hp-q" style="min-height:90px" placeholder="Напр.: скрипт падає з «Permission denied», хоча chmod зробив. Що не так?"></textarea>
      <div class="btn-row" style="margin-top:10px"><button class="btn primary" id="hp-ask">${icon("sparkles")} Запитати Claude</button>${!L.files.some((f) => f.kind === "task") ? `<span class="small muted">Порада: додайте умову у вкладку «Завдання»</span>` : ""}</div></div>
    ${hs.slice().reverse().map((h) => `<div class="card pad help-item"><div class="help-q"><b>${icon("help")} Питання</b> <span class="small muted">${relTime(h.asked_at)}</span><span style="flex:1"></span><button class="btn ghost icon sm" data-hpdel="${esc(h.id)}" title="Видалити">${icon("trash")}</button></div>
      <div class="pre-wrap">${esc(h.q)}</div>
      ${h.answered ? `<div class="help-a md">${renderMarkdown(h.answer)}</div>` : `<div class="small muted" style="margin-top:8px">${icon("clock")} Чекає на Claude — відповідь з'явиться тут сама.</div>`}</div>`).join("")}
  </div>`;
}

function bindPractice(L, refresh) {
  const box = $(".todo-card"); if (box && !box.closest("#ck-card")) bindTodos(box, () => refresh());
  const zones = $$(".pf-dz");  // 2.7: «Завдання» і «Мій код» можуть бути відкриті одночасно
  zones.forEach((dz) => {
    const kind = dz.dataset.kind, fi = $(".pf-in", dz);
    const up = async (files) => {
      let i = 0; S.uploading = true;
      for (const f of files) {
        i++; $(".pf-prog", dz).textContent = `Завантаження ${i}/${files.length}: ${f.name}`;
        const fd = new FormData(); fd.append("file", f, f.name); fd.append("kind", kind);
        try { await api(`/api/lectures/${enc(L.id)}/files`, { method: "POST", body: fd }); } catch (e) { handleErr(e); }
      }
      S.uploading = false; toast("Додано"); await refresh();
    };
    dz.onclick = () => fi.click(); fi.onchange = () => up([...fi.files]);
    dz.ondragover = (e) => { e.preventDefault(); dz.classList.add("over"); };
    dz.ondragleave = () => dz.classList.remove("over");
    dz.ondrop = (e) => { e.preventDefault(); e.stopPropagation(); dz.classList.remove("over"); hideOverlay(); up([...e.dataTransfer.files]); };
    if (kind === "task" || zones.length === 1) S.onGlobalDrop = (files) => up([...files]);  // файл, кинутий на сторінку, — це умова
  });
  if (!zones.length && S.onGlobalDrop && location.hash.startsWith("#/lecture/")) S.onGlobalDrop = null;
  $$("[data-peek]").forEach((d) => (d.ontoggle = async () => {
    if (!d.open || d.dataset.loaded) return;
    try { const t = await (await fetch(`/api/lectures/${enc(L.id)}/files/code/${enc(d.dataset.peek)}`)).text(); $("code", d).textContent = t; d.dataset.loaded = 1; } catch { }
  }));
  if ($("#hp-ask")) {
    $("#hp-q").oninput = () => (S.dirty = !!$("#hp-q").value.trim());
    $("#hp-ask").onclick = async () => {
      const q = $("#hp-q").value.trim(); if (!q) return toast("Напишіть питання", "err");
      try { await POST(`/api/lectures/${enc(L.id)}/help`, { q }); S.dirty = false; toast("Питання в черзі Claude"); await refresh(); } catch (e) { handleErr(e); }
    };
  }
  $$("[data-hpdel]").forEach((b) => (b.onclick = async () => {
    if (!(await confirmBox("Видалити питання?", "Питання і відповідь зникнуть зі сторінки.", "Видалити", true))) return;
    try { await DEL(`/api/lectures/${enc(L.id)}/help/${enc(b.dataset.hpdel)}`); await refresh(); } catch (e) { handleErr(e); }
  }));
}

function courseMapHtml(sid, crs, items) {
  const map = crs.map?.items || [], mem = crs.memory || {};
  const lec = Object.fromEntries(items.map((m) => [m.id, m]));
  const lecLink = (id, fallback) => id && lec[id] ? `<a href="#/lecture/${enc(id)}">${esc(lec[id].display_title || fmtDate(lec[id].date))}</a>` : esc(fallback || "");
  return `<div style="display:flex;flex-direction:column;gap:14px">
    <div class="card pad"><div class="section-head"><h2>${icon("map")} Карта курсу</h2>${crs.map?.updated_at ? `<span class="small muted">оновлено ${relTime(crs.map.updated_at)}</span>` : ""}</div>
      ${map.length ? `<div class="cmap">${map.map((it) => `<div class="cm-row"><div class="cm-w">${it.date ? `<span class="small muted">${fmtDate(it.date)}</span> ` : ""}${it.lecture_id ? lecLink(it.lecture_id, it.topic) : `<b>${esc(it.topic)}</b>`}${it.lecture_id && lec[it.lecture_id]?.display_title !== it.topic ? `<div class="small muted">${esc(it.topic)}</div>` : ""}</div>
        <div class="cm-arrow">→</div><div class="cm-labs">${it.labs.length ? it.labs.map((lb) => `<span class="cm-lab t-${esc(lb.type)}" title="${esc(lb.how)}">${lb.lecture_id ? lecLink(lb.lecture_id, lb.title) : esc(lb.title)}${lb.how ? `<span class="small muted"> — ${esc(lb.how)}</span>` : ""}</span>`).join("") : '<span class="small muted">ще не використовувалось</span>'}</div></div>`).join("")}</div>`
        : `<div class="empty" style="padding:16px">${icon("map")}<b>Карти ще немає</b><span class="small">Claude складає її після обробки занять: яка тема викладу знадобиться на якій лабі чи в проєкті.</span></div>`}</div>
    <div class="card pad"><div class="section-head"><h2>${icon("brain")} Пам'ять предмета</h2>${mem.updated_at ? `<span class="small muted">оновлено ${relTime(mem.updated_at)}</span>` : ""}</div>
      ${mem.text ? `<details class="mem" open><summary class="small muted">Що Claude знає про предмет: пройдене, вимоги викладача, стан лаб/проєкту, словничок</summary><div class="md">${renderMarkdown(mem.text)}</div></details>`
        : `<div class="small muted">Claude веде пам'ять предмета після кожного заняття (файл <code>subjects/${esc(sid)}/memory.md</code>) і читає її перед наступним — замість перечитування всіх старих розшифровок.</div>`}</div>
  </div>`;
}

// ---------- вкладка «Здати»
async function viewTodo(q = {}) {
  let subj = q.subject || "";
  const render = async () => {
    const list = await GET("/api/checklists?all=1");
    const all = list.flatMap((g) => g.items.map((i) => ({ ...i, g })));
    const subs = [...new Set(all.filter((r) => !r.done).map((r) => r.g.subject_id))];
    const rows = all.filter((r) => !subj || r.g.subject_id === subj);
    const open = rows.filter((r) => !r.done).sort((a, b) => (a.due || "9999").localeCompare(b.due || "9999"));
    const done = rows.filter((r) => r.done);
    const now = Date.now(), week = now + 7 * 86400000;
    const groups = [["Прострочено", open.filter((r) => r.due && new Date(r.due) < now), "late"],
      ["Найближчі 7 днів", open.filter((r) => r.due && new Date(r.due) >= now && new Date(r.due) <= week), ""],
      ["Пізніше", open.filter((r) => r.due && new Date(r.due) > week), ""],
      ["Без дати", open.filter((r) => !r.due), ""]].filter((g) => g[1].length);
    const row = (r) => { const s = subjById(r.g.subject_id);
      return todoRow(r.g.lecture_id, r, `<a class="todo-src" href="#/lecture/${enc(r.g.lecture_id)}" title="${esc(r.g.title || "")}" style="--c:${s?.color || "#94a3b8"}">${esc(s?.short || "—")}${r.g.type && r.g.type !== "W" ? " · " + esc(r.g.type) : ""}</a>`); };
    const next = open.find((r) => r.due);
    setView(`<div class="page-head"><div><h1>Здати</h1><div class="sub">${open.length ? `${open.length} ${plural(open.length, "пункт", "пункти", "пунктів")}${next ? ` · найближче ${shortDue(next.due).t}` : ""}` : "Усе здано"} · з лаб і проєкту</div></div>
        <a class="btn ghost" href="#/" title="Дедлайни з ePortalu та свої — на головній">${icon("clock")} Дедлайни</a></div>
      ${subs.length > 1 ? `<div class="seg" id="td-subj" style="margin-bottom:14px"><button data-s="" class="${!subj ? "on" : ""}">Усі</button>${subs.map((id) => `<button data-s="${esc(id)}" class="${subj === id ? "on" : ""}">${esc(subjById(id)?.short || id)}</button>`).join("")}</div>` : ""}
      ${groups.length ? groups.map(([t, items, cls]) => `<div class="todo-group"><div class="todo-gh ${cls}">${t}<span>${items.length}</span></div><div class="card todo-card"><div class="todo-list">${items.map(row).join("")}</div></div></div>`).join("")
        : `<div class="card"><div class="empty">${icon("check")}<b>${all.length ? "Усе здано 🎉" : "Поки нічого здавати"}</b><span class="small">Після кожної лаби чи зустрічі проєкту Claude виписує сюди, що треба зробити й до коли.</span></div></div>`}
      ${done.length ? `<details class="todo-group todo-done"><summary class="todo-gh">Виконано<span>${done.length}</span></summary><div class="card todo-card"><div class="todo-list">${done.map(row).join("")}</div></div></details>` : ""}`, render);
    $$("#td-subj [data-s]").forEach((b) => (b.onclick = () => { subj = b.dataset.s; history.replaceState(null, "", "#/todo" + (subj ? "?subject=" + enc(subj) : "")); render(); }));
    bindTodos($("#view"), async () => { S.state = await GET("/api/state"); renderNav(); render(); });
  };
  await render();
}

// ---------------------------------------------------------------- 2.1: план до заняття і нові матеріали з ePortalu
function planHtml(L, outUrl) {
  const P = L.plan || {}; const hasTask = L.files.some((f) => f.kind === "task");
  const head = "";  // 2.7: чекліст — у секції «Що здати»
  if (P.pending) {
    return `${head}<div class="card pad"><h3 style="margin-top:0">${icon("clock")} Інструкція готується</h3>
      <p class="small muted" style="margin-top:0">${P.auto ? "Ви додали умову завдання — інструкцію поставлено в чергу автоматично." : "Інструкція в черзі Claude."} Він з'явиться тут сам: кроки виконання, що підготувати заздалегідь, заготовки коду, ризики й що здати.</p>
      ${claudeCallout(claudeWaiting() || 1)}
      <div class="btn-row" style="margin-top:10px"><button class="btn sm ghost" data-act="unplan">${icon("x")} Скасувати</button></div></div>
      ${P.has_plan ? `<details class="card pad" style="margin-top:14px"><summary style="cursor:pointer;font-weight:600">Попередня версія інструкції</summary><div class="md">${renderMarkdown(P.md || "")}</div></details>` : ""}`;
  }
  if (P.deferred && !P.pending) {
    return `${head}<div class="card pad"><h3 style="margin-top:0">${icon("clock")} Інструкція поставиться в чергу сама</h3>
      <p class="small muted" style="margin-top:0">Умову додано, але Claude ще відповідає на попередній запит по цьому заняттю. Щойно відповідь буде готова, інструкція піде в чергу автоматично — так відповіді не накладуться одна на одну.</p>${claudeCallout(claudeWaiting() || 1)}</div>
      ${P.has_plan ? `<div class="card pad md" style="margin-top:14px">${renderMarkdown(P.md || "")}</div>` : ""}`;
  }
  if (P.has_plan) {
    return `${head}<div class="btn-row" style="margin-bottom:10px">
        ${P.pdf ? `<a class="btn primary" href="${outUrl("plan.pdf", 1)}">${icon("download")} PDF інструкції</a><a class="btn" href="${outUrl("plan.pdf")}" target="_blank">${icon("external")} Відкрити</a>` : ""}
        <button class="btn" data-act="replan">${icon("refresh")} Оновити інструкцію</button>
        <span class="small muted">готовий ${relTime(P.completed_at)}</span></div>
      <div class="card pad md">${renderMarkdown(P.md || "")}</div>`;
  }
  return `${head}<div class="card"><div class="empty">${icon("list")}<b>Інструкції ще немає</b>
      ${hasTask ? "Умова є. Попроси інструкцію в чаті (кнопка «Скопіювати запит» вище) — Claude збереже її тут." : "Додай умову в «Завдання» (PDF, скріншот, фото), а тоді попроси інструкцію в чаті."}
      <div class="btn-row" style="justify-content:center;margin-top:12px">${hasTask ? `<button class="btn ghost sm" data-act="plan">${icon("sparkles")} Або через чергу Claude Code</button>` : `<button class="btn primary" data-tabgo="task">${icon("file")} До «Завдання»</button>`}</div></div></div>`;
}

function epNewBox(L) {
  const n = L.eportal_new || []; if (!n.length) return "";
  return `<div class="callout info" style="margin-top:14px">${icon("folder")}<div class="c-body"><div class="c-title">Нові матеріали з ePortalu</div>
    До ${L.status === "done" ? "готового конспекту" : "заняття"} додано: <b>${n.map((x) => esc(x.name)).join(", ")}</b>. Оновити ${OUT_LABEL[L.type] ? OUT_LABEL[L.type].toLowerCase() : "конспект"} і картки з урахуванням цих файлів?
    <div class="btn-row" style="margin-top:8px"><button class="btn sm primary" data-act="epnew-up">${icon("refresh")} Оновити</button><button class="btn sm ghost" data-act="epnew-x">Не треба</button></div></div></div>`;
}
