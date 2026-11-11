"use strict";
// ============================================================ 2.9: «Підключити Claude» і «Обмін конспектами» (Налаштування)
// Підключається перед app.js; помічники ($, GET, icon…) використовуються лише під час виклику.

function claudeSetupHtml(st) {
  const dir = st.data_dir || "data";
  return `<h2>${icon("sparkles")} Підключити Claude</h2>
    <ol class="small" style="margin:0 0 10px;padding-left:18px;display:flex;flex-direction:column;gap:6px;color:var(--text-2)">
      <li>Відкрий <b>Claude Desktop</b> → <b>Cowork</b> і створи проєкт «Конспект».</li>
      <li>Як папку проєкту вибери: <span class="mono" style="word-break:break-all">${esc(dir)}</span></li>
      <li>В інструкції проєкту встав текст нижче.</li>
      <li>Пиши в новому чаті проєкту: <b>«Оброби нові лекції»</b>. Готові PDF з'являться тут самі.</li>
    </ol>
    <div class="btn-row"><button class="btn sm" id="cl-copy-dir">${icon("copy")} Шлях до папки</button><button class="btn sm primary" id="cl-copy-instr">${icon("copy")} Інструкція проєкту</button>
      ${st.remote_client ? "" : `<button class="btn sm ghost" id="cl-open-dir">${icon("folder")} Відкрити папку</button>`}</div>
    <div class="small muted" style="margin-top:8px">Без Cowork: Claude Code у цій папці — та сама команда. Нічого платного не потрібно, лише підписка Claude.</div>`;
}

const CLAUDE_INSTR = `Це папка застосунку «Конспект». Спершу прочитай CLAUDE.md у цій папці й працюй за ним.
Не відкривай папки backups і trash. Пиши мені українською, коротко.`;

function shareHtml(subs) {
  if (!subs.length) return `<h2>${icon("archive")} Обмін конспектами</h2><div class="small muted">Предметів ще немає.</div>${shareImportHtml()}`;
  return `<h2>${icon("archive")} Обмін конспектами</h2>
    <p class="small muted" style="margin-top:0">Пакет для однокурсника: готові конспекти (PDF), інструкції до лаб, умови завдань, пам'ять предмета й план тем.
      Аудіо, твої нотатки, оцінки й ключі доступу в пакет не потрапляють.</p>
    <div class="list" id="sh-subs">${subs.map((s) => `<label class="check" style="padding:4px 0"><input type="checkbox" value="${esc(s.id)}" ${s.notes ? "checked" : "disabled"}>
      <div><b>${esc(s.name)}</b><span>${s.notes ? `${s.notes} ${plural(s.notes, "конспект", "конспекти", "конспектів")}` : "конспектів ще немає"}${s.project ? " · є проєкт" : ""}</span></div></label>`).join("")}</div>
    <details style="margin-top:6px"><summary class="small" style="cursor:pointer">Що ще додати</summary>
      <label class="check"><input type="checkbox" data-opt="transcripts"><div><b>Розшифровки</b><span>Текст лекцій — щоб Claude у друга міг переробити конспект</span></div></label>
      <label class="check"><input type="checkbox" data-opt="slides"><div><b>Слайди лекцій</b><span>Пакет стане помітно більшим</span></div></label>
      <label class="check"><input type="checkbox" data-opt="projects"><div><b>Проєкти</b><span>Етапи, кроки й актуальні документи</span></div></label>
      <label class="check"><input type="checkbox" data-opt="zdacha"><div><b>Файли до здачі (звіти, код)</b><span>Обережно: здана чужа робота — це плагіат</span></div></label></details>
    <div class="btn-row" style="margin-top:10px"><input class="input" id="sh-author" placeholder="Твоє ім'я (побачить друг)" style="flex:1;min-width:140px">
      <button class="btn primary" id="sh-export">${icon("download")} Завантажити пакет</button></div>
    ${shareImportHtml()}`;
}

function shareImportHtml() {
  return `<div style="margin-top:16px;border-top:1px solid var(--border);padding-top:12px">
    <b class="small">Отримав пакет від друга?</b>
    <div class="dropzone" id="sh-dz" style="padding:16px;margin-top:8px"><div class="t">${icon("upload")} Вибери або перетягни .zip</div><div class="s" id="sh-st">Свої конспекти не перезаписуються</div><input type="file" id="sh-in" accept=".zip" hidden></div>
    <div id="sh-prev"></div></div>`;
}

async function loadShare(st) {
  const cc = $("#claude-card"), sc = $("#share-card");
  if (cc) {
    cc.innerHTML = claudeSetupHtml(st);
    $("#cl-copy-dir").onclick = () => copyText(st.data_dir || "", "Шлях скопійовано");
    $("#cl-copy-instr").onclick = () => copyText(CLAUDE_INSTR, "Інструкцію скопійовано — встав її в проєкт Cowork");
    $("#cl-open-dir") && ($("#cl-open-dir").onclick = () => POST("/api/open-data-folder").catch(handleErr));
  }
  if (!sc) return;
  sc.innerHTML = shareHtml(await GET("/api/share/subjects").catch(() => []));
  $("#sh-export") && ($("#sh-export").onclick = async (e) => {
    const subjects = $$("#sh-subs input:checked").map((i) => i.value);
    if (!subjects.length) return toast("Вибери хоча б один предмет", "err");
    const options = Object.fromEntries($$("[data-opt]").map((i) => [i.dataset.opt, i.checked]));
    const btn = e.currentTarget; btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Збираю…';
    try {
      const r = await fetch("/api/share/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subjects, options, author: $("#sh-author").value }) });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Помилка ${r.status}`);
      const name = (r.headers.get("content-disposition") || "").match(/filename="?([^";]+)/)?.[1] || "Konspekt.zip";
      const a = document.createElement("a"); a.href = URL.createObjectURL(await r.blob()); a.download = name; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
      toast("Пакет готовий — надішли його другу");
    } catch (er) { handleErr(er); }
    btn.disabled = false; btn.innerHTML = `${icon("download")} Завантажити пакет`;
  });
  const dz = $("#sh-dz"), fi = $("#sh-in");
  const take = async (f) => {
    if (!f) return;
    $("#sh-st").textContent = `Перевіряю ${f.name}…`;
    const fd = new FormData(); fd.append("file", f, f.name);
    try {
      const p = await api("/api/share/preview", { method: "POST", body: fd });
      $("#sh-st").textContent = f.name;
      const row = (s) => `<li><b>${esc(s.name)}</b> — ${s.match ? `до твого «${esc(s.match)}»` : "новий предмет"}: нових ${s.new}${s.fill ? `, доповнить ${s.fill}` : ""}${s.skip ? `, пропустить ${s.skip} (у тебе вже є)` : ""}${s.project ? ", проєкт" : ""}</li>`;
      $("#sh-prev").innerHTML = `<div class="callout info" style="margin-top:10px">${icon("info")}<div class="c-body small">
        <div class="c-title">Пакет${p.author ? ` від ${esc(p.author)}` : ""}</div><ul style="margin:4px 0;padding-left:18px">${p.subjects.map(row).join("")}</ul>
        <button class="btn sm primary" id="sh-go">${icon("check")} Імпортувати</button></div></div>`;
      $("#sh-go").onclick = async () => {
        try {
          const r = await POST("/api/share/import", { token: p.token });
          toast(`Додано конспектів: ${r.lectures_new + r.lectures_filled}${r.subjects_added.length ? `, нових предметів: ${r.subjects_added.length}` : ""}`);
          S.schedule = await GET("/api/schedule"); loadShare(st);
        } catch (er) { handleErr(er); }
      };
    } catch (er) { $("#sh-st").textContent = "Свої конспекти не перезаписуються"; handleErr(er); }
  };
  dz.onclick = () => fi.click(); fi.onchange = () => take(fi.files[0]);
  dz.ondragover = (e) => { e.preventDefault(); dz.classList.add("over"); };
  dz.ondragleave = () => dz.classList.remove("over");
  dz.ondrop = (e) => { e.preventDefault(); e.stopPropagation(); dz.classList.remove("over"); hideOverlay(); take(e.dataTransfer.files[0]); };
}
