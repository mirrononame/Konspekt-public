"use strict";
// ============================================================ 2.4: «Проєкт» (вкладка предмета)
// Етапи з датами, одна актуальна версія кожного файлу. 2.7: працюємо в чаті Claude (chat.js), кроки через чергу — запасний шлях.
// Підключається перед app.js; помічники ($, GET, icon…) використовуються лише під час виклику.

function projectHtml(sid, P, C) {
  const url = (area, f, dl) => `/api/subjects/${enc(sid)}/project/file/${area}/${f.split("/").map(encodeURIComponent).join("/")}${dl ? "?download=1" : ""}`;
  if (!P.exists) return `<div class="card pad"><h3 style="margin-top:0">${icon("grad")} Почати проєкт</h3>
    <p class="small muted" style="margin-top:0">Проєкт живе тут, а не в записі однієї зустрічі. Етапи з датами, <b>один крок за раз</b> (що зробити, як перевірити, що надіслати), одна актуальна версія кожного файлу — старі переносяться у «Версії» самі.</p>
    <div class="btn-row"><input class="input" id="pj-title" placeholder="Назва проєкту" style="flex:1;min-width:200px"><button class="btn primary" id="pj-create">${icon("plus")} Почати</button></div></div>`;
  const step = P.open_step;
  const stageChips = P.stages.length ? `<div class="pj-stages">${P.stages.map((s) => `<button class="pj-stage ${s.id === P.current_stage ? "on" : ""} ${s.status === "done" ? "done" : ""}" data-pjstage="${esc(s.id)}" title="${esc(s.requirements || "")}">
      <b>${esc(s.title || s.id)}</b><span class="small">${s.due ? fmtDate(s.due.slice(0, 10)) : "без дати"}${s.status === "done" ? " · зроблено" : ""}</span></button>`).join("")}</div>`
    : `<div class="small muted">Етапи з датами Claude складе з «Etapy realizacji projektu» під час першого кроку.</div>`;
  const curStage = P.stages.find((s) => s.id === P.current_stage && s.status !== "done");
  const stageBtn = curStage ? `<div class="btn-row" style="margin-top:10px"><button class="btn sm" style="white-space:normal;text-align:left;height:auto" data-pjstagedone="${esc(curStage.id)}">${icon("check")} «${esc(curStage.title || curStage.id)}» здано → наступний етап</button></div>` : "";
  const stepCard = P.pending ? `<div class="card pad pj-step"><div class="small">${icon("clock")} Claude готує крок ${P.req.n}${P.req.note ? `: «${esc(P.req.note)}»` : ""}. Поки він працює, нові запити по проєкту не приймаються — щоб не було двох версій.</div>
      <div class="btn-row" style="margin-top:8px"><button class="btn ghost sm" id="pj-cancel">Скасувати запит</button></div></div>`
    : step ? `<div class="card pad pj-step"><div class="pj-step-h"><span class="badge">Крок ${step.n}</span><b>${esc(step.title)}</b>${step.minutes ? `<span class="small muted">≈ ${step.minutes} хв</span>` : ""}</div>
      <div class="md">${renderMarkdown(step.md)}</div>
      ${step.check ? `<div class="callout info" style="margin-top:10px">${icon("check")}<div class="c-body small"><b>Як перевірити:</b> ${esc(step.check)}</div></div>` : ""}
      ${step.send_back.length ? `<div class="small" style="margin-top:8px"><b>Надішли назад</b> (у «Мої робочі»): ${step.send_back.map(esc).join(", ")}</div>` : ""}
      <div class="btn-row" style="margin-top:10px"><button class="btn primary sm" data-pjdone="${step.n}">${icon("check")} Зроблено</button><button class="btn sm" data-pjup="work">${icon("upload")} Надіслати результат</button></div></div>`
    : `<div class="card"><div class="empty">${icon("check")}<b>${P.steps.length ? "Усі кроки зроблені" : "Кроків ще немає"}</b><span class="small">Попроси наступний крок — Claude дасть один, на 15–60 хв.</span></div></div>`;
  const ask = P.pending ? "" : `<div class="card pad" style="margin-top:10px"><textarea class="input" id="pj-note" style="min-height:56px" placeholder="Що змінилось або що потрібно (необов’язково): «імпорт XMI вдався», «викладач попросив…»"></textarea>
    <div class="btn-row" style="margin-top:8px"><button class="btn primary sm" data-pjask="next">${icon("right")} Наступний крок</button>
      ${step ? `<button class="btn sm" data-pjask="fix">${icon("edit")} Виправити цей крок</button>` : ""}
      <button class="btn ghost sm" data-pjask="stage" title="Лише якщо дуже треба: Claude зробить увесь поточний етап за раз">Увесь етап одразу</button></div>
    ${step && !step.done ? `<div class="small muted" style="margin-top:6px">Спершу заверш крок ${step.n} — так Claude побачить результат і не дублюватиме роботу.</div>` : ""}</div>`;
  const list = (area, files, extra) => files.length ? `<div class="list">${files.map((f) => `<div class="row" style="padding:8px 2px"><div class="body"><div class="title">${esc(f.name)}</div><div class="meta">${fmtSize(f.size)} · ${relTime(f.mtime)}</div></div>
      <div class="right"><a class="btn sm" href="${url(area, f.name)}" target="_blank">${icon("external")}</a><a class="btn ghost icon sm" href="${url(area, f.name, 1)}" title="Завантажити">${icon("download")}</a>${extra ? extra(f) : ""}</div></div>`).join("")}</div>` : `<div class="small muted">Порожньо</div>`;
  const F = P.files;
  return `<div style="display:flex;flex-direction:column;gap:14px">
    <div class="card pad"><div class="section-head"><h2>${icon("grad")} ${esc(P.title)}</h2></div>${stageChips}${stageBtn}</div>
    ${chatPanel("project", sid, C)}
    ${P.pending || (step && !step.done) ? stepCard : ""}
    <details class="lsec"><summary>${icon("list")} <b>Кроки через чергу Claude Code</b> <span class="small muted">запасний спосіб</span></summary>${P.pending || (step && !step.done) ? "" : stepCard}${ask}</details>
    <div class="grid cols-2">
      <div class="card pad"><div class="section-head"><h3 style="margin:0">${icon("check")} Актуальне (для здачі)</h3><button class="btn sm" data-pjup="current" title="Завантажити нову версію">${icon("upload")}</button></div>${list("current", F.current)}</div>
      <div class="card pad"><div class="section-head"><h3 style="margin:0">${icon("edit")} Мої робочі</h3><button class="btn sm" data-pjup="work" title="Завантажити">${icon("upload")}</button></div>
        ${list("work", F.work, (f) => `<button class="btn ghost sm" data-pjpromote="${esc(f.name)}" title="Зробити актуальним (для здачі)">${icon("check")}</button>`)}
        <div class="small muted" style="margin-top:6px">Правиш документ — бери свою копію звідси, а не з «Актуального».</div></div>
    </div>
    <details class="card pad"><summary class="small" style="cursor:pointer">${icon("archive")} Попередні версії (${F.versions.length})</summary><div style="margin-top:8px">${list("versions", F.versions)}</div></details>
    ${P.steps.length ? `<details class="card pad"><summary class="small" style="cursor:pointer">${icon("list")} Усі кроки (${P.steps.length})</summary>${P.steps.slice().reverse().map((s) => `<details class="pj-old"><summary>${s.done ? "✓" : "○"} Крок ${s.n}: ${esc(s.title)}</summary><div class="md">${renderMarkdown(s.md)}</div>${s.done ? `<button class="btn ghost sm" data-pjundo="${s.n}">Знову відкрити</button>` : ""}</details>`).join("")}</details>` : ""}
    ${P.changelog.length ? `<details class="card pad"><summary class="small" style="cursor:pointer">${icon("clock")} Журнал змін</summary>${P.changelog.map((c) => `<div class="small"><span class="muted">${esc(new Date(c.at).toLocaleString("uk-UA", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }))}</span> ${esc(c.text)}</div>`).join("")}</details>` : ""}
    <input type="file" id="pj-file" hidden multiple>
  </div>`;
}

function bindProject(sid, after) {
  const base = `/api/subjects/${enc(sid)}/project`;
  const go = async (p) => { try { await p; after(); } catch (e) { handleErr(e); } };
  $("#pj-create") && ($("#pj-create").onclick = () => go(POST(base, { title: $("#pj-title").value })));
  $("#pj-cancel") && ($("#pj-cancel").onclick = () => go(DEL(`${base}/step`)));
  $$("[data-pjask]").forEach((b) => (b.onclick = async () => {
    const kind = b.dataset.pjask;
    if (kind === "stage" && !(await confirmBox("Увесь етап одразу?", "Claude зробить усі кроки поточного етапу за раз. Так легше заплутатися у версіях — краще по одному кроку.", "Так, увесь етап"))) return;
    go(POST(`${base}/step`, { kind, note: $("#pj-note")?.value || "" }).then(() => toast("Запит у черзі Claude", "info")));
  }));
  $$("[data-pjdone]").forEach((b) => (b.onclick = () => go(POST(`${base}/step/${b.dataset.pjdone}/done`, { done: true }))));
  $$("[data-pjundo]").forEach((b) => (b.onclick = () => go(POST(`${base}/step/${b.dataset.pjundo}/done`, { done: false }))));
  $$("[data-pjstage]").forEach((b) => (b.onclick = async () => {
    if (b.classList.contains("done")) {  // здано помилково — повернути
      if (await confirmBox("Етап ще не здано?", "Повернути етап у роботу?", "Так, повернути")) go(POST(`${base}/stage-done`, { stage: b.dataset.pjstage, done: false }));
      return;
    }
    go(POST(`${base}/stage`, { stage: b.dataset.pjstage }));
  }));
  $$("[data-pjstagedone]").forEach((b) => (b.onclick = async () => {
    if (!(await confirmBox("Етап здано?", "Наступний крок Claude робитиме вже для наступного етапу.", "Так, здано"))) return;
    go(POST(`${base}/stage-done`, { stage: b.dataset.pjstagedone, done: true }).then(() => toast("Етап здано — далі наступний")));
  }));
  $$("[data-pjpromote]").forEach((b) => (b.onclick = async () => {
    if (!(await confirmBox("Зробити актуальним?", `«${esc(b.dataset.pjpromote)}» стане версією для здачі. Попередня з такою самою назвою перейде у «Версії».`, "Так"))) return;
    go(POST(`${base}/promote`, { name: b.dataset.pjpromote }));
  }));
  const fi = $("#pj-file");
  $$("[data-pjup]").forEach((b) => (b.onclick = () => { fi.dataset.area = b.dataset.pjup; fi.click(); }));
  if (fi) fi.onchange = async () => {
    for (const f of fi.files) {
      const fd = new FormData(); fd.append("file", f); fd.append("area", fi.dataset.area || "work");
      try { await api(`${base}/files`, { method: "POST", body: fd }); toast(`Завантажено: ${esc(f.name)}`); } catch (e) { handleErr(e); }
    }
    fi.value = ""; after();
  };
}

// зустріч проєкту (тип P): файли й кроки — на сторінці предмета
function projectMeetingBox(L) {
  if (!L.project_meeting) return "";
  return `<div class="callout info" style="margin-top:14px">${icon("grad")}<div class="c-body"><div class="c-title">Це зустріч проєкту</div>
    Тут — лише конспект зустрічі. Етапи, файли й робота в чаті — у <a href="#/subject/${enc(L.subject_id)}?tab=project">Предмет → Проєкт</a>.</div></div>`;
}
