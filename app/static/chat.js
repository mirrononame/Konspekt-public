"use strict";
// ============================================================ 2.7: «Робота в чаті» — лаба чи проєкт у чаті Claude (Cowork)
// Застосунок складає CHAT.md, студент вставляє короткий запит у новий чат. Журнал (journal.md) пише Claude наприкінці чату.
// Підключається перед app.js; помічники ($, GET, icon…) використовуються лише під час виклику.

function chatPanel(kind, key, C) {
  C = C || {};
  const j = C.journal || [];
  const entry = (e) => `<div class="chat-j"><b>${esc(e.title)}</b><div class="md small">${renderMarkdown(e.body || "")}</div></div>`;
  const pc = !S.state.remote_client;
  return `<div class="card pad chat-card" data-chat-kind="${kind}" data-chat-key="${esc(key)}">
    <div class="section-head"><h2>${icon("sparkles")} Робота в чаті з Claude</h2>${C.built_at ? `<span class="small muted">запит складено ${relTime(C.built_at)}</span>` : ""}</div>
    <textarea class="input" id="chat-note" style="min-height:52px" placeholder="Що треба зараз (необов'язково): «зроби інструкцію», «крок 3 падає з Permission denied», «перевір звіт перед здачею»">${esc(C.note || "")}</textarea>
    <div class="btn-row" style="margin-top:8px">
      <button class="btn primary" data-chat="copy">${icon("copy")} Скопіювати запит</button>
      ${pc ? `<button class="btn" data-chat="claude">${icon("external")} Відкрити Claude</button><button class="btn" data-chat="folder">${icon("folder")} Папка</button>` : ""}
      <button class="btn ghost" data-chat="zip" title="Для чату без доступу до папки: телефон, інший сайт">${icon("download")} Пакет .zip</button></div>
    ${tip("chat-how", `Встав запит у <b>новий чат у проєкті Cowork «Конспект»</b> (папка <span class="mono">data</span>). Claude прочитає умову, твій код і журнал минулих чатів, а наприкінці допише журнал — наступний чат продовжить звідти ж.`)}
    ${j.length ? `<div class="chat-journal"><div class="label-t">Журнал чатів</div>${j.slice(0, 2).map(entry).join("")}
      ${j.length > 2 ? `<details><summary class="small" style="cursor:pointer">Ще ${j.length - 2}</summary>${j.slice(2).map(entry).join("")}</details>` : ""}</div>`
      : `<div class="small muted" style="margin-top:10px">Журнал порожній — перший чат з цим завданням.</div>`}
  </div>`;
}

function bindChat(after) {
  const card = $(".chat-card"); if (!card) return;
  const base = `/api/chat/${card.dataset.chatKind}/${enc(card.dataset.chatKey)}`;
  const build = () => POST(base, { note: $("#chat-note").value });
  const note = $("#chat-note");
  note.oninput = () => (S.dirty = !!note.value.trim());
  $$("[data-chat]", card).forEach((b) => (b.onclick = async () => {
    const a = b.dataset.chat;
    try {
      if (a === "folder") { await build(); await POST(`${base}/open-folder`); return; }
      const C = await build(); S.dirty = false;
      if (a === "copy" || a === "claude") {
        await copyText(C.prompt, "");
        if (a === "claude") await POST("/api/open-claude").catch(() => {});
        toast("Запит скопійовано — встав його в новий чат проєкту «Конспект»", "ok", 4000);
      } else if (a === "zip") {
        const x = document.createElement("a"); x.href = `${base}/zip`; x.download = ""; x.click();
        await copyText(C.prompt_zip, "").catch(() => {});
        toast("Пакет завантажується. Запит до нього вже скопійовано", "ok", 4000);
      }
      after && after();
    } catch (e) { handleErr(e); }
  }));
}

// 2.7: пояснення показуємо, доки студент не натисне «Зрозуміло»
function tip(id, html) {
  try { if (localStorage.getItem("tip:" + id)) return ""; } catch { }
  return `<div class="callout info tip" data-tip="${esc(id)}" style="margin-top:10px">${icon("info")}<div class="c-body small">${html}
    <div><button class="btn ghost sm" data-tipok style="margin-top:6px;padding-left:0">Зрозуміло</button></div></div></div>`;
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-tipok]"); if (!b) return;
  const t = b.closest("[data-tip]");
  try { localStorage.setItem("tip:" + t.dataset.tip, "1"); } catch { }
  t.remove();
});
