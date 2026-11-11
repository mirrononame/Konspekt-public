"""2.9: «Поділитися конспектами» — пакет .zip для однокурсника і його імпорт.

У пакет іде лише те, що допомагає вчитися: конспекти (notes.md/pdf), інструкції до лаб (plan.*), умови завдань (task/),
пам'ять предмета, план тем, карта курсу. Не йде: аудіо, відео, фото, нотатки студента, «Допоможи», оцінки, токени,
дедлайни, журнали чатів. Розшифровки, слайди, файли до здачі й проєкти — лише якщо студент сам увімкне.

  share.json                          — опис пакета (format 1)
  subjects/<sid>/memory.md, plan.json, course_map.json, zaliczenie.json, project/…
  lectures/<id>/meta.json, output/…, task/…, transcript.txt, slides/…
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from . import applog, lectures, project, storage
from .schedule import PALETTE, load_schedule, save_schedule

FORMAT = 1
OPTIONS = {"transcripts": False, "slides": False, "zdacha": False, "projects": False}
SUBJECT_FILES = ("memory.md", "plan.json", "course_map.json", "zaliczenie.json")
OUTPUT_FILES = ("notes.md", "notes.pdf", "notes_light.pdf", "plan.md", "plan.pdf", "plan.json", "result.json")
META_KEYS = ("id", "subject_id", "type", "date", "time", "title", "audio_language", "notes_language", "created_at")
MAX_FILE = 30 * 1024 * 1024
MAX_TOTAL = 800 * 1024 * 1024
SAFE_PART = re.compile(r"^[^\\/:*?\"<>|\x00-\x1f]{1,200}$")


def _files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return [p for p in sorted(folder.rglob("*")) if p.is_file() and not project.TEMP_RX.search(p.name) and p.stat().st_size <= MAX_FILE]


# ---------------------------------------------------------------- експорт
def subjects_summary() -> list[dict]:
    """Що є в кожному предметі — для вікна «Поділитися»."""
    items = lectures.list_all()
    out = []
    for s in load_schedule()["subjects"]:
        mine = [m for m in items if m.get("subject_id") == s["id"]]
        out.append({"id": s["id"], "name": s["name"], "short": s.get("short", ""), "lectures": len(mine),
                    "notes": sum(1 for m in mine if m["output"].get("pdf")), "project": project.exists(s["id"])})
    return out


def export(subject_ids: list[str], options: dict | None = None, author: str = "") -> Path:
    opt = {**OPTIONS, **{k: bool(v) for k, v in (options or {}).items() if k in OPTIONS}}
    sched = load_schedule()
    subjects = [s for s in sched["subjects"] if s["id"] in set(subject_ids)]
    if not subjects:
        raise ValueError("Виберіть хоча б один предмет")
    ids = {s["id"] for s in subjects}
    storage.TMP_DIR.mkdir(parents=True, exist_ok=True)
    target = storage.TMP_DIR / f"share_{uuid.uuid4().hex[:8]}.zip"
    lec_ids, seen, aliases = [], {}, {}
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        def put(src: Path, arc: str) -> None:
            """Однаковий файл (та сама умова в кількох заняттях) кладемо один раз, решта — посилання в share.json."""
            key = hashlib.md5(src.read_bytes()).hexdigest()
            if key in seen:
                aliases[arc] = seen[key]
            else:
                seen[key] = arc
                z.write(src, arc)

        for s in subjects:
            sd = storage.DATA_DIR / "subjects" / s["id"]
            for name in SUBJECT_FILES:
                if (sd / name).is_file():
                    put(sd / name, f"subjects/{s['id']}/{name}")
            if opt["projects"] and project.exists(s["id"]):
                p = project.pdir(s["id"])
                for f in [p / "stages.json"] + _files(p / "current") + _files(p / "steps"):
                    if f.is_file():
                        put(f, f"subjects/{s['id']}/project/{f.relative_to(p).as_posix()}")
        for m in lectures.list_all():
            if m.get("subject_id") not in ids or not m["output"].get("pdf"):
                continue  # без готового конспекту ділитися нічим
            d = lectures.lecture_dir(m["id"])
            base = f"lectures/{m['id']}"
            files = [f for f in m["files"] if f["kind"] == "task" or (opt["slides"] and f["kind"] == "slides")]
            meta = {k: m.get(k) for k in META_KEYS}
            meta["files"] = [{k: f.get(k) for k in ("kind", "name", "size")} for f in files]
            z.writestr(f"{base}/meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
            for name in OUTPUT_FILES:
                if (d / "output" / name).is_file():
                    put(d / "output" / name, f"{base}/output/{name}")
            if opt["zdacha"]:
                for f in _files(d / "output" / "zdacha"):
                    put(f, f"{base}/output/zdacha/{f.relative_to(d / 'output' / 'zdacha').as_posix()}")
            for f in files:
                p = lectures.file_path(m["id"], f["kind"], f["name"])
                if p.is_file() and p.stat().st_size <= MAX_FILE:
                    put(p, f"{base}/{p.parent.name}/{p.name}")
            if opt["transcripts"] and (d / "transcript.txt").is_file():
                put(d / "transcript.txt", f"{base}/transcript.txt")
            lec_ids.append(m["id"])
        z.writestr("share.json", json.dumps({
            "format": FORMAT, "app": "Konspekt", "created_at": storage.now_iso(), "author": (author or "").strip()[:80],
            "subjects": [{k: s.get(k) for k in ("id", "name", "short", "color")} for s in subjects],
            "lectures": len(lec_ids), "options": opt, "aliases": aliases}, ensure_ascii=False, indent=2))
    applog.event("share_export", subjects=len(subjects), lectures=len(lec_ids))
    return target


# ---------------------------------------------------------------- імпорт
def _safe_names(z: zipfile.ZipFile) -> list[str]:
    total, names = 0, []
    for i in z.infolist():
        if i.is_dir():
            continue
        p = PurePosixPath(i.filename)
        if p.is_absolute() or ".." in p.parts or not all(SAFE_PART.match(x) for x in p.parts):
            raise ValueError(f"Підозрілий шлях у пакеті: {i.filename}")
        total += i.file_size
        if i.file_size > MAX_FILE or total > MAX_TOTAL:
            raise ValueError("Пакет завеликий")
        names.append(i.filename)
    return names


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9ąćęłńóśźż]+", "", (s or "").lower())


def _match_subject(s: dict, mine: list[dict]) -> dict | None:
    for x in mine:
        if _norm(x["name"]) == _norm(s.get("name")) or (s.get("short") and _norm(x.get("short")) == _norm(s["short"])):
            return x
    return None


def read_pack(path: Path) -> tuple[dict, list[str]]:
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ValueError("Це не пакет «Конспекту» (.zip)")
    with z:
        names = _safe_names(z)
        if "share.json" not in names:
            raise ValueError("У пакеті немає share.json — це не пакет «Конспекту»")
        info = json.loads(z.read("share.json"))
    if info.get("app") != "Konspekt" or int(info.get("format") or 0) > FORMAT:
        raise ValueError("Пакет з новішої версії «Конспекту» — оновіть застосунок")
    al = info.get("aliases") or {}
    if not isinstance(al, dict):
        raise ValueError("Пакет пошкоджено")
    for k, v in al.items():
        pk = PurePosixPath(str(k))
        if pk.is_absolute() or ".." in pk.parts or not all(SAFE_PART.match(x) for x in pk.parts) or v not in names:
            raise ValueError(f"Підозрілий шлях у пакеті: {k}")
    info["aliases"] = al
    return info, names + [k for k in al if k not in names]


def _pack_lectures(z: zipfile.ZipFile, names: list[str]) -> list[dict]:
    out = []
    for n in names:
        parts = n.split("/")
        if len(parts) == 3 and parts[0] == "lectures" and parts[2] == "meta.json":
            meta = json.loads(z.read(n))
            if isinstance(meta, dict):
                meta["_dir"] = f"lectures/{parts[1]}"
                out.append(meta)
    return out


def preview(path: Path) -> dict:
    """Що станеться при імпорті — без жодних змін."""
    info, names = read_pack(path)
    mine = load_schedule()["subjects"]
    existing = lectures.list_all()
    with zipfile.ZipFile(path) as z:
        pack = _pack_lectures(z, names)
    subs = []
    for s in info.get("subjects") or []:
        loc = _match_subject(s, mine)
        lec = [m for m in pack if m.get("subject_id") == s.get("id")]
        new = skip = fill = 0
        for m in lec:
            same = _same_lecture(m, loc["id"] if loc else None, existing)
            if not same:
                new += 1
            elif same["output"].get("pdf"):
                skip += 1
            else:
                fill += 1
        subs.append({"id": s.get("id"), "name": s.get("name"), "match": loc["name"] if loc else None,
                     "new": new, "fill": fill, "skip": skip,
                     "project": any(n.startswith(f"subjects/{s.get('id')}/project/") for n in names)})
    return {"author": info.get("author", ""), "created_at": info.get("created_at"), "subjects": subs,
            "options": info.get("options") or {}}


def _same_lecture(m: dict, sid: str | None, existing: list[dict]) -> dict | None:
    if not sid:
        return None
    return next((x for x in existing if x.get("subject_id") == sid and x.get("date") == m.get("date")
                 and (x.get("type") or "W") == (m.get("type") or "W")), None)


def _extract(z: zipfile.ZipFile, prefix: str, names: list[str], dest: Path, overwrite: bool = False, aliases: dict | None = None) -> int:
    n = 0
    for name in names:
        if not name.startswith(prefix + "/"):
            continue
        rel = name[len(prefix) + 1:]
        if not rel or rel == "meta.json":
            continue
        t = dest / rel
        if t.exists() and not overwrite:
            continue
        t.parent.mkdir(parents=True, exist_ok=True)
        with z.open((aliases or {}).get(name, name)) as src, open(t, "wb") as f:
            shutil.copyfileobj(src, f)
        n += 1
    return n


def apply(path: Path) -> dict:
    """Імпорт: нові предмети й заняття додаються, власні конспекти студента не перезаписуються ніколи."""
    info, names = read_pack(path)
    al = info["aliases"]
    author = (info.get("author") or "однокурсник")[:80]
    sched = load_schedule()
    mine = sched["subjects"]
    sid_map, added_subjects = {}, []
    for s in info.get("subjects") or []:
        loc = _match_subject(s, mine)
        if not loc:
            new_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(s.get("id") or ""))[:24] or uuid.uuid4().hex[:6]
            while any(x["id"] == new_id for x in mine):
                new_id += uuid.uuid4().hex[:2]
            loc = {"id": new_id, "name": str(s.get("name") or new_id)[:200], "short": str(s.get("short") or "")[:12],
                   "color": s.get("color") or PALETTE[len(mine) % len(PALETTE)]}
            mine.append(loc)
            added_subjects.append(loc["name"])
        sid_map[s.get("id")] = loc["id"]
    if added_subjects:
        save_schedule(sched)
    stats = {"subjects_added": added_subjects, "lectures_new": 0, "lectures_filled": 0, "lectures_skipped": 0,
             "subject_files": 0, "projects": []}
    existing = lectures.list_all()
    with zipfile.ZipFile(path) as z:
        for theirs, ours in sid_map.items():
            sd = storage.DATA_DIR / "subjects" / ours
            stats["subject_files"] += _extract(z, f"subjects/{theirs}", [n for n in names if "/project/" not in n], sd, aliases=al)
            proj = [n for n in names if n.startswith(f"subjects/{theirs}/project/")]
            empty = not project.exists(ours) or not (project.stages(ours) or project._files(project.pdir(ours) / "current"))
            if proj and empty:  # свій проєкт студента не чіпаємо; порожній (створений автоматично) — заповнюємо
                if not project.exists(ours):
                    project.create(ours, f"Projekt (od: {author})")
                _extract(z, f"subjects/{theirs}/project", proj, project.pdir(ours), aliases=al)
                project.log(ours, f"Етапи й файли проєкту імпортовано від: {author}")
                stats["projects"].append(ours)
        for m in _pack_lectures(z, names):
            sid = sid_map.get(m.get("subject_id"))
            if not sid:
                continue
            same = _same_lecture(m, sid, existing)
            if same and same["output"].get("pdf"):
                stats["lectures_skipped"] += 1
                continue
            if same:
                lid, d = same["id"], lectures.lecture_dir(same["id"])
                stats["lectures_filled"] += 1
            else:
                meta = lectures.create({"subject_id": sid, "type": m.get("type"), "date": m.get("date"), "time": m.get("time"),
                                        "title": m.get("title") or "", "audio_language": m.get("audio_language"),
                                        "notes_language": m.get("notes_language")})
                lid, d = meta["id"], lectures.lecture_dir(meta["id"])
                stats["lectures_new"] += 1
            _extract(z, m["_dir"], names, d, aliases=al)
            got = [f for f in (m.get("files") or []) if (d / lectures.KIND_DIRS.get(f.get("kind"), "other") / str(f.get("name"))).is_file()]

            def fn(x, got=got):
                have = {(f["kind"], f["name"]) for f in x["files"]}
                x["files"] += [{"kind": f["kind"], "name": f["name"], "size": f.get("size") or 0, "added_at": storage.now_iso(),
                                "source": "share"} for f in got if (f["kind"], f["name"]) not in have]
                x["shared"] = {"from": author, "at": storage.now_iso()}
            lectures.mutate(lid, fn)
    lectures.write_queue()
    applog.event("share_import", new=stats["lectures_new"], filled=stats["lectures_filled"], skipped=stats["lectures_skipped"])
    return stats
