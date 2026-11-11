"""Розклад, парність тижнів та автоматичне визначення предмета."""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta

from . import storage

DAYS_UA = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
TYPES = {"W": "Лекція (wykład)", "L": "Лабораторні", "P": "Проєкт", "C": "Практичні (ćwiczenia)", "S": "Семінар"}

PALETTE = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#a855f7", "#ec4899", "#14b8a6", "#84cc16", "#f97316"]


def _sub(sid, name, short, color):
    return {"id": sid, "name": name, "short": short, "color": color}


def _cls(subject, day, start, end, typ, room, parity="all"):
    return {"id": uuid.uuid4().hex[:8], "subject_id": subject, "day": day, "start": start, "end": end,
            "type": typ, "room": room, "parity": parity}


def default_schedule() -> dict:
    """Порожній розклад для нового користувача: предмети з'являться з USOS або їх додають вручну."""
    return {"subjects": [], "classes": [], "version": 1}


def default_settings() -> dict:
    return {
        "semester_start": "2026-10-01",
        "parity_mode": "semester",      # semester | iso
        "parity_invert": False,
        "default_notes_language": "pl",  # pl | uk | ru
        "default_audio_language": "pl",
        "auto_transcribe": True,
        "auto_request_claude": True,
        "auto_plan": False,              # 2.7: інструкцію до лаби робимо в чаті; автоматичний запит у чергу — за бажанням
        "whisper_model": "large-v3-turbo",
        "whisper_device": "auto",        # auto | cuda | cpu
        "audio_enhance": True,           # шумозаглушення + вирівнювання гучності перед розшифровкою
        "video_keep": False,             # зберігати відео після того, як з нього витягли аудіо й кадри
        "compact_audio": True,           # розшифроване аудіо → AAC 48 кбіт/с моно (у 3–6 разів менше)
        "compact_images": True,          # великі фото → 2200 px, JPEG 85 %
        "trash_days": 14,                # скільки днів зберігати кошик
        "study_new_per_day": 15,         # 2.0: нових карток на день (FSRS)
        "theme": "auto",
        "version": 1,
        # планер (вкладка «Планер»)
        "planner_address": "", "planner_lat": None, "planner_lon": None, "planner_place": "",
        "planner_mode": "transit", "planner_travel_override": 0,
        "planner_morning_min": 60, "planner_buffer_min": 10, "planner_sleep_h": 8,
        "planner_work_from": "08:00", "planner_work_to": "21:00", "planner_min_block": 120,
        "planner_campus_gaps": False, "planner_weekends": True,
        # 2.3: календар для телефона (секрет у посиланні-підписці) і сповіщення
        "calendar_key": "",
        "push_kinds": {"done": True, "answers": True, "lab": True, "deadline": True, "cards": True},
    }


def load_schedule() -> dict:
    data = storage.read_json(storage.DATA_DIR / "schedule.json")
    if not isinstance(data, dict) or "subjects" not in data:
        data = default_schedule()
        storage.write_json(storage.DATA_DIR / "schedule.json", data)
    data.setdefault("classes", [])
    return data


def save_schedule(data: dict) -> dict:
    clean_subjects, seen = [], set()
    for i, s in enumerate(data.get("subjects", [])):
        sid = str(s.get("id") or "").strip() or uuid.uuid4().hex[:6]
        sid = re.sub(r"[^a-zA-Z0-9_-]", "", sid)[:24] or uuid.uuid4().hex[:6]
        if sid in seen:
            sid = sid + uuid.uuid4().hex[:3]
        seen.add(sid)
        name = str(s.get("name") or "").strip()
        if not name:
            continue
        clean_subjects.append({
            "id": sid, "name": name[:200],
            "short": (str(s.get("short") or "").strip() or name[:6])[:12],
            "color": s.get("color") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(s.get("color", ""))) else PALETTE[i % len(PALETTE)],
            **({"usos_code": str(s["usos_code"])[:40]} if s.get("usos_code") else {}),
            **({"eportal_course": int(s["eportal_course"])} if str(s.get("eportal_course") or "").isdigit() else {}),
        })
    ids = {s["id"] for s in clean_subjects}
    clean_classes = []
    for c in data.get("classes", []):
        if c.get("subject_id") not in ids:
            continue
        try:
            day = int(c.get("day"))
            assert 0 <= day <= 6
            start, end = _norm_time(c.get("start")), _norm_time(c.get("end"))
        except Exception:
            continue
        if _mins(end) <= _mins(start):
            end = _fmt(_mins(start) + 90)
        clean_classes.append({
            "id": str(c.get("id") or uuid.uuid4().hex[:8])[:16],
            "subject_id": c["subject_id"], "day": day, "start": start, "end": end,
            "type": c.get("type") if c.get("type") in TYPES else "W",
            "room": str(c.get("room") or "")[:80],
            "parity": c.get("parity") if c.get("parity") in ("all", "even", "odd") else "all",
        })
    out = {"subjects": clean_subjects, "classes": clean_classes, "version": 1}
    storage.write_json(storage.DATA_DIR / "schedule.json", out)
    return out


def load_settings() -> dict:
    data = storage.read_json(storage.DATA_DIR / "settings.json")
    base = default_settings()
    if isinstance(data, dict):
        base.update({k: v for k, v in data.items() if k in base})
    else:
        storage.write_json(storage.DATA_DIR / "settings.json", base)
    return base


def save_settings(patch: dict) -> dict:
    s = load_settings()
    for k, v in patch.items():
        if k in s:
            s[k] = v
    if s["parity_mode"] not in ("semester", "iso"):
        s["parity_mode"] = "semester"
    for k in ("default_notes_language", "default_audio_language"):
        if s[k] not in ("pl", "uk", "ru", "en"):
            s[k] = "pl"
    try:
        s["study_new_per_day"] = max(0, min(200, int(s.get("study_new_per_day", 15))))
    except (TypeError, ValueError):
        s["study_new_per_day"] = 15
    try:
        s["trash_days"] = max(1, min(365, int(s.get("trash_days") or 14)))
    except (TypeError, ValueError):
        s["trash_days"] = 14
    try:
        date.fromisoformat(s["semester_start"])
    except Exception:
        s["semester_start"] = default_settings()["semester_start"]
    storage.write_json(storage.DATA_DIR / "settings.json", s)
    return s


# ---------------------------------------------------------------- time helpers
def _norm_time(v) -> str:
    m = re.fullmatch(r"\s*(\d{1,2})[:.](\d{2})\s*", str(v or ""))
    if not m:
        raise ValueError("bad time")
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise ValueError("bad time")
    return f"{h:02d}:{mi:02d}"


def _mins(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _fmt(m: int) -> str:
    m = max(0, min(m, 23 * 60 + 59))
    return f"{m // 60:02d}:{m % 60:02d}"


# ---------------------------------------------------------------- parity
def week_info(d: date, settings: dict | None = None) -> dict:
    settings = settings or load_settings()
    if settings.get("parity_mode") == "iso":
        num = d.isocalendar()[1]
    else:
        try:
            start = date.fromisoformat(settings.get("semester_start"))
        except Exception:
            start = d
        start_monday = start - timedelta(days=start.weekday())
        d_monday = d - timedelta(days=d.weekday())
        num = (d_monday - start_monday).days // 7 + 1
    even = num % 2 == 0
    if settings.get("parity_invert"):
        even = not even
    return {"week": num, "even": even, "label": "парний" if even else "непарний"}


def classes_on(d: date, schedule: dict | None = None, settings: dict | None = None) -> list[dict]:
    schedule = schedule or load_schedule()
    subj = {s["id"]: s for s in schedule["subjects"]}
    # точні дати з USOS мають пріоритет над тижневим шаблоном (перенесення, свята, парність)
    try:
        from . import usos
        evs = usos.events_on(d)
    except Exception:
        evs = None
    if evs is not None:
        out = []
        for i, e in enumerate(evs):
            s = subj.get(e.get("subject_id"))
            if s:
                out.append({"id": f"usos-{e['date']}-{i}", "subject_id": s["id"], "day": d.weekday(),
                            "start": e["start"], "end": e["end"], "type": e["type"], "room": e["room"],
                            "parity": "all", "group": e.get("group", ""), "lecturers": e.get("lecturers", []),
                            "source": "usos", "subject": s})
        out.sort(key=lambda c: c["start"])
        return out
    wi = week_info(d, settings)
    out = []
    for c in schedule["classes"]:
        if c["day"] != d.weekday():
            continue
        if c["parity"] == "even" and not wi["even"]:
            continue
        if c["parity"] == "odd" and wi["even"]:
            continue
        s = subj.get(c["subject_id"])
        if s:
            out.append({**c, "subject": s})
    out.sort(key=lambda c: c["start"])
    return out


# ---------------------------------------------------------------- detection
_FN_PATTERNS = [
    # 2026-10-14_0915, 20261014_091512, 2026.10.14 09-15, 2026-10-14T09:15
    re.compile(r"(20\d{2})[-_. ]?(0[1-9]|1[0-2])[-_. ]?([0-2]\d|3[01])[ _T.-]{0,3}([01]\d|2[0-3])[-_.:hH]?([0-5]\d)"),
    # 14.10.2026 09.15 / 14-10-2026_0915
    re.compile(r"([0-2]\d|3[01])[-_.](0[1-9]|1[0-2])[-_.](20\d{2})[ _T.-]{0,3}([01]\d|2[0-3])[-_.:hH]?([0-5]\d)"),
]
_FN_DATE_ONLY = [
    re.compile(r"(20\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?([0-2]\d|3[01])"),
    re.compile(r"([0-2]\d|3[01])[-_.](0[1-9]|1[0-2])[-_.](20\d{2})"),
]


def datetime_from_filename(name: str) -> tuple[datetime | None, bool]:
    """Повертає (datetime, є_час)."""
    for i, rx in enumerate(_FN_PATTERNS):
        m = rx.search(name)
        if m:
            g = m.groups()
            try:
                if i == 0:
                    return datetime(int(g[0]), int(g[1]), int(g[2]), int(g[3]), int(g[4])), True
                return datetime(int(g[2]), int(g[1]), int(g[0]), int(g[3]), int(g[4])), True
            except ValueError:
                pass
    for i, rx in enumerate(_FN_DATE_ONLY):
        m = rx.search(name)
        if m:
            g = m.groups()
            try:
                if i == 0:
                    return datetime(int(g[0]), int(g[1]), int(g[2])), False
                return datetime(int(g[2]), int(g[1]), int(g[0])), False
            except ValueError:
                pass
    return None, False


def detect(start: datetime | None, end: datetime | None = None, prefer_type: str = "W",
           schedule: dict | None = None, settings: dict | None = None) -> list[dict]:
    """Підбирає заняття, що перетинаються з інтервалом запису.

    start/end — можливий інтервал запису (якщо відомий лише один момент,
    інший = None). Повертає кандидатів, відсортованих за впевненістю (0..1).
    """
    if not start and not end:
        return []
    schedule = schedule or load_schedule()
    settings = settings or load_settings()
    ref = start or end
    cands = []
    for c in classes_on(ref.date(), schedule, settings):
        cs, ce = _mins(c["start"]), _mins(c["end"])
        if start and end:
            a, b = start.hour * 60 + start.minute, end.hour * 60 + end.minute
            overlap = max(0, min(b, ce) - max(a, cs))
            span = max(1, min(b - a, ce - cs))
            score = overlap / span
            if overlap == 0:
                dist = min(abs(a - ce), abs(b - cs))
                score = max(0.0, 0.35 - dist / 120)
        else:
            t = ref.hour * 60 + ref.minute
            if cs - 25 <= t <= ce + 40:
                score = 0.9 if cs - 10 <= t <= ce + 15 else 0.65
            else:
                dist = min(abs(t - cs), abs(t - ce))
                score = max(0.0, 0.4 - dist / 150)
        if c["type"] == prefer_type:
            score += 0.08
        if score > 0.05:
            cands.append({
                "class_id": c["id"], "subject_id": c["subject_id"], "subject": c["subject"]["name"],
                "short": c["subject"]["short"], "color": c["subject"]["color"],
                "type": c["type"], "start": c["start"], "end": c["end"], "room": c["room"],
                "parity": c["parity"], "confidence": round(min(score, 1.0), 2),
            })
    cands.sort(key=lambda x: -x["confidence"])
    return cands


# ---------------------------------------------------------------- subject hints & checks
_TOKEN_RX = re.compile(r"[^0-9A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+")


def _norm(s: str) -> str:
    tr = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
    return (s or "").translate(tr).lower()


def subject_from_filenames(names: list[str], schedule: dict | None = None) -> dict | None:
    """Шукає предмет у назвах файлів: скорочення (TS-2-25.pdf) або повна назва."""
    schedule = schedule or load_schedule()
    best = None
    for n in names or []:
        stem = n.rsplit(".", 1)[0]
        tokens = {_norm(t) for t in _TOKEN_RX.split(stem) if t}
        flat = _norm(_TOKEN_RX.sub(" ", stem))
        for s in schedule["subjects"]:
            score = 0.0
            name = _norm(s["name"])
            short = _norm(s.get("short") or "")
            words = [w for w in _TOKEN_RX.split(name) if len(w) > 2]
            if name and name in flat:
                score = 0.97
            elif words and len(words) >= 2 and all(w in flat for w in words[:2]):
                score = 0.9
            elif short and short in tokens and len(short) >= 2:
                score = 0.88
            elif short and len(short) >= 3 and any(t.startswith(short) and t[len(short):].isdigit() for t in tokens):
                score = 0.8  # напр. "ts2", "bd2"
            if score and (not best or score > best["confidence"]):
                best = {"subject_id": s["id"], "subject": s["name"], "short": s.get("short"), "color": s.get("color"),
                        "confidence": score, "file": n}
    return best


def last_class(subject_id: str, ref: datetime, prefer_type: str = "W", days_back: int = 14,
               schedule: dict | None = None, settings: dict | None = None) -> dict | None:
    """Найближче заняття предмета, що вже почалося (не пізніше ref + 30 хв), шукаючи назад до 14 днів."""
    schedule = schedule or load_schedule()
    settings = settings or load_settings()
    limit = ref + timedelta(minutes=30)
    found = []
    for back in range(days_back + 1):
        d = (ref - timedelta(days=back)).date()
        for c in classes_on(d, schedule, settings):
            if c["subject_id"] != subject_id:
                continue
            start = datetime.combine(d, datetime.strptime(c["start"], "%H:%M").time())
            if start <= limit:
                found.append((back, 0 if c["type"] == prefer_type else 1, -_mins(c["start"]), d, c))
        if found:
            break
    if not found:
        return None
    found.sort(key=lambda x: (x[1], x[0], x[2]))
    _, _, _, d, c = found[0]
    return {"date": d.isoformat(), "start": c["start"], "end": c["end"], "type": c["type"], "room": c["room"],
            "class_id": c["id"], "subject_id": subject_id}


def schedule_check(subject_id: str, typ: str, date_s: str, time_s: str) -> dict:
    """Чи збігається лекція з розкладом. Повертає статус і пропозицію виправлення."""
    try:
        d = date.fromisoformat(date_s)
    except Exception:
        return {"status": "unknown"}
    if not subject_id:
        return {"status": "no_subject"}
    day = classes_on(d)
    mine = [c for c in day if c["subject_id"] == subject_id]
    t = _mins(time_s) if time_s and re.fullmatch(r"\d{1,2}:\d{2}", time_s) else None
    for c in mine:
        if t is None or abs(_mins(c["start"]) - t) <= 25 or _mins(c["start"]) <= t <= _mins(c["end"]):
            if c["type"] == typ or t is not None:
                return {"status": "ok", "class": {k: c[k] for k in ("start", "end", "type", "room")}}
    at_time = None
    if t is not None:
        for c in day:
            if _mins(c["start"]) - 15 <= t <= _mins(c["end"]):
                at_time = {"subject_id": c["subject_id"], "subject": c["subject"]["name"], "start": c["start"],
                           "end": c["end"], "type": c["type"]}
                break
    if mine:
        best = sorted(mine, key=lambda c: (c["type"] != typ, abs(_mins(c["start"]) - (t or 0))))[0]
        suggestion = {"date": d.isoformat(), "time": best["start"], "type": best["type"]}
    else:
        lc = last_class(subject_id, datetime.combine(d, datetime.max.time().replace(microsecond=0)), typ)
        suggestion = {"date": lc["date"], "time": lc["start"], "type": lc["type"]} if lc else None
    return {"status": "mismatch", "at_time": at_time, "suggestion": suggestion,
            "weekday": DAYS_UA[d.weekday()], "week": week_info(d)}
