"""2.7: «Робота в чаті» — лаба чи проєкт опрацьовується в окремому чаті Claude (Cowork), а не через чергу.

Застосунок складає CHAT.md — усе, що чату треба знати: умова, файли, що вже зроблено, терміни, пам'ять предмета.
Чат працює з папкою data (проєкт Cowork «Конспект») або з архівом-пакетом і наприкінці дописує journal.md.
Наступний CHAT.md містить цей журнал, тому новий чат продовжує з того місця, де зупинився попередній.

  lectures/<id>/CHAT.md, journal.md                — лаба / вправи / семінар
  subjects/<sid>/project/CHAT.md, journal.md       — проєкт предмета
Правила для Claude — protocol/M_chat.md.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from . import course, lectures, project, storage
from .schedule import TYPES, load_schedule

PROTOCOL = "protocol/M_chat.md"
MAX_ZIP_FILE = 25 * 1024 * 1024  # більші файли (відео, великі архіви) у пакет не кладемо
JOURNAL_SHOWN = 5                # скільки останніх записів журналу йде в CHAT.md


def _rel(p: Path) -> str:
    return p.relative_to(storage.DATA_DIR).as_posix()


def journal(path: Path) -> list[dict]:
    """Записи журналу: кожен починається з «## …». Найновіший — останній."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    out = []
    for block in re.split(r"(?m)^(?=## )", text):
        block = block.strip()
        if not block.startswith("## "):
            continue
        head, _, body = block.partition("\n")
        out.append({"title": head[3:].strip(), "body": body.strip()})
    return out


def _journal_md(path: Path) -> str:
    entries = journal(path)
    if not entries:
        return "Ще порожній — це перший чат з цим завданням."
    skipped = len(entries) - JOURNAL_SHOWN
    shown = entries[-JOURNAL_SHOWN:]
    head = f"_(Ще {skipped} старіших записів — у `{_rel(path)}`.)_\n\n" if skipped > 0 else ""
    return head + "\n\n".join(f"### {e['title']}\n{e['body']}" for e in shown)


def _list(items: list[str], empty: str = "немає") -> str:
    return "\n".join(f"  - `{x}`" for x in items) if items else f"  - {empty}"


# ---------------------------------------------------------------- лаба
def lecture_paths(lid: str) -> tuple[Path, Path]:
    d = lectures.lecture_dir(lid)
    return d / "CHAT.md", d / "journal.md"


def build_lecture(lid: str, note: str = "") -> dict:
    m = lectures.enrich(lectures.read_meta(lid), full=True)
    if m.get("type") not in ("L", "C", "S", "P"):
        raise ValueError("«Робота в чаті» — для лаб, вправ, семінарів і проєктів. Лекції обробляються як раніше.")
    if project.is_project_meeting(m):
        raise ValueError("Це зустріч проєкту — працюй у чаті проєкту: «Предмет → Проєкт → Робота в чаті».")
    note = (note or "").strip()[:3000]
    lectures.mutate(lid, lambda x: x.__setitem__("chat", {"note": note, "built_at": storage.now_iso()}))
    d = lectures.lecture_dir(lid)
    chat_p, jour_p = lecture_paths(lid)
    rel = _rel(d)
    sj = m.get("subject") or {}
    pr = course.progress(m)
    ctx = lectures._context(m, lectures.list_all())
    dl = lectures._subject_deadlines(m.get("subject_id"))
    plan = d / "output" / "plan.md"
    ws = [f"{w['folder']}/output/notes.md" + (f" — {w['date']}" if w.get("date") else "") for w in (ctx.get("lectures_w") or [])][-6:]
    text = f"""# Робота в чаті: {sj.get('name', 'без предмета')} — {TYPES.get(m.get('type'), m.get('type'))} {m.get('date', '')}

_Склав застосунок «Конспект» {storage.now_iso()[:16].replace('T', ' ')}. Не редагуй цей файл — він перезаписується щоразу,
коли студент натискає «Робота в чаті». Твої записи — у `journal.md`._

## Запит студента
{note or "Студент нічого не дописав. Подивись журнал нижче: продовж з «Далі», а якщо журнал порожній — почни з інструкції."}

## Як працювати
Спершу прочитай `{PROTOCOL}` (правила роботи в чаті). Шляхи тут — від папки `data` застосунку
(або від кореня архіву, якщо тобі дали пакет .zip). Мова документів для здачі — `{m.get('notes_language') or 'pl'}`,
відповідай студенту українською.

## Завдання
- Папка заняття: `{rel}/`
- Умова (task):
{_list([f"{rel}/task/{f['name']}" for f in m['files'] if f['kind'] == 'task'], "умови ще немає — попроси студента кинути її в застосунок (вкладка «Завдання»)")}
- Код студента:
{_list([f"{rel}/code/{f['name']}" for f in m['files'] if f['kind'] == 'code'])}
- Інструкція (одна, оновлюється на місці): `{rel}/output/plan.md` — {"є" if plan.exists() else "ще немає"}
- Файли до здачі: `{rel}/output/zdacha/`
- Студент відмітив зробленим: {"; ".join(pr["done"]) or "нічого"}
- Ще не зроблено: {"; ".join(pr["open"]) or "—"}{" · **уже здано**" if pr.get("submitted") else ""}

## Терміни
{chr(10).join(f"- {x['due']}: {x['title']}" for x in dl) or "- у застосунку термінів немає; якщо є в умові — виконуй за умовою"}

## Контекст предмета
- Пам'ять предмета: `{ctx.get('memory') or ctx.get('memory_target') or '—'}`
- Конспекти лекцій (найсвіжіші):
{_list(ws)}
- Попереднє заняття того ж типу: `{ctx.get('previous_same_type') or '—'}`

## Журнал попередніх чатів
{_journal_md(jour_p)}

## Наприкінці
Допиши запис у кінець `{_rel(jour_p)}` (формат — у `{PROTOCOL}`).
"""
    chat_p.write_text(text, encoding="utf-8", newline="\n")
    return lecture_info(lid)


def lecture_info(lid: str) -> dict:
    m = lectures.read_meta(lid)
    chat_p, jour_p = lecture_paths(lid)
    rel = _rel(chat_p)
    return {"exists": chat_p.exists(), "built_at": (m.get("chat") or {}).get("built_at"), "note": (m.get("chat") or {}).get("note", ""),
            "chat_md": rel, "folder": str(chat_p.parent), "journal": journal(jour_p)[::-1],
            "prompt": f"Працюємо в «Конспекті». Прочитай {rel} і працюй за ним.",
            "prompt_zip": "У вкладенні пакет із «Конспекту». Прочитай CHAT.md у корені архіву і працюй за ним."}


def _lecture_files(lid: str) -> list[Path]:
    m = lectures.read_meta(lid)
    d = lectures.lecture_dir(lid)
    out = [d / "CHAT.md", d / "journal.md", d / "output" / "plan.md", d / "output" / "notes.md"]
    out += [d / f["kind"] / f["name"] for f in m.get("files", []) if f.get("kind") in ("task", "code")]
    out += sorted((d / "output" / "zdacha").rglob("*")) if (d / "output" / "zdacha").is_dir() else []
    ctx = lectures._context(lectures.enrich(m), lectures.list_all())
    if ctx.get("memory"):
        out.append(storage.DATA_DIR / ctx["memory"])
    out += [storage.DATA_DIR / w["folder"] / "output" / "notes.md" for w in (ctx.get("lectures_w") or [])[-6:]]
    return out


# ---------------------------------------------------------------- проєкт
def project_paths(sid: str) -> tuple[Path, Path]:
    p = project.pdir(sid)
    return p / "CHAT.md", p / "journal.md"


def build_project(sid: str, note: str = "") -> dict:
    if not project.exists(sid):
        raise ValueError("У цьому предметі ще немає проєкту")
    note = (note or "").strip()[:3000]
    d = project._meta(sid)
    d["chat"] = {"note": note, "built_at": storage.now_iso()}
    project._save(sid, d)
    P = project.info(sid)
    chat_p, jour_p = project_paths(sid)
    rel = _rel(project.pdir(sid))
    items = lectures.list_all()
    meetings = sorted((x for x in items if x.get("subject_id") == sid and x.get("type") == "P"), key=lambda x: x.get("date") or "")[-6:]
    stg = P["stages"]
    stages_md = "\n".join(f"- {'✓ ' if s.get('status') == 'done' else ''}**{s['id']}** {s.get('title', '')}"
                          + (f" — до {s['due']}" if s.get("due") else "") + (" ← поточний" if s["id"] == P["current_stage"] else "")
                          for s in stg) or f"- етапів ще немає — склади `{rel}/stages.json` за вимогами викладача (формат — у `{PROTOCOL}`)"
    sj = next((s for s in load_schedule()["subjects"] if s["id"] == sid), {})
    dl = lectures._subject_deadlines(sid)
    text = f"""# Робота в чаті: {P.get('title') or 'Projekt'} ({sj.get('name', sid)})

_Склав застосунок «Конспект» {storage.now_iso()[:16].replace('T', ' ')}. Не редагуй цей файл — він перезаписується щоразу,
коли студент натискає «Робота в чаті». Твої записи — у `journal.md`._

## Запит студента
{note or "Студент нічого не дописав. Подивись журнал нижче: продовж з «Далі», а якщо журнал порожній — почни з плану етапів."}

## Як працювати
Спершу прочитай `{PROTOCOL}` (правила роботи в чаті, розділ «Проєкт»). Шляхи — від папки `data` застосунку
(або від кореня архіву .zip). Документи проєкту — мовою `{d.get('docs_language', 'pl')}`, студенту відповідай українською.

## Етапи
{stages_md}

## Файли проєкту (`{rel}/`)
- Актуальні версії (`current/`) — лише тут лежить «остання версія» кожного документа:
{_list([f"{rel}/current/{f['name']}" for f in P['files']['current']])}
- Робочі файли студента (`work/`, не змінюй):
{_list([f"{rel}/work/{f['name']}" for f in P['files']['work']])}
- Старі версії — `{rel}/versions/` (не читай без потреби)

## Зустрічі з викладачем
{chr(10).join(f"- {x.get('date')}: `lectures/{x['id']}/output/notes.md`" for x in meetings) or "- записів зустрічей немає"}

## Терміни
{chr(10).join(f"- {x['due']}: {x['title']}" for x in dl) or "- у застосунку термінів немає"}

## Контекст предмета
- Пам'ять предмета: `subjects/{sid}/memory.md`

## Журнал попередніх чатів
{_journal_md(jour_p)}

## Наприкінці
Допиши запис у кінець `{_rel(jour_p)}` (формат — у `{PROTOCOL}`).
"""
    chat_p.write_text(text, encoding="utf-8", newline="\n")
    return project_info(sid)


def project_info(sid: str) -> dict:
    if not project.exists(sid):
        return {"exists": False}
    chat_p, jour_p = project_paths(sid)
    ch = project._meta(sid).get("chat") or {}
    rel = _rel(chat_p)
    return {"exists": chat_p.exists(), "built_at": ch.get("built_at"), "note": ch.get("note", ""), "chat_md": rel,
            "folder": str(chat_p.parent), "journal": journal(jour_p)[::-1],
            "prompt": f"Працюємо в «Конспекті». Прочитай {rel} і працюй за ним.",
            "prompt_zip": "У вкладенні пакет із «Конспекту». Прочитай CHAT.md у корені архіву і працюй за ним."}


def _project_files(sid: str) -> list[Path]:
    p = project.pdir(sid)
    out = [p / "CHAT.md", p / "journal.md", p / "stages.json", storage.DATA_DIR / "subjects" / sid / "memory.md"]
    out += [p / "current" / f["name"] for f in project._files(p / "current")]
    out += [p / "work" / f["name"] for f in project._files(p / "work")]
    out += [lectures.lecture_dir(x["id"]) / "output" / "notes.md" for x in lectures.list_all()
            if x.get("subject_id") == sid and x.get("type") == "P"]
    return out


# ---------------------------------------------------------------- пакет .zip
def make_zip(kind: str, key: str) -> Path:
    """Пакет для чату на телефоні чи на іншому сайті: CHAT.md у корені + файли за тими ж шляхами, що й у data."""
    if kind == "lecture":
        build_lecture(key, (lectures.read_meta(key).get("chat") or {}).get("note", ""))
        files, chat_p = _lecture_files(key), lecture_paths(key)[0]
    else:
        build_project(key, (project._meta(key).get("chat") or {}).get("note", ""))
        files, chat_p = _project_files(key), project_paths(key)[0]
    storage.TMP_DIR.mkdir(parents=True, exist_ok=True)
    target = storage.TMP_DIR / f"chat_{kind}_{re.sub(r'[^A-Za-z0-9_-]', '_', key)}.zip"
    proto = storage.DATA_DIR / PROTOCOL
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(chat_p, "CHAT.md")
        if proto.exists():
            z.write(proto, PROTOCOL)
        seen = set()
        for f in files:
            if f in seen or not f.is_file() or f.stat().st_size > MAX_ZIP_FILE or project.TEMP_RX.search(f.name):
                continue
            seen.add(f)
            z.write(f, _rel(f))
    return target

