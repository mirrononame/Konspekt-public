"""2.4: «Проєкт» предмета — поетапно й по одному кроку, з одним місцем для файлів.

Проєкт (BD2, SO, TS…) триває тижнями, тож він живе не в записі однієї зустрічі, а в предметі:

data/subjects/<id>/project/
  project.json      — назва, поточний етап, запит кроку, відмітки «зроблено», журнал змін (пише застосунок)
  stages.json       — етапи з датами й вимогами (пише Claude з «Etapy realizacji…», пам'яті й слів викладача)
  steps/step_NN.md  — інструкція ОДНОГО кроку (≤ 1 сторінка): що зробити, як перевірити, що надіслати назад (пише Claude)
  steps/step_NN.json— {completed_at, title, stage, minutes, check, send_back, changelog} (пише Claude ОСТАННІМ)
  current/          — по одній АКТУАЛЬНІЙ версії кожного документа/моделі (те, що здається)
  versions/         — попередні версії; застосунок сам переносить сюди старий файл, коли кладуть новий з тією ж назвою
  work/             — робочі файли студента (docx, що він править, проєкт VP), окремо від здачі

Один канал до Claude: поки крок готується, новий запит по проєкту не приймається (і «Допоможи»/звіт/план
на зустрічах проєкту теж ведуть сюди), щоб не було кількох паралельних версій інструкцій і файлів.
"""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from . import storage

AREAS = ("current", "work", "versions")
TEMP_RX = re.compile(r"^(~\$|\.~lock\.|\.)|\.(tmp|bak)$|#$", re.I)  # Word/LibreOffice тимчасові файли й блокування


def pdir(sid: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", sid or ""):
        raise KeyError(sid)
    return storage.DATA_DIR / "subjects" / sid / "project"


def _ts(v) -> float:
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return (dt if dt.tzinfo else dt.astimezone()).timestamp()
    except Exception:
        return 0.0


def exists(sid: str) -> bool:
    try:
        return (pdir(sid) / "project.json").exists()
    except KeyError:
        return False


def _meta(sid: str) -> dict:
    d = storage.read_json(pdir(sid) / "project.json", {}) or {}
    return d if isinstance(d, dict) else {}


def _save(sid: str, d: dict) -> None:
    storage.write_json(pdir(sid) / "project.json", d)


def create(sid: str, title: str) -> dict:
    p = pdir(sid)
    if (p / "project.json").exists():
        raise ValueError("Проєкт уже є")
    for a in (*AREAS, "steps"):
        (p / a).mkdir(parents=True, exist_ok=True)
    _save(sid, {"title": (title or "Projekt").strip()[:200], "created_at": storage.now_iso(), "current_stage": "",
                "done": [], "step_req": None, "changelog": [], "instructions_language": "uk", "docs_language": "pl"})
    return info(sid)


def log(sid: str, text: str) -> None:
    d = _meta(sid)
    d.setdefault("changelog", []).append({"at": storage.now_iso(), "text": str(text)[:500]})
    d["changelog"] = d["changelog"][-200:]
    _save(sid, d)


# ---------------------------------------------------------------- файли: актуальне / версії / робоче
def _files(folder: Path, rel: str = "") -> list[dict]:
    out = []
    if not folder.is_dir():
        return out
    for f in sorted(folder.rglob("*")):
        if not f.is_file() or TEMP_RX.search(f.name):
            continue
        st = f.stat()
        out.append({"name": f.relative_to(folder).as_posix(), "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds")})
    return out


def _archive(src: Path, sid: str) -> str:
    """Стару версію — у versions/<назва>__<дата_час>.<розш>; нічого не перезаписується й не губиться."""
    stamp = datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y-%m-%d_%H%M")
    dst = storage.unique_path(pdir(sid) / "versions", f"{src.stem}__{stamp}{src.suffix}")
    shutil.move(str(src), str(dst))
    return dst.name


def put_file(sid: str, area: str, name: str, data_path: Path) -> dict:
    if area not in ("current", "work"):
        raise ValueError("Куди покласти: current або work")
    name = storage.safe_filename(name)
    if TEMP_RX.search(name):
        raise ValueError("Це тимчасовий файл Word/LibreOffice — закрийте документ і надішліть сам файл")
    target = pdir(sid) / area / name
    target.parent.mkdir(parents=True, exist_ok=True)
    note = ""
    if target.exists():
        note = f" (попередня → versions/{_archive(target, sid)})"
    shutil.move(str(data_path), str(target))
    log(sid, f"{'Актуальне' if area == 'current' else 'Робоче'}: {name}{note}")
    return info(sid)


def promote(sid: str, name: str, as_name: str = "") -> dict:
    """Робочий файл → актуальний (для здачі). Попередній актуальний з тією ж назвою — у versions/."""
    src = (pdir(sid) / "work" / name).resolve()
    if pdir(sid).resolve() not in src.parents or not src.is_file():
        raise KeyError(name)
    target = pdir(sid) / "current" / storage.safe_filename(as_name or src.name)
    note = f" (попередня → versions/{_archive(target, sid)})" if target.exists() else ""
    shutil.copy2(src, target)
    log(sid, f"Робоче → актуальне: {target.name}{note}")
    return info(sid)


def file_path(sid: str, area: str, name: str) -> Path:
    if area not in AREAS + ("steps",):
        raise KeyError(area)
    base = (pdir(sid) / area).resolve()
    p = (base / name).resolve()
    if base not in p.parents or not p.is_file():
        raise KeyError(name)
    return p


# ---------------------------------------------------------------- етапи й кроки
def stages(sid: str) -> list[dict]:
    d = storage.read_json(pdir(sid) / "stages.json", {}) if (pdir(sid) / "stages.json").exists() else {}
    items = d.get("stages") if isinstance(d, dict) else None
    return [s for s in items or [] if isinstance(s, dict) and s.get("id")]


def steps(sid: str) -> list[dict]:
    done = set(_meta(sid).get("done") or [])
    out = []
    sd = pdir(sid) / "steps"
    if not sd.is_dir():
        return out
    for j in sorted(sd.glob("step_*.json")):
        m = re.match(r"step_(\d+)\.json$", j.name)
        md = j.with_suffix(".md")
        rec = storage.read_json(j, {}) or {}
        if not m or not isinstance(rec, dict) or not md.exists():
            continue
        n = int(m.group(1))
        out.append({"n": n, "title": rec.get("title") or f"Krok {n}", "stage": rec.get("stage", ""),
                    "minutes": rec.get("minutes"), "check": rec.get("check", ""), "send_back": rec.get("send_back") or [],
                    "completed_at": rec.get("completed_at"), "done": n in done,
                    "md": md.read_text(encoding="utf-8", errors="replace")})
    out.sort(key=lambda s: s["n"])
    return out


def _pending(d: dict, st: list[dict]) -> bool:
    req = d.get("step_req")
    if not req:
        return False
    return not any(_ts(s["completed_at"]) >= _ts(req.get("requested_at")) for s in st)


def busy(sid: str) -> bool:
    """Claude зараз готує крок цього проєкту — інші запити по проєкту чекають."""
    return exists(sid) and _pending(_meta(sid), steps(sid))


def info(sid: str) -> dict:
    if not exists(sid):
        return {"exists": False, "subject_id": sid}
    d = _meta(sid)
    st = steps(sid)
    stg = stages(sid)
    passed = set(d.get("stages_done") or [])  # 2.6: «Етап здано» — позначає студент
    for s in stg:
        if s["id"] in passed:
            s["status"] = "done"
    open_stages = [s for s in stg if s.get("status") != "done"]
    cur = d.get("current_stage") if d.get("current_stage") and d.get("current_stage") not in passed else ""
    cur = cur or (open_stages[0]["id"] if open_stages else "") or next((s["stage"] for s in reversed(st) if s.get("stage")), "")
    p = pdir(sid)
    return {"exists": True, "subject_id": sid, "title": d.get("title"), "created_at": d.get("created_at"),
            "stages": stg, "current_stage": cur, "steps": st, "pending": _pending(d, st), "req": d.get("step_req"),
            "next_n": (st[-1]["n"] + 1) if st else 1, "open_step": next((s for s in reversed(st) if not s["done"]), None),
            "files": {a: _files(p / a) for a in AREAS}, "changelog": (d.get("changelog") or [])[-30:][::-1]}


def request_step(sid: str, note: str = "", kind: str = "next") -> dict:
    if kind not in ("next", "stage", "fix"):
        raise ValueError("Невідомий запит")
    d = _meta(sid)
    st = steps(sid)
    if _pending(d, st):
        raise ValueError("Claude ще готує попередній крок — дочекайтеся його")
    d["step_req"] = {"requested_at": storage.now_iso(), "note": (note or "").strip()[:3000], "kind": kind,
                     "n": (st[-1]["n"] + 1) if st else 1}
    _save(sid, d)
    log(sid, {"next": "Запит наступного кроку", "stage": "Запит: увесь поточний етап", "fix": "Запит: виправити крок"}[kind]
        + (f" — «{d['step_req']['note'][:120]}»" if d["step_req"]["note"] else ""))
    return info(sid)


def cancel_step(sid: str) -> dict:
    d = _meta(sid)
    d["step_req"] = None
    _save(sid, d)
    return info(sid)


def set_done(sid: str, n: int, done: bool = True) -> dict:
    d = _meta(sid)
    s = set(d.get("done") or [])
    (s.add if done else s.discard)(int(n))
    d["done"] = sorted(s)
    _save(sid, d)
    log(sid, f"Крок {n}: {'зроблено' if done else 'знову відкрито'}")
    return info(sid)


def stage_done(sid: str, stage_id: str, done: bool = True) -> dict:
    """«Етап здано» → наступний етап стає поточним; наступний крок Claude робить уже для нього."""
    d = _meta(sid)
    s = set(d.get("stages_done") or [])
    (s.add if done else s.discard)(str(stage_id)[:40])
    d["stages_done"] = sorted(s)
    d["current_stage"] = ""
    _save(sid, d)
    log(sid, f"Етап {stage_id}: {'здано' if done else 'знову відкрито'}")
    return info(sid)


def ensure_projects() -> list[str]:
    """2.6: «Проєкт» є в кожному предметі, де є заняття-проєкт (P) у розкладі або серед записів."""
    from . import lectures
    from .schedule import load_schedule
    sch = load_schedule()
    subj = {s["id"]: s for s in sch["subjects"]}
    with_p = {c["subject_id"] for c in sch.get("classes", []) if c.get("type") == "P"}
    try:
        with_p |= {m.get("subject_id") for m in lectures.list_all() if m.get("type") == "P"}
    except Exception:
        pass
    made = []
    for sid in sorted(x for x in with_p if x in subj):
        if not exists(sid):
            create(sid, f"Projekt {subj[sid].get('short') or subj[sid].get('name')}")
            log(sid, "Проєкт створено автоматично: у предметі є заняття-проєкт. Етапи складе Claude на першому кроці.")
            made.append(sid)
    return made


def set_stage(sid: str, stage_id: str) -> dict:
    d = _meta(sid)
    d["current_stage"] = str(stage_id)[:40]
    _save(sid, d)
    log(sid, f"Поточний етап: {stage_id}")
    return info(sid)


def all_projects() -> list[str]:
    root = storage.DATA_DIR / "subjects"
    return sorted(p.parent.parent.name for p in root.glob("*/project/project.json")) if root.exists() else []


def pending_steps(items: list[dict] | None = None) -> list[dict]:
    """Черга для Claude: один крок на проєкт (розділ J протоколу)."""
    from . import lectures
    items = items if items is not None else lectures.list_all()
    out = []
    for sid in all_projects():
        d = _meta(sid)
        st = steps(sid)
        if not _pending(d, st):
            continue
        req = d["step_req"]
        n = req.get("n") or ((st[-1]["n"] + 1) if st else 1)
        meetings = [m for m in items if m.get("subject_id") == sid and m.get("type") == "P"]
        meetings.sort(key=lambda m: m.get("date") or "")
        rel = f"subjects/{sid}/project"
        out.append({
            "subject_id": sid, "title": d.get("title"), "kind": req.get("kind", "next"), "note": req.get("note", ""),
            "stages_done": d.get("stages_done") or [],
            "requested_at": req["requested_at"], "n": n, "current_stage": info(sid)["current_stage"],
            "instructions_language": d.get("instructions_language", "uk"), "docs_language": d.get("docs_language", "pl"),
            "stages": f"{rel}/stages.json", "memory": f"subjects/{sid}/memory.md",
            "previous_steps": [{"n": s["n"], "title": s["title"], "done": s["done"], "file": f"{rel}/steps/step_{s['n']:02d}.md"} for s in st][-8:],
            "current_files": [f"{rel}/current/{f['name']}" for f in _files(pdir(sid) / "current")],
            "work_files": [f"{rel}/work/{f['name']}" for f in _files(pdir(sid) / "work")],
            "meetings": [{"date": m.get("date"), "notes": f"lectures/{m['id']}/output/notes.md",
                          "task_files": [f"lectures/{m['id']}/task/{f['name']}" for f in m.get("files", []) if f.get("kind") == "task"]}
                         for m in meetings][-6:],
            "changelog": (d.get("changelog") or [])[-15:],
            "output": {"md": f"{rel}/steps/step_{n:02d}.md", "json": f"{rel}/steps/step_{n:02d}.json",
                       "current_dir": f"{rel}/current", "stages": f"{rel}/stages.json"},
        })
    return out


def is_project_meeting(meta: dict) -> bool:
    return (meta.get("type") == "P") and exists(meta.get("subject_id") or "")
