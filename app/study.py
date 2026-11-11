"""Навчання 2.0: картки різних типів (quiz.json v2), FSRS, режими, прогрес, керування картками.

Картки бере з lectures/<id>/output/quiz.json (пише Claude):
  v1: {"cards": [{"q": "...", "a": "...", "kind": "qa" | "term"}]}               → тип flip
  v2: {"version": 2, "cards": [{"type": "mcq|cloze|tf|order|code|flip", "q": "...", ...,
        "hint": ["…", "…"], "explain": "…", "source": {"t": "00:12:34"} | {"section": "…"}, "tags": [], "important": true,
        "prev": "<текст старого питання, якщо картка його замінює — прогрес переноситься>"}]}
Прогрес — data/study.json (v2: стан FSRS, правки, власні картки, журнал днів).
«Поясни простіше» — запити в data/study_requests.json, відповіді Claude — data/explain_answers.json.
"""
from __future__ import annotations

import hashlib
import math
import random
import re
import secrets
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from . import fsrs, lectures, storage

STUDY_FILE = storage.DATA_DIR / "study.json"
REQ_FILE = storage.DATA_DIR / "study_requests.json"
ANS_FILE = storage.DATA_DIR / "explain_answers.json"
TYPES = ("mcq", "cloze", "tf", "order", "code", "flip")
AUTO_TYPES = ("mcq", "cloze", "tf", "order", "code")
NEW_PER_DAY = 15
LEARNED_S = 21  # стабільність ≥ 21 дня — «вивчено»
LEECH_LAPSES = 3
EXAM_RX = re.compile(r"kolok|egzam|exam|kartk|test|zaliczen|колок|екзам|залік|контрольн", re.I)


def _key(lid: str, q: str) -> str:
    return f"{lid}:{hashlib.sha1(q.strip().encode('utf-8')).hexdigest()[:10]}"


def _now() -> datetime:
    return datetime.now().astimezone()


def _today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------- сховище прогресу
def _migrate(data: dict) -> dict:
    """study.json v1 (Лейтнер) → v2 (FSRS). Стара версія зберігається як study.v1.json."""
    if data.get("version") == 2:
        return data
    try:
        if STUDY_FILE.exists() and not (storage.DATA_DIR / "study.v1.json").exists():
            shutil.copy2(STUDY_FILE, storage.DATA_DIR / "study.v1.json")
    except OSError:
        pass
    cards, log = {}, {}
    for k, p in (data.get("cards") or {}).items():
        if not isinstance(p, dict):
            continue
        if "s" in p and "state" in p:
            cards[k] = p
            continue
        cards[k] = fsrs.from_leitner(p)
        day = str(p.get("last") or "")[:10]
        if day:
            e = log.setdefault(day, {"n": 0, "new": 0, "again": 0, "ms": 0})
            e["n"] += max(1, int(p.get("seen", 1) or 1))
    out = {"version": 2, "cards": cards, "overrides": data.get("overrides", {}), "custom": data.get("custom", []),
           "log": {**log, **(data.get("log") or {})}, "tests": data.get("tests", []),
           "migrated_v1_at": storage.now_iso()}
    return out


def _progress() -> dict:
    data = storage.read_json(STUDY_FILE, {}) or {}
    if not isinstance(data, dict):
        data = {}
    if data.get("version") != 2:
        with storage._lock:
            data = _migrate(data)
            storage.write_json(STUDY_FILE, data)
    for k, v in (("cards", {}), ("overrides", {}), ("custom", []), ("log", {}), ("tests", [])):
        data.setdefault(k, v)
    return data


def _save(data: dict) -> None:
    storage.write_json(STUDY_FILE, data)


def _settings() -> dict:
    try:
        from .schedule import load_settings
        return load_settings()
    except Exception:
        return {}


def new_per_day() -> int:
    try:
        return max(0, min(200, int(_settings().get("study_new_per_day", NEW_PER_DAY))))
    except (TypeError, ValueError):
        return NEW_PER_DAY


# ---------------------------------------------------------------- нормалізація карток
_TS = re.compile(r"^\[?(\d{1,2}):(\d{2})(?::(\d{2}))?\]?$")


def _secs(t: str) -> int | None:
    m = _TS.match(str(t or "").strip())
    if not m:
        return None
    a, b, c = m.groups()
    return int(a) * 3600 + int(b) * 60 + int(c) if c is not None else int(a) * 60 + int(b)


def _source(src) -> dict | None:
    if not src:
        return None
    if isinstance(src, str):
        s = _secs(src)
        return {"t": src.strip("[]"), "sec": s} if s is not None else {"section": src[:200]}
    if isinstance(src, dict):
        out = {}
        if src.get("t"):
            out["t"] = str(src["t"]).strip("[]")[:12]
            out["sec"] = _secs(out["t"])
        if src.get("section"):
            out["section"] = str(src["section"])[:200]
        if src.get("lab"):
            out["lab"] = str(src["lab"])[:100]
        return out or None
    return None


def _str_list(v, n=20, ln=500) -> list[str]:
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        return []
    return [str(x)[:ln] for x in v if str(x).strip()][:n]


# 2.0.1: організаційні «картки» (коли іспит, наступне заняття, аудиторія…) не перевіряють знань — ховаємо їх.
_ORG_WHEN = re.compile(r"(?<!\w)(do\s+kiedy|kiedy|w\s+jakim\s+terminie|jaki\s+termin|до\s+якого|коли|до\s+какого|когда|when|by\s+when)(?!\w)", re.I)
_ORG_NOUN = re.compile(r"(egzamin|kolokwi|zaliczeni|sprawozdani|raport|oddani|odda[ćc]|termin\s+oddania|test\s+wiedzy|"
                       r"wykład|zajęci|laboratori|labie|labk|spotkani|"
                       r"іспит|екзамен|колоквіум|залік|звіт|здати|здач|лекці|занятт|(?<!\w)лаб|"
                       r"экзамен|коллоквиум|зач[её]т|отч[её]т|сдать|сдач|заняти|"
                       r"exam|deadline|due\s+date|next\s+lecture)", re.I)
_ORG_ALWAYS = re.compile(r"(następn\w*\s+(wykład|zaj[eę]ci|lab|spotkani|ćwiczeni)|co\s+będzie\s+(na|za)\s|za\s+(dwa|2)\s+tygodnie|"
                         r"(?<!\w)sal[ia]\s+\d|w\s+jakiej\s+sali|obecnoś|ile\s+(punktów|pkt)|"
                         r"ocen[aęy]\s+(końcow|z\s+przedmiotu)|wz[oó]r\s+na\s+ocen|jak\s+nazywa\s+się\s+prowadząc|"
                         r"наступн\w*\s+(лекці|занятт|лаб)|в\s+якій\s+аудиторі|присутн|скільки\s+бал|"
                         r"следующ\w*\s+(лекци|заняти|лаб)|в\s+какой\s+аудитории|сколько\s+балл|"
                         r"next\s+(lecture|class|lab)|which\s+room|attendance)", re.I)


def is_org(c: dict) -> bool:
    """True, якщо картка про організацію (дати, терміни, наступне заняття), а не про матеріал."""
    if not isinstance(c, dict):
        return False
    if str(c.get("kind") or "").lower() == "org":
        return True
    q = str(c.get("q") or "")
    if _ORG_ALWAYS.search(q):
        return True
    return bool(_ORG_WHEN.search(q) and _ORG_NOUN.search(q))


def normalize(c: dict) -> dict | None:
    """Перевіряє й нормалізує картку з quiz.json (v1 або v2). Невалідну — у flip або None."""
    if not isinstance(c, dict):
        return None
    q = str(c.get("q") or "").strip()
    if not q:
        return None
    t = str(c.get("type") or "").lower()
    if t not in TYPES:
        t = "flip"
    out = {"type": t, "q": q[:3000], "a": str(c.get("a") or "").strip()[:4000],
           "why": str(c.get("why") or "").strip()[:2000], "explain": str(c.get("explain") or "").strip()[:3000],
           "hint": _str_list(c.get("hint"), 4, 600), "tags": _str_list(c.get("tags"), 10, 40),
           "important": bool(c.get("important")), "source": _source(c.get("source")),
           "prev": str(c.get("prev") or "").strip()}
    if c.get("code"):
        out["code"] = str(c["code"])[:4000]
        out["lang"] = str(c.get("lang") or "")[:20]
    try:
        if t == "mcq":
            opts = _str_list(c.get("options"), 6, 600)
            corr = c.get("correct", c.get("answer"))
            if isinstance(corr, str) and len(corr.strip()) == 1 and corr.strip().upper() in "ABCDEF":
                corr = "ABCDEF".index(corr.strip().upper())
            corr = int(corr)
            if len(opts) < 2 or not 0 <= corr < len(opts):
                raise ValueError
            traps = c.get("traps") or {}
            if isinstance(traps, list):
                traps = {str(i): str(x) for i, x in enumerate(traps) if x}
            out.update(options=opts, correct=corr,
                       traps={str(k if str(k).isdigit() else "ABCDEF".index(str(k).upper()) if str(k).upper() in "ABCDEF" else k): str(v)[:600]
                              for k, v in traps.items() if v})
            out["a"] = out["a"] or opts[corr]
        elif t == "cloze":
            ans = str(c.get("answer") or "").strip()
            if not ans or ("___" not in q and "{{" not in q):
                raise ValueError
            out.update(answer=ans[:300], accept=_str_list(c.get("accept"), 10, 300))
            out["a"] = out["a"] or ans
        elif t == "tf":
            ans = c.get("answer")
            if isinstance(ans, str):
                ans = ans.strip().lower() in ("true", "prawda", "tak", "так", "правда", "1", "t")
            if not isinstance(ans, bool):
                raise ValueError
            out["answer"] = ans
        elif t == "order":
            steps = _str_list(c.get("steps"), 10, 400)
            if len(steps) < 2:
                raise ValueError
            out["steps"] = steps
        elif t == "code":
            ans = str(c.get("answer") or "").strip()
            if not ans or not out.get("code"):
                raise ValueError
            out.update(answer=ans[:1000], accept=_str_list(c.get("accept"), 10, 1000),
                       mode="complete" if str(c.get("mode")) == "complete" else "output")
            out["a"] = out["a"] or ans
        elif t == "flip" and not out["a"]:
            return None
    except (ValueError, TypeError):
        if out["a"]:
            out["type"] = "flip"
            for k in ("options", "correct", "traps", "answer", "accept", "steps", "mode"):
                out.pop(k, None)
        else:
            return None
    return out


# ---------------------------------------------------------------- збір карток
def _load_answers() -> dict:
    d = storage.read_json(ANS_FILE, {}) or {}
    return d.get("answers", d) if isinstance(d, dict) else {}


def _load_requests() -> list:
    d = storage.read_json(REQ_FILE, {}) or {}
    return d.get("requests", []) if isinstance(d, dict) else []


def _ts(v) -> float:
    p = fsrs._parse(v)
    return p.timestamp() if p else 0.0


def _subjects() -> dict:
    try:
        from .schedule import load_schedule
        return {s["id"]: s for s in load_schedule()["subjects"]}
    except Exception:
        return {}


def all_cards(subject: str | None = None, lecture: str | None = None, include_hidden: bool = False,
              data: dict | None = None) -> list[dict]:
    data = data or _progress()
    prog, over = data["cards"], data["overrides"]
    answers, reqs = _load_answers(), {r.get("key"): r for r in _load_requests()}
    now = _now()
    out, migrated = [], False
    subs = _subjects()

    def finish(base: dict, key: str, lid: str, m: dict | None, subj_id: str) -> None:
        nonlocal migrated
        ov = over.get(key) or {}
        if ov.get("hidden") and not include_hidden:
            return
        c = dict(base)
        for f in ("q", "a", "why", "explain"):
            if ov.get(f) is not None:
                c[f] = ov[f]
        if "important" in ov:
            c["important"] = bool(ov["important"])
        p = prog.get(key)
        if p is None and base.get("prev") and lid:
            old = _key(lid, base["prev"])
            if old in prog and old != key:  # Claude переробив картку — переносимо прогрес
                p = prog[key] = dict(prog[old], moved_from=old)
                migrated = True
        p = p or {}
        sj = subs.get(subj_id) or (m or {}).get("subject") or {}
        due_dt = fsrs._parse(p.get("due"))
        is_new = not p or p.get("state", "new") == "new"
        ans = answers.get(key)
        req = reqs.get(key)
        c.update({
            "key": key, "lecture_id": lid, "lecture_title": (m or {}).get("display_title") or "",
            "lecture_type": (m or {}).get("type") or "", "date": (m or {}).get("date"),
            "subject_id": subj_id, "subject": sj.get("short", ""), "color": sj.get("color", "#94a3b8"),
            "hidden": bool(ov.get("hidden")), "edited": bool({"q", "a", "why", "explain"} & set(ov)),
            "state": p.get("state", "new"), "s": p.get("s"), "d": p.get("d"), "reps": p.get("reps", 0),
            "lapses": p.get("lapses", 0), "due": p.get("due"), "last": p.get("last"), "rating": p.get("rating"),
            "is_new": is_new, "is_due": (not is_new) and (due_dt is None or due_dt <= now),
            "learned": (not is_new) and p.get("state") == "review" and (p.get("s") or 0) >= LEARNED_S,
            "leech": (p.get("lapses", 0) >= LEECH_LAPSES) or ((p.get("d") or 0) >= 8.5 and p.get("reps", 0) >= 3),
            "simpler": ans.get("text") if isinstance(ans, dict) else (ans if isinstance(ans, str) else None),
            "explain_pending": bool(req) and not (isinstance(ans, dict) and _ts(ans.get("at")) >= _ts(req.get("asked_at"))),
        })
        c.pop("prev", None)
        out.append(c)

    for m in lectures.list_all():
        if subject and m.get("subject_id") != subject:
            continue
        if lecture and m["id"] != lecture:
            continue
        qf = storage.LECTURES_DIR / m["id"] / "output" / "quiz.json"
        if not qf.exists():
            continue
        quiz = storage.read_json(qf, {}) or {}
        seen = set()
        for raw in quiz.get("cards", []) if isinstance(quiz, dict) else []:
            if is_org(raw):
                continue
            c = normalize(raw)
            if not c:
                continue
            k = _key(m["id"], c["q"])
            if k in seen:
                continue
            seen.add(k)
            finish(c, k, m["id"], m, m.get("subject_id") or "")
    for cc in data.get("custom", []):
        if subject and cc.get("subject_id") != subject:
            continue
        if lecture and cc.get("lecture_id") != lecture:
            continue
        c = normalize({**cc, "type": cc.get("type") or "flip"})
        if not c:
            continue
        m = None
        if cc.get("lecture_id"):
            try:
                m = lectures.enrich(lectures.read_meta(cc["lecture_id"]))
            except (KeyError, OSError):
                m = None
        finish({**c, "custom": True, "custom_id": cc["id"]}, "custom:" + cc["id"], cc.get("lecture_id") or "", m,
               cc.get("subject_id") or "")
    if migrated:
        with storage._lock:
            cur = _progress()
            for c in out:
                if c["key"] not in cur["cards"] and c["key"] in prog:
                    cur["cards"][c["key"]] = prog[c["key"]]
            _save(cur)
    return out


def with_preview(cards: list[dict], data: dict | None = None) -> list[dict]:
    data = data or _progress()
    now = _now()
    for c in cards:
        c["next"] = fsrs.preview(data["cards"].get(c["key"]), now)
    return cards


# ---------------------------------------------------------------- статистика
def _day_log(data: dict, day: str) -> dict:
    return data["log"].get(day) or {"n": 0, "new": 0, "again": 0, "ms": 0}


def stats(subject: str | None = None, cards: list[dict] | None = None, data: dict | None = None) -> dict:
    data = data or _progress()
    cards = cards if cards is not None else all_cards(subject, data=data)
    new_left = max(0, new_per_day() - _day_log(data, _today())["new"])
    by_subj: dict[str, dict] = {}
    for c in cards:
        s = by_subj.setdefault(c["subject_id"] or "", {"total": 0, "due": 0, "new": 0, "mastered": 0, "leech": 0})
        s["total"] += 1
        s["due"] += c["is_due"]
        s["new"] += c["is_new"]
        s["mastered"] += c["learned"]
        s["leech"] += c["leech"]
    tot = {k: sum(v[k] for v in by_subj.values()) for k in ("total", "due", "new", "mastered", "leech")}
    tot["new_left"] = new_left
    tot["today"] = tot["due"] + min(new_left, tot["new"])  # що буде в режимі «Сьогодні»
    return {"total": tot, "subjects": by_subj}


def _streak(log: dict) -> int:
    d = date.today()
    if not (log.get(d.isoformat()) or {}).get("n"):
        d -= timedelta(days=1)  # сьогодні ще не вчились — серія не обривається до кінця дня
    n = 0
    while (log.get(d.isoformat()) or {}).get("n"):
        n += 1
        d -= timedelta(days=1)
    return n


def progress() -> dict:
    data = _progress()
    cards = all_cards(data=data)
    log = data["log"]
    today = date.today()
    start = today - timedelta(days=7 * 20 + today.weekday())
    heat = []
    d = start
    while d <= today:
        e = log.get(d.isoformat()) or {}
        heat.append({"date": d.isoformat(), "n": int(e.get("n", 0)), "min": round(e.get("ms", 0) / 60000)})
        d += timedelta(days=1)
    tomorrow_end = datetime.combine(today + timedelta(days=1), datetime.max.time()).astimezone()
    due_tomorrow = sum(1 for c in cards if not c["is_new"] and (fsrs._parse(c["due"]) or tomorrow_end) <= tomorrow_end)
    new_total = sum(1 for c in cards if c["is_new"])
    subs = _subjects()
    per = {}
    for c in cards:
        p = per.setdefault(c["subject_id"] or "", {"total": 0, "learned": 0, "learning": 0, "new": 0, "due": 0})
        p["total"] += 1
        p["learned"] += c["learned"]
        p["new"] += c["is_new"]
        p["learning"] += (not c["is_new"]) and not c["learned"]
        p["due"] += c["is_due"]
    # темп до найближчого колоквіуму / екзамену з «Дедлайнів»
    tempo = []
    try:
        from . import eportal
        dls = eportal.list_deadlines()
    except Exception:
        dls = []
    now = _now()
    seen_subj = set()
    for x in dls:
        if x.get("done") or not EXAM_RX.search(f"{x.get('title', '')} {x.get('what', '')}"):
            continue
        due = fsrs._parse(x.get("due"))
        if not due or due < now:
            continue
        sid = x.get("subject_id") or ""
        if sid in seen_subj:
            continue
        seen_subj.add(sid)
        days_left = max(1, (due.date() - today).days)
        sc = [c for c in cards if not sid or c["subject_id"] == sid]
        fresh = sum(1 for c in sc if c["is_new"])
        weak = sum(1 for c in sc if not c["is_new"] and (c.get("s") or 0) < days_left)
        per_day = math.ceil(fresh / days_left) if fresh else 0
        tempo.append({"title": x.get("title"), "due": x.get("due"), "subject_id": sid,
                      "subject": (subs.get(sid) or {}).get("short", ""), "days_left": days_left,
                      "total": len(sc), "new": fresh, "weak": weak, "per_day": per_day,
                      "ok": per_day <= new_per_day()})
    tempo.sort(key=lambda t: t["due"])
    week = [_day_log(data, (today - timedelta(days=i)).isoformat()) for i in range(7)]
    return {"streak": _streak(log), "heatmap": heat, "subjects": per,
            "today": _day_log(data, today.isoformat()), "new_per_day": new_per_day(),
            "new_left": max(0, new_per_day() - _day_log(data, today.isoformat())["new"]),
            "forecast": {"tomorrow_reviews": due_tomorrow, "tomorrow_new": min(new_per_day(), new_total)},
            "week": {"n": sum(e["n"] for e in week), "min": round(sum(e.get("ms", 0) for e in week) / 60000)},
            "tempo": tempo[:6], "tests": data.get("tests", [])[-10:][::-1],
            "total": len(cards), "learned": sum(c["learned"] for c in cards)}


# ---------------------------------------------------------------- режими
def _blitz_items(cards: list[dict]) -> list[dict]:
    items = []
    for c in cards:
        if c["type"] == "tf":
            items.append({**c, "blitz_q": c["q"], "blitz_answer": c["answer"]})
        elif c["type"] == "mcq":
            i = random.randrange(len(c["options"]))
            items.append({**c, "key": c["key"] + f"#b{i}", "base_key": c["key"],
                          "blitz_q": f"{c['q']}\n→ {c['options'][i]}", "blitz_answer": i == c["correct"]})
        elif c["type"] == "cloze":
            items.append({**c, "key": c["key"] + "#b", "base_key": c["key"],
                          "blitz_q": re.sub(r"_{3,}|\{\{[^}]*\}\}", c["answer"], c["q"], count=1), "blitz_answer": True})
    random.shuffle(items)
    return items


def session(mode: str = "today", subject: str | None = None, lecture: str | None = None, n: int | None = None) -> dict:
    data = _progress()
    cards = all_cards(subject, lecture, data=data)
    rnd = random.Random()
    if mode == "test":
        auto = [c for c in cards if c["type"] in AUTO_TYPES]
        rest = [c for c in cards if c["type"] not in AUTO_TYPES]
        rnd.shuffle(auto)
        rnd.shuffle(rest)
        auto.sort(key=lambda c: (not c["important"], c["learned"]))
        pick = (auto + rest)[: n or 20]
        rnd.shuffle(pick)
        return {"mode": mode, "cards": with_preview(pick, data), "graded": False}
    if mode == "blitz":
        return {"mode": mode, "cards": _blitz_items(cards)[: n or 80], "seconds": 60, "graded": False}
    if mode == "hard":
        pick = [c for c in cards if c["leech"] or (c["rating"] == 1 and not c["is_new"])]
        pick.sort(key=lambda c: (-c["lapses"], -(c.get("d") or 0)))
        return {"mode": mode, "cards": with_preview(pick[: n or 30], data), "graded": True}
    if mode == "all":
        pick = cards[:]
        rnd.shuffle(pick)
        return {"mode": mode, "cards": with_preview(pick[: n or 200], data), "graded": True}
    if mode == "new":
        pick = [c for c in cards if c["is_new"]]
        return {"mode": mode, "cards": with_preview(pick[: n or new_per_day()], data), "graded": True}
    # «Сьогодні»: усі прострочені (найважливіші й найдавніші першими) + нові в межах денного ліміту, ~10 хв
    due = sorted([c for c in cards if c["is_due"]], key=lambda c: (not c["important"], c["due"] or ""))
    new_left = max(0, new_per_day() - _day_log(data, _today())["new"])
    fresh = [c for c in cards if c["is_new"]]
    fresh.sort(key=lambda c: (not c["important"], c["date"] or "", c["lecture_id"]))
    fresh = fresh[:new_left]
    budget, pick = 600.0, []
    for c in due:
        if budget <= 0:
            break
        pick.append(c)
        budget -= 12
    nf = [c for c in fresh if (budget := budget - 25) > -25]
    # нові вплітаємо між повтореннями
    out, j = [], 0
    step = max(1, len(pick) // (len(nf) + 1)) if nf else 1
    for i, c in enumerate(pick):
        out.append(c)
        if nf and j < len(nf) and (i + 1) % step == 0:
            out.append(nf[j])
            j += 1
    out += nf[j:]
    if n:
        out = out[:n]
    return {"mode": "today", "cards": with_preview(out, data), "graded": True,
            "due_total": len(due), "new_left": new_left}


# ---------------------------------------------------------------- відповіді
def _log(data: dict, n: int = 1, new: int = 0, again: int = 0, ms: int = 0) -> None:
    e = data["log"].setdefault(_today(), {"n": 0, "new": 0, "again": 0, "ms": 0})
    e["n"] += n
    e["new"] += new
    e["again"] += again
    e["ms"] += max(0, min(int(ms or 0), 10 * 60 * 1000))


def answer(key: str, rating: int | None = None, known: bool | None = None, ms: int = 0) -> dict:
    if rating is None:
        rating = 3 if known else 1
    rating = int(rating)
    if rating not in (1, 2, 3, 4):
        raise ValueError("Оцінка має бути 1..4")
    with storage._lock:
        data = _progress()
        old = data["cards"].get(key)
        was_new = not old or old.get("state", "new") == "new"
        p = fsrs.review(old, rating)
        data["cards"][key] = p
        _log(data, 1, int(was_new), int(rating == 1), ms)
        _save(data)
    return {**p, "next": fsrs.preview(p)}


def log_activity(mode: str, n: int, correct: int = 0, ms: int = 0, subject_id: str = "", mistakes: list | None = None) -> dict:
    with storage._lock:
        data = _progress()
        _log(data, max(0, int(n)), 0, 0, ms)
        if mode == "test":
            data["tests"].append({"at": storage.now_iso(), "subject_id": subject_id or "", "score": int(correct),
                                  "total": int(n), "mistakes": [str(x) for x in (mistakes or [])][:50]})
            data["tests"] = data["tests"][-50:]
        _save(data)
    return {"ok": True}


def reset(subject: str | None = None) -> int:
    keys = {c["key"] for c in all_cards(subject, include_hidden=True)}
    with storage._lock:
        data = _progress()
        n = 0
        for k in list(data["cards"]):
            if k in keys:
                del data["cards"][k]
                n += 1
        _save(data)
    return n


# ---------------------------------------------------------------- керування картками
EDITABLE = ("q", "a", "why", "explain")


def edit(key: str, patch: dict) -> dict:
    with storage._lock:
        data = _progress()
        ov = dict(data["overrides"].get(key) or {})
        if key.startswith("custom:"):
            cid = key.split(":", 1)[1]
            for cc in data["custom"]:
                if cc["id"] == cid:
                    for f in EDITABLE:
                        if isinstance(patch.get(f), str):
                            cc[f] = patch[f][:4000]
        else:
            for f in EDITABLE:
                if isinstance(patch.get(f), str):
                    ov[f] = patch[f][:4000]
        for f in ("hidden", "important"):
            if f in patch and patch[f] is not None:
                ov[f] = bool(patch[f])
        if patch.get("revert"):
            ov = {k: v for k, v in ov.items() if k not in EDITABLE}
        ov["edited_at"] = storage.now_iso()
        data["overrides"][key] = ov
        _save(data)
    return {"key": key, **ov}


def add_custom(body: dict) -> dict:
    q, a = str(body.get("q") or "").strip(), str(body.get("a") or "").strip()
    if not q or not a:
        raise ValueError("Потрібні питання й відповідь")
    sid, lid = str(body.get("subject_id") or ""), str(body.get("lecture_id") or "")
    if lid and not sid:
        try:
            sid = lectures.read_meta(lid).get("subject_id") or ""
        except KeyError:
            lid = ""
    cc = {"id": secrets.token_hex(5), "type": "flip", "q": q[:3000], "a": a[:4000], "why": str(body.get("why") or "")[:2000],
          "subject_id": sid, "lecture_id": lid, "important": bool(body.get("important")), "created_at": storage.now_iso()}
    with storage._lock:
        data = _progress()
        data["custom"].append(cc)
        _save(data)
    return cc


def delete_custom(cid: str) -> dict:
    with storage._lock:
        data = _progress()
        n0 = len(data["custom"])
        data["custom"] = [c for c in data["custom"] if c["id"] != cid]
        data["cards"].pop("custom:" + cid, None)
        _save(data)
    if len(data["custom"]) == n0:
        raise KeyError(cid)
    return {"ok": True}


def request_explain(key: str, note: str = "") -> dict:
    card = next((c for c in all_cards(include_hidden=True) if c["key"] == key), None)
    if not card:
        raise KeyError(key)
    with storage._lock:
        d = storage.read_json(REQ_FILE, {}) or {}
        reqs = [r for r in d.get("requests", []) if r.get("key") != key]
        reqs.append({"key": key, "lecture_id": card["lecture_id"], "subject_id": card["subject_id"],
                     "type": card["type"], "q": card["q"], "a": card.get("a", ""), "note": str(note or "")[:1000],
                     "asked_at": storage.now_iso()})
        storage.write_json(REQ_FILE, {"updated_at": storage.now_iso(), "requests": reqs})
    return {"ok": True}


def cancel_explain(key: str) -> dict:
    with storage._lock:
        d = storage.read_json(REQ_FILE, {}) or {}
        storage.write_json(REQ_FILE, {"updated_at": storage.now_iso(),
                                      "requests": [r for r in d.get("requests", []) if r.get("key") != key]})
    return {"ok": True}


def pending_explains() -> list[dict]:
    """Запити «Поясни простіше», на які Claude ще не відповів — ідуть у queue.json."""
    answers = _load_answers()
    out = []
    for r in _load_requests():
        a = answers.get(r.get("key"))
        if isinstance(a, dict) and _ts(a.get("at")) >= _ts(r.get("asked_at")):
            continue
        out.append(r)
    return out


# ---------------------------------------------------------------- скрипт PDF
def build_script(subject_id: str, subject_name: str) -> Path:
    """Склеює всі PDF-конспекти предмета в один файл із закладками."""
    from pypdf import PdfWriter, PdfReader  # встановлюється з requirements.txt

    items = [m for m in lectures.list_all() if m.get("subject_id") == subject_id and m["output"].get("pdf")]
    items.sort(key=lambda m: (m.get("date") or "", m.get("time") or ""))
    if not items:
        raise ValueError("Для цього предмета ще немає готових PDF-конспектів")
    w = PdfWriter()
    for m in items:
        pdf = storage.LECTURES_DIR / m["id"] / "output" / m["output"]["pdf"]
        start = len(w.pages)
        try:
            r = PdfReader(str(pdf))
        except Exception:
            continue
        for page in r.pages:
            w.add_page(page)
        title = f"{m.get('date') or ''} — {m.get('display_title') or subject_name}"
        w.add_outline_item(title, start)
    w.add_metadata({"/Title": f"{subject_name} — skrypt (konspekty wykładów)", "/Author": "Konspekt"})
    out = storage.TMP_DIR / f"script_{subject_id}.pdf"
    with open(out, "wb") as f:
        w.write(f)
    return out
