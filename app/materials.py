"""Матеріали предмета: нотатки/умови заліку, посилання, файли та план тем.

data/subjects/<id>/
    materials.json — нотатки, посилання, список файлів (пише застосунок)
    plan.json      — план тем {items:[{date, title, topics, links}]} (пише застосунок або Claude)
    files/         — силабус, скріншоти з ePortalu тощо
"""
from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from . import storage

SUBJECTS_DIR = storage.DATA_DIR / "subjects"


def _sid(sid: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,24}", sid or ""):
        raise KeyError(sid)
    return sid


def subject_dir(sid: str) -> Path:
    d = SUBJECTS_DIR / _sid(sid)
    (d / "files").mkdir(parents=True, exist_ok=True)
    return d


def _ts(v) -> float:
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return (dt if dt.tzinfo else dt.astimezone()).timestamp()
    except Exception:
        return 0.0


def get(sid: str) -> dict:
    d = subject_dir(sid)
    m = storage.read_json(d / "materials.json", {}) or {}
    plan = storage.read_json(d / "plan.json", {}) or {}
    m.setdefault("notes", "")
    m.setdefault("links", [])
    files = []
    for p in sorted((d / "files").iterdir()):
        if p.is_file() and not p.name.startswith("."):
            st = p.stat()
            files.append({"name": p.name, "size": st.st_size,
                          "added_at": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds")})
    req = m.get("parse_requested_at")
    parse_pending = bool(req) and _ts(plan.get("updated_at")) <= _ts(req)
    return {"subject_id": sid, "notes": m["notes"], "links": m["links"], "files": files,
            "plan": plan.get("items", []), "plan_updated_at": plan.get("updated_at"), "plan_source": plan.get("source"),
            "parse_requested_at": req if parse_pending else None, "parse_pending": parse_pending,
            "parse_instructions": m.get("parse_instructions", "") if parse_pending else ""}


def save(sid: str, notes: str | None = None, links: list | None = None) -> dict:
    d = subject_dir(sid)
    with storage._lock:
        m = storage.read_json(d / "materials.json", {}) or {}
        if notes is not None:
            m["notes"] = str(notes)[:50000]
        if links is not None:
            clean = []
            for l in links[:200]:
                url = str(l.get("url") or "").strip()
                if not url:
                    continue
                if not re.match(r"^[a-z]+://", url):
                    url = "https://" + url
                clean.append({"title": str(l.get("title") or "").strip()[:200], "url": url[:2000]})
            m["links"] = clean
        m["updated_at"] = storage.now_iso()
        storage.write_json(d / "materials.json", m)
    return get(sid)


def save_plan(sid: str, items: list) -> dict:
    d = subject_dir(sid)
    clean = []
    for it in items[:300]:
        title = str(it.get("title") or "").strip()
        dt = str(it.get("date") or "").strip()
        if not title and not dt:
            continue
        topics = it.get("topics") or []
        if isinstance(topics, str):
            topics = [t.strip(" -•\t") for t in topics.splitlines() if t.strip(" -•\t")]
        clean.append({"date": dt[:10], "title": title[:300], "topics": [str(t)[:300] for t in topics][:50],
                      "links": it.get("links") or []})
    clean.sort(key=lambda x: (x["date"] or "9999", x["title"]))
    storage.write_json(d / "plan.json", {"updated_at": storage.now_iso(), "source": "user", "items": clean})
    return get(sid)


def request_parse(sid: str, instructions: str = "") -> dict:
    d = subject_dir(sid)
    with storage._lock:
        m = storage.read_json(d / "materials.json", {}) or {}
        m["parse_requested_at"] = storage.now_iso()
        m["parse_instructions"] = str(instructions or "")[:3000]
        storage.write_json(d / "materials.json", m)
    return get(sid)


def cancel_parse(sid: str) -> dict:
    d = subject_dir(sid)
    with storage._lock:
        m = storage.read_json(d / "materials.json", {}) or {}
        m.pop("parse_requested_at", None)
        storage.write_json(d / "materials.json", m)
    return get(sid)


async def save_file(sid: str, upload) -> dict:
    d = subject_dir(sid) / "files"
    name = storage.safe_filename(upload.filename)
    tmp = storage.TMP_DIR / f"{uuid.uuid4().hex}.part"
    size = 0
    try:
        with open(tmp, "wb") as f:
            while chunk := await upload.read(1024 * 1024):
                f.write(chunk)
                size += len(chunk)
        if not size:
            raise ValueError("Порожній файл")
        target = storage.unique_path(d, name)
        shutil.move(str(tmp), str(target))
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return get(sid)


def file_path(sid: str, name: str) -> Path:
    d = (subject_dir(sid) / "files").resolve()
    p = (d / name).resolve()
    if d not in p.parents or not p.is_file():
        raise KeyError(name)
    return p


def delete_file(sid: str, name: str) -> dict:
    p = file_path(sid, name)
    trash = storage.TRASH_DIR / "_files" / f"subject_{sid}"
    trash.mkdir(parents=True, exist_ok=True)
    dst = storage.unique_path(trash, p.name)
    shutil.move(str(p), str(dst))
    storage.touch(dst)
    return get(sid)


def plan_item(sid: str, date_s: str) -> dict | None:
    if not sid or not date_s:
        return None
    try:
        plan = storage.read_json(SUBJECTS_DIR / _sid(sid) / "plan.json", {}) or {}
    except KeyError:
        return None
    for it in plan.get("items", []):
        if it.get("date") == date_s:
            return it
    return None


def pending_parses() -> list[dict]:
    out = []
    if not SUBJECTS_DIR.exists():
        return out
    for d in SUBJECTS_DIR.iterdir():
        if d.is_dir():
            try:
                g = get(d.name)
            except KeyError:
                continue
            if g["parse_pending"]:
                out.append({"subject_id": d.name, "folder": f"subjects/{d.name}", "requested_at": g["parse_requested_at"],
                            "instructions": g["parse_instructions"], "files": [f["name"] for f in g["files"]],
                            "links": g["links"]})
    return out
