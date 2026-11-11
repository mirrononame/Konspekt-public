"""Заняття за типом (2.0): пам'ять предмета, карта курсу, «Допоможи з задачею», чекліст здачі.

data/subjects/<id>/memory.md        — «пам'ять предмета», веде Claude після кожного заняття
data/subjects/<id>/course_map.json  — карта курсу: тема викладу → лаби/проєкт, де вона потрібна (пише Claude)
data/lectures/<id>/task/            — умова завдання (ePortal / фото / PDF) — для L/P/C
data/lectures/<id>/code/            — «Мій код» (файли або архів)
meta.json → help: [{id, q, asked_at}]          — питання «Допоможи з задачею» (пише застосунок)
output/help.md                                  — відповіді Claude, кожна після рядка <!-- help:<id> -->
output/result.json → checklist: [{text, due?}]  — чекліст здачі (пише Claude); виконане — meta.json → checklist_done
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime

from . import lectures, materials, storage

HELP_RX = re.compile(r"<!--\s*help:([A-Za-z0-9_-]+)\s*-->")


def _read(p) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    except OSError:
        return ""


# ---------------------------------------------------------------- пам'ять предмета і карта курсу
def memory(sid: str) -> dict:
    d = materials.SUBJECTS_DIR / materials._sid(sid)
    p = d / "memory.md"
    st = p.stat() if p.exists() else None
    return {"text": _read(p), "updated_at": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds") if st else None}


def course_map(sid: str) -> dict:
    d = materials.SUBJECTS_DIR / materials._sid(sid)
    data = storage.read_json(d / "course_map.json", {}) or {}
    items = []
    lect = {m["id"]: m for m in lectures.list_all() if m.get("subject_id") == sid}
    for it in data.get("items", []) if isinstance(data, dict) else []:
        if not isinstance(it, dict) or not (it.get("topic") or it.get("title")):
            continue
        lid = it.get("lecture_id") or ""
        labs = []
        for lb in it.get("labs") or it.get("used_in") or []:
            if isinstance(lb, str):
                lb = {"title": lb}
            if isinstance(lb, dict):
                l2 = lb.get("lecture_id") or ""
                labs.append({"title": str(lb.get("title") or lb.get("lab") or "")[:200], "type": str(lb.get("type") or "L")[:1],
                             "n": lb.get("n"), "lecture_id": l2 if l2 in lect else "", "how": str(lb.get("how") or "")[:300]})
        items.append({"topic": str(it.get("topic") or it.get("title"))[:300], "date": str(it.get("date") or "")[:10],
                      "lecture_id": lid if lid in lect else "", "labs": labs})
    return {"items": items, "updated_at": data.get("updated_at") if isinstance(data, dict) else None}


# ---------------------------------------------------------------- «Допоможи з задачею»
def help_answers(lid: str) -> dict[str, str]:
    md = _read(lectures.lecture_dir(lid) / "output" / "help.md")
    out, parts = {}, HELP_RX.split(md)
    # parts: [до першої мітки, id1, текст1, id2, текст2, ...]
    for i in range(1, len(parts) - 1, 2):
        out[parts[i]] = parts[i + 1].strip()
    return out


def help_list(lid: str) -> list[dict]:
    meta = lectures.read_meta(lid)
    ans = help_answers(lid)
    return [{**h, "answer": ans.get(h["id"]), "answered": h["id"] in ans} for h in meta.get("help", [])]


def ask_help(lid: str, q: str) -> list[dict]:
    q = str(q or "").strip()
    if not q:
        raise ValueError("Напишіть питання")
    from . import project
    busy_error(lectures.read_meta(lid))  # 2.6: один запит за раз
    if project.is_project_meeting(lectures.read_meta(lid)):  # 2.4: один канал до Claude для проєкту
        raise ValueError("Це зустріч проєкту: питання й прохання — у «Предмет → Проєкт → Наступний крок», щоб не було паралельних версій")
    h = {"id": "h" + secrets.token_hex(4), "q": q[:5000], "asked_at": storage.now_iso()}
    lectures.mutate(lid, lambda m: m.setdefault("help", []).append(h))
    lectures.write_queue()
    return help_list(lid)


def delete_help(lid: str, hid: str) -> list[dict]:
    lectures.mutate(lid, lambda m: m.__setitem__("help", [x for x in m.get("help", []) if x.get("id") != hid]))
    lectures.write_queue()
    return help_list(lid)


def pending_help() -> list[dict]:
    out = []
    if not storage.LECTURES_DIR.exists():
        return out
    for d in storage.LECTURES_DIR.iterdir():
        meta = storage.read_json(d / "meta.json", {}) or {}
        hs = meta.get("help") if isinstance(meta, dict) else None
        if not hs:
            continue
        try:
            ans = help_answers(d.name)
        except KeyError:
            continue
        qs = [h for h in hs if h.get("id") not in ans]
        if qs:
            out.append({"lecture_id": d.name, "folder": f"lectures/{d.name}", "subject_id": meta.get("subject_id"),
                        "type": meta.get("type"), "questions": qs, "answer_file": f"lectures/{d.name}/output/help.md",
                        "instruction": f"lectures/{d.name}/output/plan.md" if (d / "output" / "plan.md").exists() else None,
                        "progress": progress(lectures.enrich(meta, full=True)) if meta.get("id") else {}})
    return out


# ---------------------------------------------------------------- чекліст здачі
def _cid(text: str) -> str:
    return hashlib.sha1(text.strip().lower().encode("utf-8")).hexdigest()[:8]


def checklist(m: dict) -> list[dict]:
    res = (m.get("output") or {}).get("result") or {}
    items = list(res.get("checklist") or []) if isinstance(res, dict) and isinstance(res.get("checklist"), list) else []
    try:  # 2.1: пункти з плану до заняття (plan.json) — якщо їх ще немає в посібнику
        pj = _plan_json(m["id"]) if m.get("id") else {}
        have = {_cid(str(i.get("text") if isinstance(i, dict) else i or "")) for i in items}
        for it in pj.get("checklist") or [] if isinstance(pj.get("checklist"), list) else []:
            t = str(it.get("text") if isinstance(it, dict) else it or "")
            if t.strip() and _cid(t) not in have:
                items.append(it)
                have.add(_cid(t))
    except (KeyError, OSError):
        pass
    done = set(m.get("checklist_done") or [])
    out = []
    seen = set()
    for it in items:
        if isinstance(it, str):
            it = {"text": it}
        if not isinstance(it, dict) or not str(it.get("text") or "").strip():
            continue
        t = str(it["text"]).strip()[:300]
        if _cid(t) in seen:
            continue
        seen.add(_cid(t))
        due = str(it.get("due") or "")[:16]
        if due and not re.fullmatch(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?", due):
            due = ""
        out.append({"id": _cid(t), "text": t, "due": (due + "T23:59") if len(due) == 10 else due, "done": _cid(t) in done})
    return out


def progress(m: dict) -> dict:
    """2.6: що студент уже зробив і що ні — Claude бачить це й не повторює зроблене (кінець «циклам»)."""
    items = checklist(m)
    return {"done": [i["text"] for i in items if i["done"]], "open": [i["text"] for i in items if not i["done"]],
            "submitted": bool(m.get("submitted_at"))}


def busy_reason(m: dict) -> str | None:
    """2.6: для лаб/проєктів/вправ — лише один запит до Claude за раз, щоб відповіді не накладались одна на одну."""
    if (m.get("type") or "W") not in PLAN_TYPES:
        return None
    if lectures.enrich(m)["status"] == "waiting_claude":
        return "конспект"
    if plan_info(m["id"], m)["pending"]:
        return "інструкція"
    if m.get("report_req") and report_info(m["id"], m)["pending"]:
        return "звіт"
    try:
        ans = help_answers(m["id"])
    except KeyError:
        ans = {}
    if any(h.get("id") not in ans for h in m.get("help") or []):
        return "«Допоможи»"
    return None


def start_deferred_plans(items: list[dict]) -> int:
    """2.6: відкладені автоінструкції — у чергу, щойно заняття звільнилось (викликається з write_queue, без рекурсії)."""
    n = 0
    for m in items:
        if m.get("plan_wanted") and not busy_reason(m):
            def fn(x):
                x.pop("plan_wanted", None)
                x["plan_req"] = {"requested_at": storage.now_iso(), "auto": True}
            lectures.mutate(m["id"], fn)
            n += 1
    return n


def busy_error(m: dict) -> None:
    r = busy_reason(m)
    if r:
        raise ValueError(f"Claude ще працює над цим заняттям ({r}). Дочекайся відповіді — тоді наступний запит "
                         "врахує її, і нічого не накладеться.")


def set_check(lid: str, cid: str, done: bool) -> dict:
    def fn(m):
        s = set(m.get("checklist_done") or [])
        (s.add if done else s.discard)(cid)
        m["checklist_done"] = sorted(s)
    lectures.mutate(lid, fn)
    return lectures.enrich(lectures.read_meta(lid), full=True)


def set_submitted(lid: str, done: bool) -> dict:
    """2.2: «Здано» — закриває всі пункти чекліста й дедлайни цього заняття; «Скасувати» повертає, як було."""
    from . import applog, eportal
    m0 = lectures.enrich(lectures.read_meta(lid), full=True)
    ids = {i["id"] for i in checklist(m0)}

    def fn(m):
        if done:
            m["checklist_done_before"] = list(m.get("checklist_done") or [])
            m["checklist_done"] = sorted(set(m.get("checklist_done") or []) | ids)
            m["submitted_at"] = storage.now_iso()
        else:
            m["checklist_done"] = sorted(m.pop("checklist_done_before", None) or [])
            m.pop("submitted_at", None)
    lectures.mutate(lid, fn)
    for d in eportal.list_deadlines():
        if d["id"].startswith((f"lec:{lid}:", f"lecp:{lid}:")):
            eportal.set_deadline(d["id"], done=done)
    applog.event("submitted", lecture=lid, done=done, items=len(ids))
    return lectures.enrich(lectures.read_meta(lid), full=True)


def open_soon(days: int = 7) -> int:
    """Лічильник «Здати» в меню: лише незакриті пункти з терміном від тижня тому до тижня наперед."""
    now = datetime.now()
    lo, hi = (now.replace(microsecond=0) - _td(days)).isoformat()[:16], (now + _td(days)).isoformat()[:16]
    return sum(1 for g in all_checklists() for i in g["items"] if not i["done"] and i["due"] and lo <= i["due"] <= hi)


def _td(days: int):
    from datetime import timedelta
    return timedelta(days=days)


def all_checklists(include_done: bool = False) -> list[dict]:
    """Пункти здачі з усіх лаб/проєктів — для вкладки «Здати» (за замовчуванням лише незакриті списки)."""
    out = []
    for m in lectures.list_all():
        items = checklist(m)
        if not items or (not include_done and all(i["done"] for i in items)):
            continue
        sj = m.get("subject") or {}
        out.append({"lecture_id": m["id"], "title": m.get("display_title") or sj.get("name", ""), "type": m.get("type"),
                    "subject_id": m.get("subject_id"), "date": m.get("date"), "items": items,
                    "next_due": min((i["due"] for i in items if i["due"] and not i["done"]), default="")})
    out.sort(key=lambda x: (x["next_due"] or "9999", x["date"] or ""))
    return out


# ---------------------------------------------------------------- 2.1: «Кинув завдання → план»
# meta.json → plan_req: {requested_at, auto}  — запит плану (пише застосунок; авто — коли додано умову в «Завдання»)
# output/plan.md, plan.pdf                     — план виконання (пише Claude)
# output/plan.json                             — {"completed_at", "todos":[...], "checklist":[...]} (пише Claude ОСТАННІМ)
PLAN_TYPES = ("L", "P", "C", "S")


def _plan_json(lid: str) -> dict:
    p = lectures.lecture_dir(lid) / "output" / "plan.json"
    d = storage.read_json(p, {}) if p.exists() else {}
    return d if isinstance(d, dict) else {}


def plan_info(lid: str, meta: dict | None = None) -> dict:
    meta = meta or lectures.read_meta(lid)
    out = lectures.lecture_dir(lid) / "output"
    req = meta.get("plan_req") or {}
    pj = _plan_json(lid)
    done_at = lectures._ts(pj.get("completed_at"))
    req_at = lectures._ts(req.get("requested_at"))
    md = out / "plan.md"
    return {"requested_at": req.get("requested_at"), "auto": bool(req.get("auto")), "deferred": bool(meta.get("plan_wanted")),
            "completed_at": pj.get("completed_at"), "has_plan": md.exists(),
            "pending": bool(req_at) and done_at < req_at,
            "pdf": "plan.pdf" if (out / "plan.pdf").exists() else None,
            "md": _read(md)}


def request_plan(lid: str, auto: bool = False, note: str = "") -> dict:
    meta = lectures.read_meta(lid)
    if (meta.get("type") or "W") not in PLAN_TYPES:
        raise ValueError("План робиться для лаб, проєктів і вправ")
    busy_error(meta)
    req = {"requested_at": storage.now_iso(), "auto": auto}
    if note:
        req["note"] = str(note)[:3000]
    lectures.mutate(lid, lambda m: m.__setitem__("plan_req", req))
    lectures.write_queue()
    return plan_info(lid)


def cancel_plan(lid: str) -> dict:
    lectures.mutate(lid, lambda m: m.pop("plan_req", None))
    lectures.write_queue()
    return plan_info(lid)


def on_task_added(lid: str) -> bool:
    """Нова умова в «Завдання» (вручну або з ePortalu) → план у черзі Claude автоматично."""
    meta = lectures.read_meta(lid)
    if (meta.get("type") or "W") not in PLAN_TYPES:
        return False
    from .schedule import load_settings
    if not load_settings().get("auto_plan"):  # 2.7: за замовчуванням інструкцію складає чат («Робота в чаті»)
        return False
    from . import project
    if project.is_project_meeting(meta):  # 2.4: у проєкті план — це кроки, а не автоплан на кожен новий файл
        return False
    if busy_reason(meta):  # 2.6: не поверх незавершеного запиту — відкладаємо, запуститься сам, коли Claude відповість
        lectures.mutate(lid, lambda m: m.__setitem__("plan_wanted", storage.now_iso()))
        return False
    request_plan(lid, auto=True)
    return True


def pending_plans(items: list[dict] | None = None) -> list[dict]:
    out = []
    items = items if items is not None else lectures.list_all()
    for m in items:
        if not m.get("plan_req"):
            continue
        info = plan_info(m["id"], m)
        if not info["pending"]:
            continue
        sj = m.get("subject") or {}
        out.append({"lecture_id": m["id"], "folder": f"lectures/{m['id']}", "subject": sj.get("name", ""),
                    "subject_id": m.get("subject_id"), "type": m.get("type"), "date": m.get("date"), "time": m.get("time"),
                    "notes_language": m.get("notes_language"), "requested_at": info["requested_at"],
                    "note": (m.get("plan_req") or {}).get("note", ""),
                    "task_files": [f"task/{f['name']}" for f in m["files"] if f["kind"] == "task"],
                    "code_files": [f"code/{f['name']}" for f in m["files"] if f["kind"] == "code"],
                    "has_notes": (lectures.lecture_dir(m["id"]) / "output" / "notes.md").exists(),
                    "instruction_exists": info["has_plan"], "progress": progress(m),
                    "deadlines": lectures._subject_deadlines(m.get("subject_id")),
                    "context": lectures._context(m, items),
                    "output": {"md": f"lectures/{m['id']}/output/plan.md", "pdf": f"lectures/{m['id']}/output/plan.pdf",
                               "json": f"lectures/{m['id']}/output/plan.json"}})
    return out


# ---------------------------------------------------------------- 2.3 (E3): чернетка звіту й перевірка перед здачею
# meta.json → report_req: {kind: draft|check, requested_at, note}   (пише застосунок)
# output/zdacha/report.json → {completed_at, kind, summary, missing: [...]}  (пише Claude ОСТАННІМ)
REPORT_KINDS = {"draft": "Чернетка звіту", "check": "Перевірка перед здачею"}


def report_info(lid: str, meta: dict | None = None) -> dict:
    meta = meta or lectures.read_meta(lid)
    req = meta.get("report_req") or {}
    p = lectures.lecture_dir(lid) / "output" / "zdacha" / "report.json"
    res = storage.read_json(p, {}) if p.exists() else {}
    res = res if isinstance(res, dict) else {}
    pending = bool(req) and lectures._ts(res.get("completed_at")) < lectures._ts(req.get("requested_at"))
    return {"req": req or None, "pending": pending, "result": res or None}


def request_report(lid: str, kind: str, note: str = "") -> dict:
    if kind not in REPORT_KINDS:
        raise ValueError("Невідомий запит")
    from . import project
    busy_error(lectures.read_meta(lid))
    if project.is_project_meeting(lectures.read_meta(lid)):
        raise ValueError("Це зустріч проєкту: питання й прохання — у «Предмет → Проєкт → Наступний крок», щоб не було паралельних версій")
    lectures.mutate(lid, lambda m: m.__setitem__("report_req", {"kind": kind, "requested_at": storage.now_iso(),
                                                                 "note": (note or "").strip()[:2000]}))
    return lectures.enrich(lectures.read_meta(lid), full=True)


def cancel_report(lid: str) -> dict:
    lectures.mutate(lid, lambda m: m.pop("report_req", None))
    return lectures.enrich(lectures.read_meta(lid), full=True)


def pending_reports(items: list[dict] | None = None) -> list[dict]:
    out = []
    for m in items if items is not None else lectures.list_all():
        if not m.get("report_req"):
            continue
        info = report_info(m["id"], m)
        if not info["pending"]:
            continue
        d = lectures.lecture_dir(m["id"])
        files = lambda k: [f"lectures/{m['id']}/{k}/{f['name']}" for f in m.get("files", []) if f.get("kind") == k]
        out.append({"lecture_id": m["id"], "kind": info["req"]["kind"], "note": info["req"].get("note", ""),
                    "requested_at": info["req"]["requested_at"], "type": m.get("type"), "subject_id": m.get("subject_id"),
                    "notes_language": m.get("notes_language"),
                    "task_files": files("task"), "code_files": files("code"),
                    "deliverables": [f"lectures/{m['id']}/output/{x['name']}" for x in (m.get("output") or {}).get("deliverables", [])],
                    "checklist": [i["text"] for i in checklist(m)], "progress": progress(m),
                    "memory": f"subjects/{m.get('subject_id')}/memory.md",
                    "notes": f"lectures/{m['id']}/output/notes.md" if (d / "output" / "notes.md").exists() else "",
                    "output": {"dir": f"lectures/{m['id']}/output/zdacha", "json": f"lectures/{m['id']}/output/zdacha/report.json"}})
    return out
