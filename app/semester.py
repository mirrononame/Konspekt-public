"""2.3: семестр — «Шлях до заліку» (E1), план тижня у вікнах планера (E2), календар для телефона (E4),
«Готуюсь до тесту» (E6).

data/subjects/<id>/zaliczenie.json  — умови заліку (пише Claude): формула, складники з вагами й порогами, етапи з датами
data/grades.json                    — оцінки, які вписав студент (пише застосунок)
data/subjects/<id>/exam_prep.json   — запит «Готуюсь до тесту»: {date, title, requested_at} (пише застосунок)
data/subjects/<id>/szpargalka.md/.pdf, szpargalka.json — шпаргалка й позначка {completed_at} (пише Claude)
"""
from __future__ import annotations

import re
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

from . import storage

GRADES = storage.DATA_DIR / "grades.json"


def _subj_dir(sid: str):
    return storage.DATA_DIR / "subjects" / sid


def _subjects() -> list[dict]:
    from .schedule import load_schedule
    return load_schedule()["subjects"]


def _ts(v) -> float:
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return (dt if dt.tzinfo else dt.astimezone()).timestamp()
    except Exception:
        return 0.0


# ---------------------------------------------------------------- E1: «Шлях до заліку»
def setup(sid: str) -> dict | None:
    p = _subj_dir(sid) / "zaliczenie.json"
    d = storage.read_json(p, None) if p.exists() else None
    return d if isinstance(d, dict) and isinstance(d.get("components"), list) else None


def _grades() -> dict:
    d = storage.read_json(GRADES, {}) or {}
    return d if isinstance(d, dict) else {}


def add_grade(sid: str, component: str, value, title: str = "") -> dict:
    try:
        v = float(str(value).replace(",", "."))
    except ValueError:
        raise ValueError("Оцінка — число, напр. 4 або 4,5")
    if not 0 <= v <= 100:
        raise ValueError("Оцінка поза межами")
    with storage._lock:
        g = _grades()
        g.setdefault(sid, []).append({"id": uuid.uuid4().hex[:8], "component": str(component)[:20], "value": v,
                                      "title": str(title or "").strip()[:120], "added_at": storage.now_iso()})
        storage.write_json(GRADES, g)
    from . import applog
    applog.event("grade_added", subject=sid, component=str(component)[:20])
    return subject_status(sid)


def delete_grade(sid: str, gid: str) -> dict:
    with storage._lock:
        g = _grades()
        g[sid] = [x for x in g.get(sid, []) if x.get("id") != gid]
        storage.write_json(GRADES, g)
    return subject_status(sid)


def _fmt(v: float | None) -> str:
    return "" if v is None else (f"{v:.2f}".rstrip("0").rstrip(".")).replace(".", ",")


def subject_status(sid: str, subj: dict | None = None) -> dict:
    subj = subj or next((s for s in _subjects() if s["id"] == sid), {"id": sid, "name": sid, "short": sid, "color": "#94a3b8"})
    st = setup(sid)
    grades = _grades().get(sid, [])
    today = date.today().isoformat()
    out = {"subject_id": sid, "name": subj.get("name"), "short": subj.get("short"), "color": subj.get("color"),
           "setup": st, "grades": grades, "components": [], "current": None, "risks": [], "next": [], "overdue": [],
           "prep": exam_prep_info(sid)}
    if not st:
        out["status"] = "nosetup"
        return out
    comps, wsum, acc = [], 0.0, 0.0
    for c in st["components"]:
        cid = str(c.get("id") or "")
        vals = [g["value"] for g in grades if g.get("component") == cid]
        avg = round(sum(vals) / len(vals), 2) if vals else None
        w = float(c.get("weight") or 0)
        mn = c.get("min")
        comp = {"id": cid, "name": c.get("name") or cid, "weight": w, "min": mn, "avg": avg, "n": len(vals), "note": c.get("note", "")}
        comps.append(comp)
        if avg is not None and w:
            wsum += w
            acc += w * avg
        if avg is not None and mn is not None and avg < float(mn):
            out["risks"].append(f"{comp['name']}: зараз {_fmt(avg)}, а треба щонайменше {_fmt(float(mn))}")
    out["components"] = comps
    out["current"] = round(acc / wsum, 2) if wsum else None
    out["complete"] = all(c["avg"] is not None for c in comps if c["weight"])
    ms = [m for m in st.get("milestones") or [] if isinstance(m, dict) and re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", str(m.get("date") or ""))]
    ms.sort(key=lambda m: m["date"])
    out["next"] = [m for m in ms if m["date"][:10] >= today][:4]
    out["overdue"] = [m for m in ms if m["date"][:10] < today and not m.get("done")][-3:]
    out["status"] = "risk" if out["risks"] else "ok" if grades else "nodata"
    return out


def semester() -> list[dict]:
    return [subject_status(s["id"], s) for s in _subjects()]


def pending_setups() -> list[dict]:
    """Черга для Claude: предмети з пам'яттю, але без zaliczenie.json — скласти умови заліку."""
    out = []
    for s in _subjects():
        d = _subj_dir(s["id"])
        if (d / "memory.md").exists() and not (d / "zaliczenie.json").exists():
            out.append({"subject_id": s["id"], "subject": s["name"], "memory": f"subjects/{s['id']}/memory.md",
                        "output": f"subjects/{s['id']}/zaliczenie.json"})
    return out


# ---------------------------------------------------------------- E6: «Готуюсь до тесту»
def exam_prep_info(sid: str) -> dict | None:
    d = _subj_dir(sid)
    req = storage.read_json(d / "exam_prep.json", None) if (d / "exam_prep.json").exists() else None
    if not isinstance(req, dict):
        return None
    done = storage.read_json(d / "szpargalka.json", {}) if (d / "szpargalka.json").exists() else {}
    ready = bool(done) and _ts(done.get("completed_at")) >= _ts(req.get("requested_at")) and (d / "szpargalka.pdf").exists()
    try:
        days_left = (date.fromisoformat(req["date"][:10]) - date.today()).days
    except (KeyError, ValueError):
        days_left = None
    return {**req, "pending": not ready, "ready": ready, "pdf": ready, "days_left": days_left}


def request_exam_prep(sid: str, day: str, title: str) -> dict:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day or ""):
        raise ValueError("Вкажіть дату тесту")
    storage.write_json(_subj_dir(sid) / "exam_prep.json", {"date": day, "title": (title or "Test").strip()[:120],
                                                           "requested_at": storage.now_iso()})
    return subject_status(sid)


def cancel_exam_prep(sid: str) -> dict:
    p = _subj_dir(sid) / "exam_prep.json"
    if p.exists():
        p.unlink()
    return subject_status(sid)


def pending_exam_preps() -> list[dict]:
    out = []
    for s in _subjects():
        info = exam_prep_info(s["id"])
        if info and info["pending"] and (info["days_left"] is None or info["days_left"] >= 0):
            out.append({"subject_id": s["id"], "subject": s["name"], "date": info["date"], "title": info["title"],
                        "requested_at": info["requested_at"], "memory": f"subjects/{s['id']}/memory.md",
                        "output": {"md": f"subjects/{s['id']}/szpargalka.md", "pdf": f"subjects/{s['id']}/szpargalka.pdf",
                                   "json": f"subjects/{s['id']}/szpargalka.json"}})
    return out


def exam_deadlines() -> list[dict]:
    """Тести з «Готуюсь до тесту» — теж дедлайни (і темп карток у «Навчанні» рахується до них)."""
    out = []
    for s in _subjects():
        info = exam_prep_info(s["id"])
        if info and info.get("days_left") is not None and info["days_left"] >= 0:
            out.append({"id": f"exam:{s['id']}", "title": f"Test: {info['title']}", "due": info["date"][:10] + "T09:00",
                        "subject_id": s["id"], "what": "Готуюсь до тесту", "url": f"#/subject/{s['id']}", "source": "exam_prep"})
    return out


# ---------------------------------------------------------------- E2: план тижня у вікнах планера
def _m(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _f(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def week_tasks(days: list[dict]) -> list[dict]:
    """Що робити: дедлайни (до 14 днів), підготовка до лаб/проєкту (до 7 днів), тест (E6), картки — з оцінкою часу."""
    from . import eportal
    today = date.today()
    tasks = []
    for d in eportal.list_deadlines():
        if d.get("done") or not d.get("due") or d.get("source") == "exam_prep":
            continue
        try:
            due = datetime.fromisoformat(d["due"][:16])
        except ValueError:
            continue
        if not today <= due.date() <= today + timedelta(days=14):
            continue
        est = int(d.get("est_min") or (120 if d.get("source") != "lecture" else 90))
        tasks.append({"id": d["id"], "title": d["title"], "subject_id": d.get("subject_id", ""), "kind": "deadline",
                      "minutes": est, "due": due, "href": d.get("url") or "#/", "done_api": f"/api/deadlines/{d['id']}"})
    for day in days:
        try:
            dd = date.fromisoformat(day["date"])
        except ValueError:
            continue
        if not today <= dd <= today + timedelta(days=7):
            continue
        for c in day.get("classes", []):
            if c.get("type") in ("L", "P", "C"):
                tasks.append({"id": f"prep:{day['date']}:{c['subject']}:{c['start']}", "kind": "prep", "minutes": 45,
                              "title": f"Підготуватися: {c['subject']} {c['type']} ({c['start']})", "subject_id": "",
                              "due": datetime.combine(dd, datetime.min.time()) + timedelta(minutes=_m(c["start"])),
                              "href": "#/todo"})
    for s in _subjects():
        info = exam_prep_info(s["id"])
        if info and info.get("days_left") is not None and 0 <= info["days_left"] <= 21:
            for i in range(min(info["days_left"], 14)):
                dd = today + timedelta(days=i)
                tasks.append({"id": f"exam:{s['id']}:{dd}", "kind": "exam", "minutes": 30, "subject_id": s["id"],
                              "title": f"Тест {s['short']}: повторити шпаргалку", "due": datetime.combine(dd, datetime.max.time()),
                              "href": f"#/subject/{s['id']}", "day_only": dd.isoformat()})
    tasks.sort(key=lambda t: (t["due"], t["kind"] != "deadline"))
    return tasks


def place_tasks(days: list[dict]) -> dict:
    """Жадібно кладе завдання у вільні вікна від сьогодні до терміну; велике ділиться на частини.
    Короткі (≤ 30 хв) можна й у перерву на кампусі. Повертає {placed, unplaced}."""
    tasks = week_tasks(days)
    now = datetime.now()
    free = []  # [day, window, from_min, to_min]
    for day in days:
        if day["date"] < now.date().isoformat():
            continue
        for w in day.get("windows", []):
            w.setdefault("tasks", [])
            a, b = _m(w["from"]), _m(w["to"])
            if day["date"] == now.date().isoformat():
                a = max(a, -(-(now.hour * 60 + now.minute) // 5) * 5)  # з найближчих «круглих» 5 хв
            if b - a >= 10:
                free.append([day, w, a, b])
    unplaced, placed = [], 0
    for t in tasks:
        left = t["minutes"]
        for slot in free:
            day, w, a, b = slot
            if day["date"] > t["due"].date().isoformat() or (t.get("day_only") and day["date"] != t["day_only"]):
                continue
            if not w.get("work") and t["minutes"] > 30:
                continue
            if day["date"] == t["due"].date().isoformat() and t["due"].time() != datetime.max.time():
                b = min(b, t["due"].hour * 60 + t["due"].minute - 15)
            take = min(left, b - a)
            if take < min(left, 25):
                continue
            w["tasks"].append({k: v for k, v in t.items() if k not in ("due", "day_only")} |
                              {"from": _f(a), "to": _f(a + take), "minutes": take, "part": take < t["minutes"]})
            slot[2] = a + take
            left -= take
            placed += 1
            if left <= 0:
                break
        if left > 0:
            unplaced.append({k: v for k, v in t.items() if k not in ("day_only",)} | {"due": t["due"].isoformat(timespec="minutes"), "left": left})
    return {"placed": placed, "unplaced": unplaced}


# ---------------------------------------------------------------- E4: календар для телефона (ICS)
def calendar_key() -> str:
    from .schedule import load_settings, save_settings
    k = load_settings().get("calendar_key")
    if not k:
        k = secrets.token_urlsafe(18)
        save_settings({"calendar_key": k})
    return k


def _esc(s: str) -> str:
    return str(s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _dt(d: date, hm: str) -> str:
    return f"{d.strftime('%Y%m%d')}T{hm.replace(':', '')}00"


def ics() -> str:
    """Пари з USOS (або з шаблону розкладу), дедлайни з нагадуваннями за добу й за 2 год, етапи заліку."""
    from . import eportal, usos, schedule
    today = date.today()
    subs = {s["id"]: s for s in _subjects()}
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Konspekt//PL", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "X-WR-CALNAME:Konspekt", "X-WR-TIMEZONE:Europe/Warsaw", "REFRESH-INTERVAL;VALUE=DURATION:PT2H",
             "X-PUBLISHED-TTL:PT2H",
             "BEGIN:VTIMEZONE", "TZID:Europe/Warsaw",
             "BEGIN:DAYLIGHT", "TZOFFSETFROM:+0100", "TZOFFSETTO:+0200", "TZNAME:CEST", "DTSTART:19700329T020000",
             "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", "END:DAYLIGHT",
             "BEGIN:STANDARD", "TZOFFSETFROM:+0200", "TZOFFSETTO:+0100", "TZNAME:CET", "DTSTART:19701025T030000",
             "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU", "END:STANDARD", "END:VTIMEZONE"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def ev(uid, start, end, summary, desc="", loc="", alarms=(), allday=False):
        lines.append("BEGIN:VEVENT")
        lines.extend([f"UID:{uid}@konspekt", f"DTSTAMP:{stamp}"])
        if allday:
            lines.extend([f"DTSTART;VALUE=DATE:{start}", f"DTEND;VALUE=DATE:{end}"])
        else:
            lines.extend([f"DTSTART;TZID=Europe/Warsaw:{start}", f"DTEND;TZID=Europe/Warsaw:{end}"])
        lines.append(f"SUMMARY:{_esc(summary)}")
        if desc:
            lines.append(f"DESCRIPTION:{_esc(desc)}")
        if loc:
            lines.append(f"LOCATION:{_esc(loc)}")
        for a in alarms:
            lines.extend(["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_esc(summary)}", f"TRIGGER:-{a}", "END:VALARM"])
        lines.append("END:VEVENT")

    evs = usos.load().get("events") or []
    sets = schedule.load_settings()
    sched = schedule.load_schedule()
    for i in range(-7, 150):
        d = today + timedelta(days=i)
        day_evs = [e for e in evs if e.get("date") == d.isoformat()]
        if day_evs:
            for e in day_evs:
                s = subs.get(e.get("subject_id") or "", {})
                ev(f"usos-{d}-{e.get('start')}-{e.get('subject_id')}-{e.get('type')}", _dt(d, e["start"]), _dt(d, e["end"]),
                   f"{s.get('short') or e.get('name', '')} {e.get('type', '')}", ", ".join(e.get("lecturers") or []), e.get("room", ""))
        elif not evs:
            for c in schedule.classes_on(d, sched, sets):
                ev(f"tpl-{d}-{c['start']}-{c['subject_id']}", _dt(d, c["start"]), _dt(d, c["end"]),
                   f"{c['subject']['short']} {c['type']}", "", c.get("room", ""))
    for x in eportal.list_deadlines():
        if x.get("done") or not x.get("due"):
            continue
        try:
            due = datetime.fromisoformat(x["due"][:16])
        except ValueError:
            continue
        if due.date() < today - timedelta(days=1):
            continue
        s = subs.get(x.get("subject_id") or "", {})
        st = due - timedelta(minutes=30)
        ev(f"dl-{re.sub(r'[^A-Za-z0-9_-]', '_', x['id'])}", st.strftime("%Y%m%dT%H%M00"), due.strftime("%Y%m%dT%H%M00"),
           f"⏰ {s.get('short', '')} {x['title']}".strip(), x.get("what", ""), "", alarms=("P1D", "PT2H"))
    for s in _subjects():
        st = setup(s["id"]) or {}
        for m in st.get("milestones") or []:
            try:
                d = date.fromisoformat(str(m.get("date"))[:10])
            except ValueError:
                continue
            if d < today:
                continue
            ev(f"ms-{s['id']}-{d}-{abs(hash(m.get('title', ''))) % 10**8}", d.strftime("%Y%m%d"),
               (d + timedelta(days=1)).strftime("%Y%m%d"), f"🎓 {s['short']}: {m.get('title', '')}", "", "", allday=True)
    lines.append("END:VCALENDAR")
    out = []
    for ln in lines:  # RFC 5545: рядки ≤ 75 байт
        b = ln.encode("utf-8")
        while len(b) > 75:
            cut = 75
            while (b[cut] & 0xC0) == 0x80:
                cut -= 1
            out.append(b[:cut].decode("utf-8"))
            b = b" " + b[cut:]
        out.append(b.decode("utf-8"))
    return "\r\n".join(out) + "\r\n"
