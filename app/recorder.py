"""Запис лекції прямо в застосунку (телефон через Tailscale або ПК).

Браузер записує MediaRecorder-ом і кожні ~5 с надсилає шматок (chunk) з номером.
Шматки дописуються в один файл audio/<name>.webm|.m4a — так запис не губиться,
навіть якщо телефон втратить мережу чи сторінку закриють: незавантажені шматки
лежать у браузері (IndexedDB) і досилаються пізніше.
Кожен новий старт (після перезавантаження/паузи) — окремий файл-частина тієї ж лекції.
"""
from __future__ import annotations

import hashlib
import os
import time
import uuid
from datetime import datetime

from . import applog, lectures, storage

EXT_BY_MIME = {"webm": ".webm", "ogg": ".ogg", "mp4": ".m4a", "mpeg": ".mp3", "aac": ".aac", "wav": ".wav"}
STALE_AFTER = 3 * 3600  # без жодного шматка 3 год — завершуємо автоматично


def _ext(mime: str) -> str:
    m = (mime or "").lower()
    for k, v in EXT_BY_MIME.items():
        if k in m:
            return v
    return ".webm"


def _sessions(meta: dict) -> dict:
    return meta.setdefault("recording", {}).setdefault("sessions", {})


def start(data: dict) -> dict:
    """Новий запис (нова лекція) або нова частина вже існуючої лекції (lecture_id)."""
    from .schedule import detect
    now = datetime.now()
    lid = data.get("lecture_id")
    if lid:
        meta = lectures.read_meta(lid)
    else:
        info = {k: data.get(k) for k in ("subject_id", "type", "notes_language", "audio_language", "title", "user_notes")}
        info["date"] = now.strftime("%Y-%m-%d")
        info["time"] = now.strftime("%H:%M")
        if not info.get("subject_id"):
            cands = detect(now, None, prefer_type=data.get("type") or "W")
            if cands and cands[0]["confidence"] >= 0.5:
                c = cands[0]
                info["subject_id"], info["type"], info["time"] = c["subject_id"], c["type"], c["start"]
        meta = lectures.create(info)
        lid = meta["id"]
    sid = uuid.uuid4().hex[:10]
    part = len(_sessions(meta)) + 1
    name = f"zapys_{now.strftime('%Y-%m-%d_%H%M')}" + (f"_cz{part}" if part > 1 else "") + _ext(data.get("mime", ""))
    target = storage.unique_path(storage.LECTURES_DIR / lid / "audio", name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch()

    def fn(m):
        rec = m.setdefault("recording", {})
        rec["state"] = "recording"
        rec.setdefault("sessions", {})[sid] = {"file": target.name, "mime": data.get("mime", ""),
                                                "started_at": storage.now_iso(), "state": "recording"}
    meta = lectures.mutate(lid, fn)
    storage.write_json(_prog_path(lid, sid), {"seq": -1, "bytes": 0, "last_at": time.time()})
    try:
        from . import eportal
        eportal.auto_attach(lid)
    except Exception as e:
        applog.error("auto_attach", e)
    return {"lecture": lectures.enrich(lectures.read_meta(lid)), "session": sid, "file": target.name}


def _prog_path(lid: str, sid: str):
    return storage.LECTURES_DIR / lid / f".rec_{sid}.json"


def _progress(lid: str, sid: str) -> dict:
    return storage.read_json(_prog_path(lid, sid), {}) or {"seq": -1, "bytes": 0, "last_at": time.time()}


def chunk(lid: str, sid: str, seq: int, data: bytes, force: bool = False) -> dict:
    """Ідемпотентне дописування. Повертає очікуваний наступний номер.
    Прогрес — в окремому .rec_<sid>.json, щоб не переписувати meta.json кожні 5 с."""
    with storage._lock:
        meta = lectures.read_meta(lid)
        s = _sessions(meta).get(sid)
        if not s:
            raise KeyError(sid)
        pr = _progress(lid, sid)
        if seq <= pr["seq"]:
            return {"ok": True, "next": pr["seq"] + 1, "dup": True}
        if seq != pr["seq"] + 1 and not force:
            return {"ok": False, "next": pr["seq"] + 1}
        p = storage.LECTURES_DIR / lid / "audio" / s["file"]
        with open(p, "ab") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        pr = {"seq": seq, "bytes": pr["bytes"] + len(data), "last_at": time.time()}
        storage.write_json(_prog_path(lid, sid), pr)
        return {"ok": True, "next": seq + 1, "bytes": pr["bytes"]}


def finish(lid: str, sid: str | None = None, duration: float | None = None, auto: bool = False) -> dict:
    from . import transcriber
    from .schedule import load_settings
    meta = lectures.read_meta(lid)
    sess = _sessions(meta)
    targets = [sid] if sid else [k for k, v in sess.items() if v.get("state") == "recording"]
    for k in targets:
        s = sess.get(k)
        if not s or s.get("state") == "done":
            continue
        p = storage.LECTURES_DIR / lid / "audio" / s["file"]

        def fn(m, k=k, s=s, p=p):
            ss = _sessions(m)[k]
            ss["state"] = "done"
            ss["finished_at"] = storage.now_iso()
            if p.exists() and p.stat().st_size > 0:
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for b in iter(lambda: f.read(1024 * 1024), b""):
                        h.update(b)
                entry = {"name": p.name, "kind": "audio", "size": p.stat().st_size, "sha256": h.hexdigest(),
                         "added_at": storage.now_iso(), "source": "recorder"}
                if duration and k == sid:
                    entry["duration"] = round(float(duration), 1)
                m["files"] = [f for f in m["files"] if f.get("name") != p.name] + [entry]
            elif p.exists():
                p.unlink()  # порожній запис
            if all(v.get("state") == "done" for v in _sessions(m).values()):
                m["recording"]["state"] = "done"
        lectures.mutate(lid, fn)
    meta = lectures.read_meta(lid)
    if meta.get("recording", {}).get("state") == "done" and any(f["kind"] == "audio" for f in meta["files"]):
        st = load_settings()
        if st.get("auto_transcribe") and transcriber.available():
            transcriber.enqueue(lid)
        if st.get("auto_request_claude") and not meta.get("claude", {}).get("requested"):
            lectures.request_claude(lid, "Автоматично після запису в застосунку" if auto else "")
    return lectures.enrich(lectures.read_meta(lid))


def finish_stale() -> int:
    """Сканер: завершує записи, до яких давно не приходили шматки (телефон розрядився тощо)."""
    n = 0
    if not storage.LECTURES_DIR.exists():
        return 0
    for d in storage.LECTURES_DIR.iterdir():
        meta = storage.read_json(d / "meta.json")
        if not isinstance(meta, dict) or meta.get("recording", {}).get("state") != "recording":
            continue
        sess = meta["recording"].get("sessions", {})
        last = max((_progress(d.name, k).get("last_at") or 0 for k in sess), default=0)
        if time.time() - last > STALE_AFTER:
            try:
                finish(d.name, auto=True)
                n += 1
            except Exception as e:
                applog.error("finish_stale", e)
    return n


def mark(lid: str, t: float) -> dict:
    """«⭐ Важливо» під час запису: позначка часу (від початку поточної частини)."""
    def fn(m):
        marks = m.setdefault("marks", [])
        part = len(m.get("recording", {}).get("sessions", {}))
        marks.append({"t": round(float(t)), "part": part, "at": storage.now_iso()})
        line = f"⭐ Важливо: {int(t) // 60}:{int(t) % 60:02d}" + (f" (частина {part})" if part > 1 else "")
        m["user_notes"] = ((m.get("user_notes") or "").rstrip() + "\n" + line).strip()
    return lectures.mutate(lid, fn)
