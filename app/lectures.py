"""Робота з лекціями: створення, файли, статуси, пошук, кошик."""
from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from . import applog, storage
from .schedule import load_schedule

AUDIO_EXT = {".mp3", ".m4a", ".wav", ".ogg", ".oga", ".opus", ".aac", ".flac", ".wma", ".amr", ".3gp",
             ".webm", ".mp4", ".mkv", ".mov", ".m4b", ".caf", ".aiff", ".aif"}
SLIDES_EXT = {".pdf", ".ppt", ".pptx", ".odp", ".key", ".doc", ".docx", ".odt", ".txt", ".md", ".rtf"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
KIND_DIRS = {"audio": "audio", "video": "video", "slides": "slides", "image": "images", "other": "other",
             "task": "task", "code": "code"}  # task/code — умова завдання і «Мій код» (лаби, проєкт)
VIDEO_LIKE = {".mp4", ".mkv", ".mov", ".avi", ".m4v", ".wmv", ".flv", ".ts", ".mts", ".m2ts", ".webm", ".3gp", ".mpg", ".mpeg"}
AUDIO_EXT |= {".avi", ".m4v", ".wmv", ".flv", ".ts", ".mts", ".m2ts", ".mpg", ".mpeg"}
LANGS = {"pl": "Polski", "uk": "Українська", "ru": "Русский", "en": "English"}

STATUS_LABELS = {
    "draft": "Чернетка",
    "recording": "Іде запис",
    "transcribing": "Розшифровка",
    "waiting_claude": "Чекає на Claude",
    "done": "Готово",
    "error": "Помилка",
}


def kind_of(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in AUDIO_EXT:
        return "audio"
    if ext in SLIDES_EXT:
        return "slides"
    if ext in IMAGE_EXT:
        return "image"
    return "other"


def lecture_dir(lid: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}", lid or ""):
        raise KeyError(lid)
    p = storage.LECTURES_DIR / lid
    if not (p / "meta.json").exists() and not (p / "meta.json.bak").exists():
        raise KeyError(lid)
    return p


def read_meta(lid: str) -> dict:
    d = lecture_dir(lid)
    meta = storage.read_json(d / "meta.json")
    if not isinstance(meta, dict):
        raise KeyError(lid)
    return _normalize(meta, d)


def write_meta(meta: dict) -> None:
    meta["updated_at"] = storage.now_iso()
    clean = {k: v for k, v in meta.items() if not k.startswith("_")}
    storage.write_json(storage.LECTURES_DIR / meta["id"] / "meta.json", clean)


def _normalize(meta: dict, d: Path) -> dict:
    meta.setdefault("files", [])
    meta.setdefault("title", "")
    meta.setdefault("user_notes", "")
    meta.setdefault("audio_language", "pl")
    meta.setdefault("notes_language", "pl")
    meta.setdefault("type", "W")
    meta.setdefault("transcribe", {"state": "none"})
    meta.setdefault("claude", {"requested": False})
    # файли, яких більше немає на диску, прибираємо зі списку
    meta["files"] = [f for f in meta["files"] if (d / KIND_DIRS.get(f.get("kind"), "other") / f.get("name", "")).exists()]
    return meta


def mutate(lid: str, fn) -> dict:
    """Атомарне читання-зміна-запис метаданих (захист від гонок між потоками)."""
    with storage._lock:
        meta = read_meta(lid)
        fn(meta)
        write_meta(meta)
        return meta


def new_id(date_s: str, time_s: str, subject_id: str) -> str:
    base = f"{date_s}_{(time_s or '0000').replace(':', '')}_{subject_id or 'x'}"
    base = re.sub(r"[^A-Za-z0-9_-]", "", base)[:60]
    return f"{base}_{uuid.uuid4().hex[:4]}"


def create(data: dict) -> dict:
    storage.ensure_dirs()
    date_s = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    time_s = data.get("time") or ""
    lid = new_id(date_s, time_s, data.get("subject_id") or "")
    d = storage.LECTURES_DIR / lid
    d.mkdir(parents=True, exist_ok=False)
    meta = {
        "id": lid,
        "subject_id": data.get("subject_id") or "",
        "type": data.get("type") or "W",
        "date": date_s,
        "time": time_s,
        "title": (data.get("title") or "").strip()[:300],
        "audio_language": data.get("audio_language") or "pl",
        "notes_language": data.get("notes_language") or "pl",
        "user_notes": (data.get("user_notes") or "")[:20000],
        "files": [],
        "transcribe": {"state": "none"},
        "claude": {"requested": False},
        "created_at": storage.now_iso(),
    }
    write_meta(meta)
    applog.event("lecture_added", lecture=lid, subject=meta["subject_id"], type=meta["type"])
    return meta


def update(lid: str, patch: dict) -> dict:
    def fn(meta):
        for k in ("subject_id", "type", "date", "time", "title", "audio_language", "notes_language", "user_notes"):
            if k in patch and patch[k] is not None:
                meta[k] = patch[k] if not isinstance(patch[k], str) else patch[k][:20000]
        if patch.get("schedule_ok"):  # 2.2: «Так і є» — розбіжність з розкладом підтверджено для цих дати/часу/предмета
            meta["schedule_ok"] = schedule_sig(meta)
    return mutate(lid, fn)


def schedule_sig(meta: dict) -> str:
    return "|".join(str(meta.get(k) or "") for k in ("subject_id", "type", "date", "time"))


async def save_upload(lid: str, upload, duration: float | None = None, kind: str | None = None) -> dict:
    """Потокове збереження великого файлу: спочатку в .tmp, потім переміщення.
    kind="task" | "code" — файл кладеться у task/ або code/ як є (без розпізнавання типу)."""
    read_meta(lid)  # KeyError → 404, якщо заняття вже немає
    name = storage.safe_filename(upload.filename)
    forced = kind if kind in ("task", "code") else None
    kind = forced or kind_of(name)
    tmp = storage.TMP_DIR / f"{uuid.uuid4().hex}.part"
    h = hashlib.sha256()
    size = 0
    try:
        with open(tmp, "wb") as f:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                size += len(chunk)
        if size == 0:
            raise ValueError("Порожній файл")
        sha = h.hexdigest()
        if not forced and kind == "audio" and Path(name).suffix.lower() in VIDEO_LIKE:
            try:
                from . import video
                if video.have_av() and video.has_video_stream(tmp):
                    kind = "video"
            except Exception as e:
                applog.error("video probe", e)
        existing = next((f for f in read_meta(lid)["files"] if f.get("sha256") == sha and f.get("kind") == kind), None)
        if existing:
            return {"file": existing, "duplicate_of": None, "already_here": True}
        target_dir = storage.LECTURES_DIR / lid / KIND_DIRS[kind]
        target_dir.mkdir(parents=True, exist_ok=True)
        target = storage.unique_path(target_dir, name)
        shutil.move(str(tmp), str(target))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    entry = {"name": target.name, "kind": kind, "size": size, "sha256": sha, "added_at": storage.now_iso()}
    if duration and kind in ("audio", "video"):
        try:
            entry["duration"] = round(float(duration), 1)
        except (TypeError, ValueError):
            pass
    mutate(lid, lambda meta: meta["files"].append(entry))
    dup = find_duplicate(sha, exclude=lid)
    return {"file": entry, "duplicate_of": dup}


def find_duplicate(sha: str, exclude: str | None = None) -> str | None:
    for d in storage.LECTURES_DIR.iterdir():
        if d.name == exclude:
            continue
        meta = storage.read_json(d / "meta.json")
        if isinstance(meta, dict) and any(f.get("sha256") == sha for f in meta.get("files", [])):
            return d.name
    return None


def file_path(lid: str, kind: str, name: str) -> Path:
    d = lecture_dir(lid)
    folder = d / KIND_DIRS.get(kind, "other")
    p = (folder / name).resolve()
    if folder.resolve() not in p.parents or not p.is_file():
        raise KeyError(name)
    return p


def delete_file(lid: str, kind: str, name: str) -> dict:
    p = file_path(lid, kind, name)
    trash = storage.TRASH_DIR / "_files" / lid
    trash.mkdir(parents=True, exist_ok=True)
    dst = storage.unique_path(trash, p.name)
    shutil.move(str(p), str(dst))
    storage.touch(dst)  # відлік днів у кошику — від моменту видалення
    return mutate(lid, lambda m: None)


def output_info(d: Path) -> dict:
    out = d / "output"
    res = storage.read_json(out / "result.json", {}) if out.exists() else {}
    files = []
    if out.exists():
        for p in sorted(out.iterdir()):
            if p.is_file() and not p.name.startswith((".", "~$")) and not p.name.endswith((".tmp", ".bak", "#")):
                files.append({"name": p.name, "size": p.stat().st_size,
                              "mtime": datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat(timespec="seconds")})
    pdf = out / "notes.pdf"
    if not pdf.exists():
        pdfs = [f for f in files if f["name"].lower().endswith(".pdf")]
        pdf = out / pdfs[0]["name"] if pdfs else None
    return {"result": res if isinstance(res, dict) else {}, "files": files,
            "pdf": pdf.name if pdf and pdf.exists() else None,
            "pdf_mtime": pdf.stat().st_mtime if pdf and pdf.exists() else None,
            "deliverables": deliverables(out, files)}


SERVICE_RX = re.compile(r"^(notes|plan\.|quiz|result|help\.md|audio_diagnostics)", re.I)


def deliverables(out: Path, files: list[dict]) -> list[dict]:
    """2.2: «Здача» — звіт, код, документація. Нове місце — output/zdacha/; у старих заняттях — усе в output, що не конспект/картки/план."""
    res = []
    z = out / "zdacha"
    if z.is_dir():
        for p in sorted(z.iterdir()):
            if p.is_file() and not p.name.startswith((".", "~$")) and not p.name.endswith((".tmp", ".bak", "#")):
                res.append({"name": f"zdacha/{p.name}", "title": p.name, "size": p.stat().st_size})
    res += [{"name": f["name"], "title": f["name"], "size": f["size"]} for f in files if not SERVICE_RX.match(f["name"])]
    return res


def _ts(v) -> float:
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.astimezone()
        return dt.timestamp()
    except Exception:
        return 0.0


def compute_status(meta: dict, out: dict) -> str:
    if meta.get("recording", {}).get("state") == "recording":
        return "recording"
    tr = meta.get("transcribe", {}).get("state")
    cl = meta.get("claude", {})
    res = out.get("result") or {}
    req_at = _ts(cl.get("requested_at"))
    done_at = _ts(res.get("completed_at")) or (out.get("pdf_mtime") or 0.0)
    fresh = (not cl.get("requested")) or done_at >= req_at
    if out.get("pdf") and res.get("status", "done") == "done" and fresh:
        return "done"
    if res.get("status") == "error" and done_at and done_at >= req_at:
        return "error"
    if tr in ("queued", "running") or any(v.get("state") in ("queued", "processing") for v in (meta.get("video") or {}).values()):
        return "transcribing"
    if cl.get("requested"):
        return "waiting_claude"
    if tr == "error":
        return "error"
    return "draft"


def enrich(meta: dict, full: bool = False) -> dict:
    d = storage.LECTURES_DIR / meta["id"]
    out = output_info(d)
    sched = load_schedule()
    subj = next((s for s in sched["subjects"] if s["id"] == meta.get("subject_id")), None)
    tr_path = d / "transcript.txt"
    m = dict(meta)
    m["subject"] = subj
    m["output"] = out
    m["status"] = compute_status(meta, out)
    m["status_label"] = STATUS_LABELS[m["status"]]
    m["has_transcript"] = tr_path.exists() and tr_path.stat().st_size > 0
    from . import materials
    m["plan_item"] = materials.plan_item(meta.get("subject_id"), meta.get("date"))
    m["display_title"] = (meta.get("title") or (out["result"].get("title") if out["result"] else "")
                          or (m["plan_item"] or {}).get("title") or "")
    quiz = storage.read_json(d / "output" / "quiz.json", {}) if (d / "output" / "quiz.json").exists() else {}
    m["cards_count"] = len((quiz or {}).get("cards", [])) if isinstance(quiz, dict) else 0
    m["summary"] = out["result"].get("summary", "") if out["result"] else ""
    m["audio_duration"] = sum(f.get("duration") or 0 for f in meta["files"] if f["kind"] == "audio")
    from . import course
    m["checklist"] = course.checklist(m)
    m["help_count"] = len(meta.get("help") or [])
    m["eportal_new"] = meta.get("eportal_new") or []
    if (meta.get("type") or "W") in course.PLAN_TYPES:
        try:
            pi = course.plan_info(meta["id"], meta)
            if not full:
                pi.pop("md", None)
            m["plan"] = pi
        except (KeyError, OSError):
            m["plan"] = None
    if full:
        try:
            m["help"] = course.help_list(meta["id"])
        except Exception:
            m["help"] = []
        m["transcript"] = tr_path.read_text(encoding="utf-8", errors="replace") if m["has_transcript"] else ""
        md = d / "output" / "notes.md"
        m["notes_md"] = md.read_text(encoding="utf-8", errors="replace") if md.exists() else ""
        m["folder"] = str(d)
    return m


def list_all() -> list[dict]:
    items = []
    if not storage.LECTURES_DIR.exists():
        return items
    for d in storage.LECTURES_DIR.iterdir():
        if not d.is_dir():
            continue
        try:
            items.append(enrich(read_meta(d.name)))
        except (KeyError, OSError):
            continue
    items.sort(key=lambda m: (m.get("date") or "", m.get("time") or "", m.get("created_at") or ""), reverse=True)
    return items


def request_claude(lid: str, instructions: str = "") -> dict:
    def fn(meta):
        meta["claude"] = {"requested": True, "requested_at": storage.now_iso(), "instructions": (instructions or "")[:5000]}
    meta = mutate(lid, fn)
    write_queue()
    return meta


def cancel_claude(lid: str) -> dict:
    meta = mutate(lid, lambda m: m.__setitem__("claude", {"requested": False}))
    write_queue()
    return meta


def trash(lid: str) -> None:
    d = lecture_dir(lid)
    shutil.move(str(d), str(storage.TRASH_DIR / storage.trash_dir_name(lid)))
    write_queue()


def list_trash() -> list[dict]:
    out = []
    for d in sorted(storage.TRASH_DIR.iterdir(), reverse=True) if storage.TRASH_DIR.exists() else []:
        if not d.is_dir() or d.name == "_files":
            continue
        meta = storage.read_json(d / "meta.json", {})
        out.append({"trash_id": d.name, "id": meta.get("id"), "date": meta.get("date"), "title": meta.get("title"),
                    "subject_id": meta.get("subject_id")})
    return out


def restore(trash_id: str) -> str:
    src = (storage.TRASH_DIR / trash_id).resolve()
    if storage.TRASH_DIR.resolve() not in src.parents or not src.is_dir():
        raise KeyError(trash_id)
    meta = storage.read_json(src / "meta.json", {})
    lid = meta.get("id") or trash_id.split("__")[0]
    target = storage.LECTURES_DIR / lid
    if target.exists():
        lid = lid + "_r" + uuid.uuid4().hex[:3]
        meta["id"] = lid
        target = storage.LECTURES_DIR / lid
    shutil.move(str(src), str(target))
    if meta:
        storage.write_json(target / "meta.json", meta)
    write_queue()
    return lid


def _eportal_hints(m: dict) -> list[str]:
    """Можливі слайди з ePortalu для цієї лекції (якщо ще не прикріплені) — підказка для Claude."""
    try:
        from . import eportal
        return [f"subjects/{m['subject_id']}/files/{c['file']}" for c in eportal.candidates(m["id"])
                if c["score"] > 0 and not c["attached"]][:4]
    except Exception:
        return []


def _subject_deadlines(sid: str | None) -> list[dict]:
    """Найближчі дедлайни предмета (ePortal + вручну) — щоб Claude міг написати «що здати і до коли»."""
    if not sid:
        return []
    try:
        from . import eportal
        today = datetime.now().strftime("%Y-%m-%d")
        return [{"title": x["title"], "due": x["due"], "what": x.get("what", "")} for x in eportal.list_deadlines()
                if x.get("subject_id") == sid and not x.get("done") and (x.get("due") or "") >= today][:8]
    except Exception:
        return []


_waiting: dict | None = None  # id → requested_at з попереднього запису черги (для журналу «Claude обробив»)


def _log_claude_done(items: list[dict]) -> None:
    global _waiting
    now_wait = {m["id"]: m["claude"].get("requested_at") for m in items if m["status"] == "waiting_claude"}
    if _waiting is not None:
        by_id = {m["id"]: m for m in items}
        for lid, req in _waiting.items():
            m = by_id.get(lid)
            if lid in now_wait or not m or m["status"] != "done":
                continue
            try:
                wait_h = round((datetime.now().astimezone() - datetime.fromisoformat(req)).total_seconds() / 3600, 1)
            except (TypeError, ValueError):
                wait_h = None
            applog.event("claude_done", lecture=lid, type=m.get("type"), subject=m.get("subject_id"), wait_h=wait_h)
            from . import push
            push.notify("done", f"Готово: {m.get('display_title') or (m.get('subject') or {}).get('short', '')}",
                        "Конспект і картки чекають", f"#/lecture/{lid}", tag=f"done-{lid}")
    _waiting = now_wait


_answers_prev: dict | None = None  # 2.3: що чекало на Claude (Допоможи, план, звіт, шпаргалка, залік) — для сповіщень


def _notify_answers(groups: dict) -> None:
    global _answers_prev
    now = {}
    labels = {"help": "відповів у «Допоможи»", "plans": "склав план до заняття", "reports": "перевірив / підготував звіт",
              "exam_prep": "зробив шпаргалку до тесту", "zaliczenie": "склав умови заліку",
              "project_steps": "підготував наступний крок проєкту"}
    for k, items in groups.items():
        for it in items:
            key = f"{k}:{it.get('lecture_id') or it.get('subject_id')}"
            now[key] = (k, it.get("lecture_id"), it.get("subject_id"))
    if _answers_prev is not None:
        from . import push
        for key, (k, lid, sid) in _answers_prev.items():
            if key not in now:
                push.notify("answers", f"Claude {labels[k]}", "", f"#/lecture/{lid}" if lid else
                            f"#/subject/{sid}" + ("?tab=project" if k == "project_steps" else ""), tag=key)
    _answers_prev = now


def write_queue() -> None:
    """data/queue.json — список лекцій, які чекають на обробку Claude."""
    queue = []
    items = list_all()
    _log_claude_done(items)
    from . import course as _course
    if _course.start_deferred_plans(items):  # 2.6: відкладена інструкція — тепер, коли заняття вільне
        items = list_all()
    for m in items:
        if m["status"] == "waiting_claude":
            queue.append({
                "id": m["id"], "folder": f"lectures/{m['id']}",
                "subject": (m.get("subject") or {}).get("name", ""), "type": m.get("type"),
                "date": m.get("date"), "time": m.get("time"), "notes_language": m.get("notes_language"),
                "audio_language": m.get("audio_language"), "has_transcript": m["has_transcript"],
                "requested_at": m["claude"].get("requested_at"), "instructions": m["claude"].get("instructions", ""),
                "eportal_hints": _eportal_hints(m),
                "deadlines": _subject_deadlines(m.get("subject_id")),
                "context": _context(m, items),
                "progress": _progress(m),
            })
    from . import course, materials, project, semester, study
    groups = {"help": course.pending_help(), "plans": course.pending_plans(items), "reports": course.pending_reports(items),
              "exam_prep": semester.pending_exam_preps(), "zaliczenie": semester.pending_setups(),
              "project_steps": project.pending_steps(items)}
    _notify_answers(groups)
    storage.write_json(storage.DATA_DIR / "queue.json", {"updated_at": storage.now_iso(), "lectures": queue,
                                                         "subjects": materials.pending_parses(),
                                                         "explain": study.pending_explains(), **groups})


def _progress(m: dict) -> dict:
    if (m.get("type") or "W") == "W":
        return {}
    from . import course
    return course.progress(enrich(m, full=True))


def _context(m: dict, items: list[dict]) -> dict:
    """Що Claude читає перед обробкою заняття: пам'ять предмета + конспекти викладів цього предмета (а не всі розшифровки)."""
    sid = m.get("subject_id")
    if not sid:
        return {}
    mem = storage.DATA_DIR / "subjects" / sid / "memory.md"
    ws = []
    for x in items:
        if x.get("subject_id") == sid and x.get("type") == "W" and x["id"] != m["id"] \
                and (storage.LECTURES_DIR / x["id"] / "output" / "notes.md").exists() and (x.get("date") or "") <= (m.get("date") or "9999"):
            ws.append({"folder": f"lectures/{x['id']}", "date": x.get("date"), "title": x.get("display_title") or ""})
    ws.sort(key=lambda x: x["date"] or "")
    prev_same = [x for x in items if x.get("subject_id") == sid and x.get("type") == m.get("type") and x["id"] != m["id"]
                 and (x.get("date") or "") <= (m.get("date") or "9999") and x["status"] == "done"]
    prev_same.sort(key=lambda x: x.get("date") or "")
    return {"memory": f"subjects/{sid}/memory.md" if mem.exists() else None, "memory_target": f"subjects/{sid}/memory.md",
            "course_map": f"subjects/{sid}/course_map.json", "lectures_w": ws[-14:],
            "previous_same_type": f"lectures/{prev_same[-1]['id']}" if prev_same else None,
            "plan": f"lectures/{m['id']}/output/plan.md" if (storage.LECTURES_DIR / m["id"] / "output" / "plan.md").exists() else None}


def search(q: str, limit: int = 50) -> list[dict]:
    q = (q or "").strip().lower()
    if len(q) < 2:
        return []
    terms = q.split()
    results = []
    for m in list_all():
        d = storage.LECTURES_DIR / m["id"]
        texts = {
            "Назва": m.get("display_title") or "",
            "Нотатки": m.get("user_notes") or "",
            "Конспект": _read(d / "output" / "notes.md"),
            "Розшифровка": _read(d / "transcript.txt"),
        }
        hits = []
        for label, text in texts.items():
            low = text.lower()
            if all(t in low for t in terms):
                i = low.find(terms[0])
                a, b = max(0, i - 90), min(len(text), i + 160)
                hits.append({"where": label, "snippet": ("…" if a else "") + text[a:b].replace("\n", " ") + ("…" if b < len(text) else "")})
        subj = (m.get("subject") or {}).get("name", "").lower()
        if hits or all(t in subj for t in terms):
            results.append({"lecture": m, "hits": hits})
        if len(results) >= limit:
            break
    return results


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    except OSError:
        return ""


def signature() -> str:
    """Відбиток стану на диску — щоб помічати зміни, зроблені Claude ззовні."""
    h = hashlib.md5()
    if storage.LECTURES_DIR.exists():
        for d in sorted(storage.LECTURES_DIR.iterdir()):
            for p in (d / "meta.json", d / "transcript.txt", d / "output", d / "journal.md"):  # 2.7: журнал чату
                try:
                    st = p.stat()
                    h.update(f"{p}{st.st_mtime_ns}{st.st_size}".encode())
                except OSError:
                    pass
            out = d / "output"
            if out.is_dir():
                for p in out.iterdir():
                    try:
                        st = p.stat()
                        h.update(f"{p}{st.st_mtime_ns}{st.st_size}".encode())
                    except OSError:
                        pass
    sd = storage.DATA_DIR / "subjects"
    if sd.exists():
        for d in sd.iterdir():
            for p in (d / "plan.json", d / "materials.json", d / "files", d / "memory.md", d / "course_map.json",
                      d / "project" / "journal.md", d / "project" / "stages.json", d / "project" / "current"):
                try:
                    st = p.stat()
                    h.update(f"{p}{st.st_mtime_ns}{st.st_size}".encode())
                except OSError:
                    pass
    for name in ("schedule.json", "settings.json", "explain_answers.json", "study_requests.json"):
        try:
            st = (storage.DATA_DIR / name).stat()
            h.update(f"{name}{st.st_mtime_ns}".encode())
        except OSError:
            pass
    return h.hexdigest()
