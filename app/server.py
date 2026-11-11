"""Конспект — локальний вебзастосунок для лекцій.

Запуск:  python -m app.server [--lan] [--port 8765] [--no-browser]
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import urllib.request
import webbrowser
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import applog, chat, compact, share, course, eportal, project, push, semester, lectures, materials, planner, recorder, remote, schedule, storage, study, transcriber, usos, video

VERSION = "2.9.0"
# Бета: окрема копія даних (KONSPEKT_DATA), без синхронізацій, стиснення і Tailscale — реальні дані не чіпаються
BETA = os.environ.get("KONSPEKT_BETA") == "1"
if BETA:
    VERSION += "-beta"
mimetypes.add_type("application/manifest+json", ".webmanifest")
STATIC = storage.APP_DIR / "static"
_state = {"rev": 1, "sig": "", "port": int(os.environ.get("KONSPEKT_PORT", 8765))}


def bump() -> None:
    _state["rev"] += 1


def _scanner() -> None:
    """Раз на 3 с перевіряє диск: якщо Claude поклав PDF — інтерфейс оновиться сам."""
    last_backup_check = 0.0
    last_sync_check = time.time() - 50
    while True:
        try:
            if eportal.check_inbox():
                bump()
            if not BETA and time.time() - last_sync_check > 60:
                last_sync_check = time.time()
                if usos.due():
                    usos.sync_async()
                if eportal.due():
                    eportal.sync_async()
                elif eportal.deadlines_due():
                    eportal.refresh_deadlines()
                if recorder.finish_stale():
                    bump()
                try:
                    push.daily()  # 2.3: нагадування про завтрашні лаби, дедлайни, картки
                except Exception as e:
                    applog.error("push daily", e)
            sig = lectures.signature() + "|" + ",".join(
                str(int(f.stat().st_mtime_ns)) if f.exists() else "-"
                for f in (usos.USOS_FILE, eportal.EP_FILE, storage.DATA_DIR / "schedule.json"))
            if sig != _state["sig"]:
                if _state["sig"]:
                    lectures.write_queue()
                _state["sig"] = sig
                bump()
            if time.time() - last_backup_check > 3600:
                last_backup_check = time.time()
                storage.backup_if_needed()
                if not BETA:
                    compact.run_async()  # стиснення аудіо/фото, однакові файли, старий кошик
        except Exception as e:  # сканер не повинен падати ніколи
            applog.error("scanner", e)
        time.sleep(3)


def startup() -> None:
    storage.ensure_dirs()
    try:
        moved = storage.migrate_secrets()
        if moved:
            applog.info("startup", "секрети перенесено в secrets/:", ", ".join(moved))
    except OSError as e:
        applog.error("migrate_secrets", e)
    storage.cleanup_tmp()
    schedule.load_settings()
    schedule.load_schedule()
    src = storage.APP_DIR / "CLAUDE.md"
    if src.exists():
        shutil.copyfile(src, storage.DATA_DIR / "CLAUDE.md")
    if (storage.APP_DIR / "protocol").is_dir():  # 2.5: розділи протоколу, які Claude читає лише за потреби
        shutil.copytree(storage.APP_DIR / "protocol", storage.DATA_DIR / "protocol", dirs_exist_ok=True)
    try:
        made = project.ensure_projects()  # 2.6: «Проєкт» у кожному предметі з проєктом
        if made:
            applog.info("startup", "створено проєкти:", ", ".join(made))
    except Exception as e:
        applog.error("ensure_projects", e)
    lectures.write_queue()
    try:
        (storage.DATA_DIR / ".port").write_text(str(_state["port"]))
    except OSError:
        pass
    storage.backup_if_needed()
    compact.load_last()
    try:
        nd = video.cleanup_processed()
        if nd:
            applog.info("startup", f"Видалено оброблених відео: {nd} (аудіо й кадри збережено)")
    except Exception as e:
        applog.error("video cleanup", e)
    try:
        nv = video.resume_pending()
        if nv:
            applog.info("startup", f"Відновлено обробку відео: {nv}")
    except Exception as e:
        applog.error("video resume", e)
    n = transcriber.resume_pending()
    if n:
        applog.info("startup", f"Відновлено незавершених розшифровок: {n}")
    threading.Thread(target=_scanner, daemon=True, name="scanner").start()


def _quiet_conn_reset() -> None:
    """Windows: браузер/телефон рве з'єднання → asyncio друкує страшний, але нешкідливий WinError 10054. Ховаємо його."""
    import asyncio
    loop = asyncio.get_running_loop()
    prev = loop.get_exception_handler()

    def handler(lp, ctx):
        exc = ctx.get("exception")
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        prev(lp, ctx) if prev else lp.default_exception_handler(ctx)

    loop.set_exception_handler(handler)


@asynccontextmanager
async def lifespan(app):
    _quiet_conn_reset()
    startup()
    yield


app = FastAPI(title="Конспект", version=VERSION, lifespan=lifespan)


@app.middleware("http")
async def _same_origin(request: Request, call_next):
    """Захист від сторонніх сайтів, які могли б надсилати запити до локального сервера."""
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin.split("://", 1)[0] in ("http", "https"):  # «Команди» iPhone шлють без Origin або «null»
            o_host = origin.split("://", 1)[-1].rstrip("/")
            h = request.headers
            allowed = {h.get("host", ""), h.get("x-forwarded-host", "")}
            via_tailscale = bool(h.get("tailscale-user-login") or h.get("x-forwarded-for"))
            if o_host not in allowed and not (via_tailscale and o_host.endswith(".ts.net")):
                return JSONResponse({"detail": "Заборонено (інше джерело запиту)"}, status_code=403)
    return await call_next(request)


@app.exception_handler(KeyError)
async def _keyerr(request: Request, exc: KeyError):
    return JSONResponse({"detail": "Не знайдено"}, status_code=404)


@app.exception_handler(Exception)
async def _err(request: Request, exc: Exception):
    applog.error("http", request.url.path, repr(exc))
    return JSONResponse({"detail": f"Внутрішня помилка: {exc}"}, status_code=500)


def _no_beta(what: str) -> None:
    if BETA:
        raise HTTPException(400, f"У беті {what} вимкнено — бета працює на копії даних без ключів доступу")


# ---------------------------------------------------------------- general
@app.get("/api/ping")
def ping():
    return {"ok": True, "app": "konspekt", "version": VERSION}


@app.get("/api/rev")
def rev():
    return {"rev": _state["rev"]}


def _is_remote(request: Request) -> bool:
    h = request.headers
    host = request.client.host if request.client else "127.0.0.1"
    return bool(h.get("tailscale-user-login") or h.get("x-forwarded-for")) or host not in ("127.0.0.1", "::1", "localhost")


@app.get("/api/state")
def state(request: Request):
    s = schedule.load_settings()
    items = lectures.list_all()
    counts = {k: 0 for k in lectures.STATUS_LABELS}
    for m in items:
        counts[m["status"]] += 1
    today = date.today()
    return {
        "rev": _state["rev"], "version": VERSION, "beta": BETA, "settings": s, "remote_client": _is_remote(request),
        "week": schedule.week_info(today, s), "today": today.isoformat(),
        "counts": counts, "total": len(items),
        "waiting_since": min((m["claude"].get("requested_at") for m in items
                              if m["status"] == "waiting_claude" and m["claude"].get("requested_at")), default=None),
        "subjects_waiting": len(materials.pending_parses()),
        "help_waiting": sum(len(x["questions"]) for x in course.pending_help()),
        "plans_waiting": len(course.pending_plans(items)),
        "explain_waiting": len(study.pending_explains()),
        "reports_waiting": len(course.pending_reports(items)) + len(semester.pending_exam_preps()) + len(project.pending_steps(items)),
        "todo_open": course.open_soon(),
        "study": study.stats()["total"],
        "whisper": transcriber.status(),
        "data_dir": str(storage.DATA_DIR),
        "langs": lectures.LANGS, "types": schedule.TYPES, "status_labels": lectures.STATUS_LABELS,
    }


@app.get("/api/disk")
def disk():
    return storage.disk_usage()


# ---------------------------------------------------------------- сховище (стиснення, кошик)
@app.get("/api/storage")
def storage_report():
    return compact.report()


@app.post("/api/storage/compact")
def storage_compact():
    return {"started": compact.run_async(force=True)}


@app.post("/api/storage/empty-trash")
def storage_empty_trash():
    freed = compact.purge_trash(0)
    bump()
    return {"freed": freed}


# ---------------------------------------------------------------- schedule & settings
@app.get("/api/schedule")
def get_schedule():
    return schedule.load_schedule()


@app.put("/api/schedule")
async def put_schedule(request: Request):
    data = await request.json()
    out = schedule.save_schedule(data)
    bump()
    return out


@app.post("/api/schedule/reset")
def reset_schedule():
    storage.make_backup("before-reset")
    out = schedule.save_schedule(schedule.default_schedule())
    bump()
    return out


@app.get("/api/settings")
def get_settings():
    return schedule.load_settings()


@app.put("/api/settings")
async def put_settings(request: Request):
    out = schedule.save_settings(await request.json())
    bump()
    return out


@app.get("/api/week")
def week(start: str | None = None):
    """Розклад на тиждень з урахуванням парності (start = будь-який день тижня)."""
    d = date.fromisoformat(start) if start else date.today()
    monday = d - timedelta(days=d.weekday())
    sched = schedule.load_schedule()
    sets = schedule.load_settings()
    days = []
    for i in range(7):
        dd = monday + timedelta(days=i)
        days.append({"date": dd.isoformat(), "classes": schedule.classes_on(dd, sched, sets)})
    return {"monday": monday.isoformat(), "week": schedule.week_info(monday, sets), "days": days}


@app.post("/api/detect")
async def detect(request: Request):
    """Визначає дату/час і предмет за назвою файлу, часом зміни файлу та тривалістю."""
    body = await request.json()
    names = body.get("filenames") or []
    last_modified = body.get("last_modified")  # ms, з браузера (зазвичай = кінець запису)
    duration = body.get("duration")  # секунди
    manual_date, manual_time = body.get("date"), body.get("time")
    hint = schedule.subject_from_filenames(names)

    def as_cand(c, conf, d=None):
        subj = c.get("subject") if isinstance(c.get("subject"), dict) else next(
            (s for s in schedule.load_schedule()["subjects"] if s["id"] == c["subject_id"]), {})
        return {"class_id": c.get("class_id") or c.get("id"), "subject_id": c["subject_id"], "subject": subj.get("name", ""),
                "short": subj.get("short", ""), "color": subj.get("color", "#999"), "type": c["type"],
                "start": c["start"], "end": c["end"], "room": c.get("room", ""), "parity": c.get("parity", "all"),
                "confidence": conf, "date": d}

    # Лише слайди / фото (без аудіо): час файлу нічого не каже про заняття —
    # беремо предмет із назви файлу та його останнє заняття за розкладом.
    if body.get("materials_only") and not manual_date:
        now = datetime.now()
        cands, ref_date, src = [], None, None
        if hint:
            lc = schedule.last_class(hint["subject_id"], now)
            if lc:
                cands = [as_cand(lc, hint["confidence"], lc["date"])]
                ref_date, src = lc["date"], "filename_subject"
        if not cands:
            for back in range(7):
                d = (now - timedelta(days=back)).date()
                day = [c for c in schedule.classes_on(d) if back or schedule._mins(c["start"]) <= now.hour * 60 + now.minute + 30]
                if day:
                    day.sort(key=lambda c: (-schedule._mins(c["start"])))
                    cands = [as_cand(c, 0.5 if c["type"] == "W" else 0.35, d.isoformat()) for c in day]
                    if hint:
                        cands = [c for c in cands if c["subject_id"] == hint["subject_id"]] or cands
                    ref_date, src = d.isoformat(), "recent"
                    break
        return {"source": src, "date": ref_date, "time": cands[0]["start"] if cands else None,
                "class_time": cands[0]["start"] if cands else None, "candidates": cands, "subject_hint": hint,
                "week": schedule.week_info(date.fromisoformat(ref_date)) if ref_date else None}

    start = end = None
    source = None
    day_only = None
    if manual_date:
        try:
            if manual_time:
                start = datetime.fromisoformat(f"{manual_date}T{manual_time}")
                if duration:
                    end = start + timedelta(seconds=float(duration))
            else:
                day_only = date.fromisoformat(manual_date)
            source = "manual"
        except ValueError:
            start, day_only = None, None
    if not source:
        for n in names:
            dt, has_time = schedule.datetime_from_filename(n)
            if dt and has_time:
                start, source = dt, "filename"
                if duration:
                    end = start + timedelta(seconds=float(duration))
                break
            if dt and not day_only:
                day_only = dt.date()
    if not source and last_modified:
        try:
            end = datetime.fromtimestamp(float(last_modified) / 1000)
            source = "file_time"
            if duration:
                start = end - timedelta(seconds=float(duration))
        except (ValueError, OSError, OverflowError):
            end = None
    if start or end:
        ref = start or end
        # якщо відомий лише один момент, припускаємо типову тривалість заняття (90 хв)
        a = start or (end - timedelta(minutes=90))
        b = end or (start + timedelta(minutes=90))
        if (b - a) < timedelta(minutes=15):  # дуже короткий запис — тривалість ненадійна
            if source == "file_time":
                a = b - timedelta(minutes=90)
            else:
                b = a + timedelta(minutes=90)
        cands = schedule.detect(a, b)
    elif day_only:
        ref = datetime.combine(day_only, datetime.min.time())
        source = source or "filename"
        cands = [{"class_id": c["id"], "subject_id": c["subject_id"], "subject": c["subject"]["name"],
                  "short": c["subject"]["short"], "color": c["subject"]["color"], "type": c["type"],
                  "start": c["start"], "end": c["end"], "room": c["room"], "parity": c["parity"],
                  "confidence": 0.5 if c["type"] == "W" else 0.3}
                 for c in schedule.classes_on(day_only)]
        cands.sort(key=lambda x: -x["confidence"])
    else:
        cands, ref = [], None
    if hint and cands:
        for c in cands:
            if c["subject_id"] == hint["subject_id"]:
                c["confidence"] = round(min(1.0, c["confidence"] + 0.3), 2)
        cands.sort(key=lambda x: -x["confidence"])
    return {
        "subject_hint": hint,
        "source": source,
        "date": ref.date().isoformat() if ref else None,
        "time": (start or end).strftime("%H:%M") if (start or end) else (cands[0]["start"] if cands else None),
        "class_time": cands[0]["start"] if cands else None,
        "candidates": cands,
        "week": schedule.week_info(ref.date()) if ref else None,
    }


# ---------------------------------------------------------------- lectures
@app.get("/api/lectures")
def list_lectures(subject: str | None = None, status: str | None = None):
    items = lectures.list_all()
    if subject:
        items = [m for m in items if m.get("subject_id") == subject]
    if status:
        items = [m for m in items if m["status"] == status]
    return items


@app.post("/api/lectures")
async def create_lecture(request: Request):
    meta = lectures.create(await request.json())
    try:
        eportal.auto_attach(meta["id"])
    except Exception as e:
        applog.error("auto_attach", e)
    bump()
    return lectures.enrich(lectures.read_meta(meta["id"]))


@app.get("/api/lectures/{lid}")
def get_lecture(lid: str):
    m = lectures.enrich(lectures.read_meta(lid), full=True)
    m["schedule_check"] = schedule.schedule_check(m.get("subject_id"), m.get("type"), m.get("date"), m.get("time"))
    if m.get("schedule_ok") and m["schedule_ok"] == lectures.schedule_sig(m):
        m["schedule_check"] = {"status": "ok", "confirmed": True}
    m["report"] = course.report_info(lid, m)
    m["project_meeting"] = project.is_project_meeting(m)  # 2.4: файли й кроки — на сторінці предмета
    if m.get("type") in course.PLAN_TYPES and not m["project_meeting"]:
        m["chat"] = chat.lecture_info(lid)  # 2.7: «Робота в чаті»
    return m


@app.patch("/api/lectures/{lid}")
async def patch_lecture(lid: str, request: Request):
    meta = lectures.update(lid, await request.json())
    lectures.write_queue()
    bump()
    return lectures.enrich(meta, full=True)


@app.delete("/api/lectures/{lid}")
def delete_lecture(lid: str):
    transcriber.cancel(lid)
    lectures.trash(lid)
    bump()
    return {"ok": True}


@app.post("/api/lectures/{lid}/files")
async def upload_file(lid: str, file: UploadFile = File(...), duration: str | None = Form(None), kind: str | None = Form(None)):
    lectures.read_meta(lid)
    free = shutil.disk_usage(storage.DATA_DIR).free
    if free < 200 * 1024 * 1024:
        raise HTTPException(507, "Мало місця на диску (менше 200 МБ)")
    try:
        res = await lectures.save_upload(lid, file, float(duration) if duration else None, kind=kind)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if kind == "task" and not res.get("already_here"):
        try:
            course.on_task_added(lid)  # 2.1: умова завдання → план у черзі Claude
        except Exception as e:
            applog.error("plan", e)
    if kind in ("task", "code"):
        lectures.write_queue()
    if res.get("file", {}).get("kind") == "video" and not res.get("already_here"):
        video.enqueue(lid, res["file"]["name"])
    bump()
    return res


@app.get("/api/lectures/{lid}/files/{kind}/{name}")
def get_file(lid: str, kind: str, name: str, download: int = 0):
    p = lectures.file_path(lid, kind, name)
    return FileResponse(p, filename=p.name if download else None,
                        content_disposition_type="attachment" if download else "inline")


@app.delete("/api/lectures/{lid}/files/{kind}/{name}")
def del_file(lid: str, kind: str, name: str):
    meta = lectures.delete_file(lid, kind, name)
    bump()
    return lectures.enrich(meta, full=True)


@app.get("/api/lectures/{lid}/output/{name:path}")
def get_output(lid: str, name: str, download: int = 0):
    d = lectures.lecture_dir(lid) / "output"
    p = (d / name).resolve()
    if d.resolve() not in p.parents or not p.is_file():
        raise HTTPException(404, "Файл не знайдено")
    return FileResponse(p, filename=p.name if download else None,
                        content_disposition_type="attachment" if download else "inline",
                        headers={"Cache-Control": "no-store"})


@app.put("/api/lectures/{lid}/transcript")
async def put_transcript(lid: str, request: Request):
    body = await request.json()
    d = lectures.lecture_dir(lid)
    text = str(body.get("text") or "")
    if text.strip():
        tmp = d / ".transcript.txt.tmp"
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, d / "transcript.txt")
    elif (d / "transcript.txt").exists():
        (d / "transcript.txt").unlink()
    lectures.mutate(lid, lambda m: m.__setitem__("transcribe", {"state": "done" if text.strip() else "none",
                                                                 "source": "manual", "updated_at": storage.now_iso()}))
    lectures.write_queue()
    bump()
    return {"ok": True}


@app.post("/api/lectures/{lid}/transcribe")
def start_transcribe(lid: str):
    if not transcriber.available():
        raise HTTPException(400, "Локальна розшифровка не встановлена. Відкрийте Налаштування → Розшифровка.")
    meta = lectures.read_meta(lid)
    if video.busy(meta):
        # аудіо ще витягується з відео — розшифровка почнеться сама одразу після цього
        meta = lectures.mutate(lid, lambda m: m.__setitem__("transcribe_after_video", True))
        bump()
        return lectures.enrich(meta)
    meta = transcriber.enqueue(lid)
    bump()
    return lectures.enrich(meta)


@app.post("/api/lectures/{lid}/video/{name}/process")
def video_reprocess(lid: str, name: str):
    lectures.file_path(lid, "video", name)
    video.enqueue(lid, name)
    bump()
    return lectures.enrich(lectures.read_meta(lid), full=True)


@app.post("/api/lectures/{lid}/transcribe/cancel")
def cancel_transcribe(lid: str):
    meta = transcriber.cancel(lid)
    bump()
    return lectures.enrich(meta)


@app.post("/api/lectures/{lid}/claude")
async def req_claude(lid: str, request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    try:
        course.busy_error(lectures.read_meta(lid))  # 2.6: один запит за раз для лаб/проєктів
    except ValueError as e:
        raise HTTPException(409, str(e))
    meta = lectures.request_claude(lid, body.get("instructions", ""))
    bump()
    return lectures.enrich(meta)


@app.delete("/api/lectures/{lid}/claude")
def cancel_claude(lid: str):
    meta = lectures.cancel_claude(lid)
    bump()
    return lectures.enrich(meta)


# ---------------------------------------------------------------- quick upload (iPhone «Команди» / Диктофон)
def _media_info(p) -> tuple[float, datetime | None]:
    """Тривалість і час запису з метаданих файлу (Диктофон iPhone пише creation_time)."""
    try:
        import av
        with av.open(str(p)) as c:
            dur = float(c.duration / 1_000_000) if c.duration else 0.0
            ct = (c.metadata or {}).get("creation_time") or (c.metadata or {}).get("date")
            t = None
            if ct:
                try:
                    t = datetime.fromisoformat(ct.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
                except ValueError:
                    t = None
            return dur, t
    except Exception:
        return 0.0, None


QUICK_LOG = storage.DATA_DIR / "quick_log.json"
_CT_EXT = {"audio/x-m4a": ".m4a", "audio/m4a": ".m4a", "audio/mp4": ".m4a", "audio/aac": ".aac", "audio/mpeg": ".mp3",
           "audio/mp3": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/ogg": ".ogg", "audio/webm": ".webm",
           "audio/x-caf": ".caf", "video/quicktime": ".mov", "video/mp4": ".mp4", "video/x-m4v": ".m4v"}


def _quick_log(**kw) -> None:
    try:
        log = storage.read_json(QUICK_LOG, []) or []
        log.insert(0, {"at": storage.now_iso(), **kw})
        storage.write_json(QUICK_LOG, log[:25])
    except Exception as e:  # noqa: BLE001
        applog.error("quick log", e)


class _SpooledUpload:
    """Сирий файл із тіла запиту (у «Командах»: Тіло запиту → Файл), уже збережений на диск."""

    def __init__(self, path, filename: str):
        self.filename = filename
        self._f = open(path, "rb")

    async def read(self, n: int = -1) -> bytes:
        b = self._f.read(n)
        if not b:
            self._f.close()
        return b


@app.get("/api/quick-upload", response_class=PlainTextResponse)
def quick_upload_check():
    """Перевірка зв'язку: відкрийте адресу в Safari на iPhone або запустіть команду без файлу."""
    return f"✓ Конспект {VERSION} на зв'язку. Надсилайте запис методом POST (тіло — файл)."


@app.get("/api/quick-upload/log")
def quick_upload_log():
    return storage.read_json(QUICK_LOG, []) or []


@app.post("/api/quick-upload", response_class=PlainTextResponse)
async def quick_upload(request: Request, name: str | None = None, created: str | None = None,
                       duration: str | None = None, notes_language: str | None = None):
    """Один запит — одна лекція: файл → предмет за розкладом → розшифровка → черга Claude.
    Приймає і форму (multipart, будь-яка назва поля з файлом), і «сирий» файл у тілі запиту.
    Відповідь — короткий текст для сповіщення на телефоні; кожна спроба пишеться в quick_log.json."""
    h = request.headers
    ct = (h.get("content-type") or "").split(";")[0].strip().lower()
    info = {"ip": request.client.host if request.client else "", "type": ct or "—",
            "declared": int(h.get("content-length") or 0), "agent": (h.get("user-agent") or "")[:80]}
    tmp = None
    try:
        if ct.startswith("multipart/"):
            try:
                form = await request.form(max_part_size=50 * 1024 * 1024)
            except TypeError:  # старіша Starlette
                form = await request.form()
            up = next((v for v in form.values() if not isinstance(v, str) and hasattr(v, "read")), None)
            txt = {k: v for k, v in form.items() if isinstance(v, str)}
            created = created or txt.get("created")
            duration = duration or txt.get("duration")
            notes_language = notes_language or txt.get("notes_language")
            if up is None:
                raise HTTPException(400, "у формі немає файлу (є лише текстові поля: " + (", ".join(txt) or "—") +
                                    "). У полі «file» оберіть тип «Файл» і значення «Вхідні дані Команди».")
            info["bytes"] = getattr(up, "size", None)
            upload = up
        else:
            storage.TMP_DIR.mkdir(parents=True, exist_ok=True)
            tmp = storage.TMP_DIR / f"quick_{int(time.time() * 1000)}.part"
            size = 0
            info["raw"] = True
            try:
                with open(tmp, "wb") as f:
                    async for chunk in request.stream():
                        size += len(chunk)
                        f.write(chunk)
            except Exception:  # noqa: BLE001 — телефон обірвав з'єднання (тайм-аут «Команд», зник інтернет)
                info["bytes"] = size
                raise HTTPException(400, f"передача обірвалась ({size // 1048576} з {info['declared'] // 1048576} МБ)")
            info["bytes"] = size
            if size < 2000:
                head = tmp.read_bytes()[:120].decode("utf-8", "replace").strip()
                raise HTTPException(400, f"отримано не аудіо, а {size} байт" + (f" («{head[:60]}»)" if head else "") +
                                    ". Тіло запиту має бути «Файл» → «Вхідні дані Команди».")
            disp = h.get("content-disposition") or ""
            fname = name or h.get("x-filename") or (disp.split("filename=", 1)[1].strip('"; ') if "filename=" in disp else "")
            fname = os.path.basename(fname or "") or "Zapys"
            if not os.path.splitext(fname)[1]:
                fname += _CT_EXT.get(ct, ".m4a")
            upload = _SpooledUpload(tmp, fname)
        msg = await quick_core(upload, created, duration, notes_language)
        _quick_log(ok=True, result=msg, name=getattr(upload, "filename", ""), **info)
        return msg
    except HTTPException as e:
        _quick_log(ok=False, result=str(e.detail), **info)
        return PlainTextResponse(f"✗ Конспект: {e.detail}", status_code=e.status_code)
    except Exception as e:  # noqa: BLE001
        _quick_log(ok=False, result=f"{type(e).__name__}: {e}"[:300], **info)
        applog.error("quick upload", repr(e))
        return PlainTextResponse(f"✗ Конспект: помилка на ПК ({type(e).__name__}: {e})"[:300], status_code=500)
    finally:
        if tmp is not None:
            try:
                if "upload" in locals() and isinstance(upload, _SpooledUpload):
                    upload._f.close()
                tmp.unlink(missing_ok=True)
            except OSError:
                pass


async def quick_core(file, created: str | None = None, duration: str | None = None,
                     notes_language: str | None = None, source: str = "") -> str:
    free = shutil.disk_usage(storage.DATA_DIR).free
    if free < 300 * 1024 * 1024:
        raise HTTPException(507, "Мало місця на диску ПК")
    st = schedule.load_settings()
    now = datetime.now()
    meta = lectures.create({"date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M"),
                            "notes_language": notes_language or st.get("default_notes_language", "pl"),
                            "audio_language": st.get("default_audio_language", "pl")})
    lid = meta["id"]
    try:
        res = await lectures.save_upload(lid, file, float(duration) if duration else None)
    except ValueError as e:
        lectures.trash(lid)
        raise HTTPException(400, str(e))
    entry = res["file"]
    if source:
        lectures.mutate(lid, lambda m: [f.__setitem__("source", source) for f in m["files"] if f["name"] == entry["name"]])
    p = storage.LECTURES_DIR / lid / lectures.KIND_DIRS[entry["kind"]] / entry["name"]
    dur, meta_t = _media_info(p)
    dur = float(duration or 0) or dur
    if dur and not entry.get("duration"):
        lectures.mutate(lid, lambda m: [f.__setitem__("duration", round(dur, 1)) for f in m["files"] if f["name"] == entry["name"]])
    # момент запису: метадані файлу → дата з «Команд» → «щойно закінчили»
    moments = []
    if meta_t:
        moments.append(meta_t)
    if created:
        try:
            t = datetime.fromisoformat(created.strip().replace("Z", "+00:00"))
            moments.append(t.astimezone().replace(tzinfo=None) if t.tzinfo else t)
        except ValueError:
            pass
    moments.append(now)
    span = timedelta(seconds=dur if dur and dur >= 15 * 60 else 5400)  # короткий запис — дивимось на ціле заняття
    best = None
    for t in moments:
        # не знаємо, це початок чи кінець запису — пробуємо обидва
        for a, b in ((t, t + span), (t - span, t)):
            for c in schedule.detect(a, b):
                if not best or c["confidence"] > best[0]["confidence"]:
                    best = (c, a)
        if best and best[0]["confidence"] >= 0.6:
            break
    if best and best[0]["confidence"] >= 0.45:
        c, a = best
        lectures.update(lid, {"subject_id": c["subject_id"], "type": c["type"], "date": a.strftime("%Y-%m-%d"), "time": c["start"]})
        label = f"{c.get('short') or c.get('subject')} · {schedule.TYPES.get(c['type'], c['type'])} · {a.strftime('%d.%m')} {c['start']}"
    else:
        t0 = moments[0] - (span if moments[0] is now else timedelta(0))
        lectures.update(lid, {"date": t0.strftime("%Y-%m-%d"), "time": t0.strftime("%H:%M")})
        label = f"предмет не визначено ({t0.strftime('%d.%m %H:%M')}) — оберіть у застосунку"
    if entry["kind"] == "video":
        video.enqueue(lid, entry["name"])
        lectures.mutate(lid, lambda m: m.__setitem__("transcribe_after_video", bool(st.get("auto_transcribe"))))
    elif entry["kind"] == "audio" and st.get("auto_transcribe") and transcriber.available():
        transcriber.enqueue(lid)
    if st.get("auto_request_claude"):
        lectures.request_claude(lid)
    bump()
    mins = int(dur // 60)
    tr = " · обробляю відео" if entry["kind"] == "video" else (" · розшифровка почалась" if entry["kind"] == "audio" and transcriber.available() else "")
    return f"✓ Конспект: {label}" + (f" · {mins} хв" if mins else "") + tr


# ---------------------------------------------------------------- recording in the app
@app.post("/api/record/start")
async def record_start(request: Request):
    free = shutil.disk_usage(storage.DATA_DIR).free
    if free < 300 * 1024 * 1024:
        raise HTTPException(507, "Мало місця на диску ПК (менше 300 МБ)")
    r = recorder.start(await request.json())
    bump()
    return r


@app.post("/api/record/{lid}/{sid}/chunk")
async def record_chunk(lid: str, sid: str, seq: int, request: Request, force: int = 0):
    data = await request.body()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(413, "Завеликий шматок")
    r = recorder.chunk(lid, sid, seq, data, bool(force))
    if not r["ok"]:
        return JSONResponse(r, status_code=409)
    return r


@app.post("/api/record/{lid}/mark")
async def record_mark(lid: str, request: Request):
    body = await request.json()
    recorder.mark(lid, float(body.get("t") or 0))
    return {"ok": True}


@app.post("/api/record/{lid}/finish")
async def record_finish(lid: str, request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    m = recorder.finish(lid, body.get("session") or None, body.get("duration"))
    bump()
    return m


# ---------------------------------------------------------------- deadlines & ePortal slides
@app.get("/api/deadlines")
def deadlines():
    return eportal.list_deadlines()


@app.post("/api/deadlines")
async def deadline_add(request: Request):
    try:
        r = eportal.add_deadline(await request.json())
    except ValueError as e:
        raise HTTPException(400, str(e))
    bump()
    return r


@app.post("/api/deadlines/{did}")
async def deadline_set(did: str, request: Request):
    body = await request.json()
    r = eportal.set_deadline(did, done=bool(body.get("done")))
    bump()
    return r


@app.delete("/api/deadlines/{did}")
def deadline_del(did: str):
    r = eportal.set_deadline(did, delete=True)
    bump()
    return r


@app.get("/api/lectures/{lid}/eportal")
def lecture_eportal(lid: str):
    lectures.read_meta(lid)
    return eportal.candidates(lid)


@app.post("/api/lectures/{lid}/eportal")
async def lecture_eportal_attach(lid: str, request: Request):
    body = await request.json()
    at = body.get("as_task")
    meta = eportal.attach(lid, str(body.get("key") or ""), as_task=None if at is None else bool(at))
    lectures.write_queue()
    bump()
    return lectures.enrich(meta, full=True)


@app.post("/api/lectures/{lid}/open-folder")
def open_folder(lid: str, request: Request):
    if _is_remote(request):  # Провідник відкрився б на ПК, а не на телефоні
        raise HTTPException(400, "Лише на ПК")
    d = lectures.lecture_dir(lid)
    _open_path(d)
    return {"ok": True, "path": str(d)}


@app.post("/api/open-data-folder")
def open_data_folder(request: Request):
    if _is_remote(request):
        raise HTTPException(400, "Лише на ПК")
    _open_path(storage.DATA_DIR)
    return {"ok": True, "path": str(storage.DATA_DIR)}


def _open_path(p) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(str(p))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
    except Exception as e:
        raise HTTPException(500, f"Не вдалося відкрити папку: {e}")


@app.get("/api/search")
def search(q: str = ""):
    return lectures.search(q)


@app.post("/api/open-claude")
def open_claude(request: Request):
    """2.1: «Надіслати в Claude» — відкриває застосунок Claude на цьому ПК (повідомлення вже в буфері обміну)."""
    if _is_remote(request):
        raise HTTPException(400, "Лише на ПК")
    if sys.platform != "win32":
        raise HTTPException(404, "Лише Windows")
    cands = [Path(os.environ.get("LOCALAPPDATA", "")) / "AnthropicClaude" / "claude.exe",
             Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Claude" / "Claude.exe",
             Path(os.environ.get("PROGRAMFILES", "")) / "Claude" / "Claude.exe"]
    for exe in cands:
        if exe.is_file():
            subprocess.Popen([str(exe)], close_fds=True)
            return {"ok": True, "via": "exe"}
    try:
        os.startfile("claude://")  # type: ignore[attr-defined]
        return {"ok": True, "via": "protocol"}
    except OSError as e:
        raise HTTPException(404, f"Claude не знайдено: {e}")


@app.get("/api/claude-prompt", response_class=PlainTextResponse)
def claude_prompt():
    q = storage.read_json(storage.DATA_DIR / "queue.json", {"lectures": []})
    n = sum(len(q.get(k, [])) for k in ("lectures", "subjects", "help", "explain", "plans", "reports", "exam_prep", "zaliczenie", "project_steps"))
    return (f"Оброби нові лекції з мого застосунку «Конспект» ({n} у черзі). "
            f"Папка даних: {storage.DATA_DIR}. Протокол — у файлі CLAUDE.md у цій папці.")


# ---------------------------------------------------------------- subject materials
@app.get("/api/subjects/{sid}/materials")
def get_materials(sid: str):
    return materials.get(sid)


@app.put("/api/subjects/{sid}/materials")
async def put_materials(sid: str, request: Request):
    b = await request.json()
    out = materials.save(sid, b.get("notes"), b.get("links"))
    bump()
    return out


@app.put("/api/subjects/{sid}/plan")
async def put_plan(sid: str, request: Request):
    b = await request.json()
    out = materials.save_plan(sid, b.get("items") or [])
    bump()
    return out


@app.post("/api/subjects/{sid}/parse")
async def req_parse(sid: str, request: Request):
    b = {}
    try:
        b = await request.json()
    except Exception:
        pass
    out = materials.request_parse(sid, b.get("instructions", ""))
    lectures.write_queue()
    bump()
    return out


@app.delete("/api/subjects/{sid}/parse")
def cancel_parse(sid: str):
    out = materials.cancel_parse(sid)
    lectures.write_queue()
    bump()
    return out


@app.post("/api/subjects/{sid}/files")
async def upload_subject_file(sid: str, file: UploadFile = File(...)):
    try:
        out = await materials.save_file(sid, file)
    except ValueError as e:
        raise HTTPException(400, str(e))
    bump()
    return out


@app.get("/api/subjects/{sid}/files/{name}")
def get_subject_file(sid: str, name: str, download: int = 0):
    p = materials.file_path(sid, name)
    return FileResponse(p, filename=p.name if download else None,
                        content_disposition_type="attachment" if download else "inline")


@app.delete("/api/subjects/{sid}/files/{name}")
def del_subject_file(sid: str, name: str):
    out = materials.delete_file(sid, name)
    bump()
    return out


@app.get("/api/subjects/{sid}/script.pdf")
def subject_script(sid: str):
    subj = next((s for s in schedule.load_schedule()["subjects"] if s["id"] == sid), None)
    if not subj:
        raise HTTPException(404, "Предмет не знайдено")
    try:
        p = study.build_script(sid, subj["name"])
    except ImportError:
        raise HTTPException(500, "Не встановлено pypdf — перезапустіть start.bat, він доставить залежності")
    except ValueError as e:
        raise HTTPException(400, str(e))
    safe = storage.safe_filename(f"{subj.get('short') or sid} - skrypt.pdf")
    return FileResponse(p, filename=safe, media_type="application/pdf", headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- study (2.0)
@app.get("/api/study")
def get_study(subject: str | None = None, lecture: str | None = None, hidden: int = 0):
    data = study._progress()
    cards = study.all_cards(subject, lecture, include_hidden=bool(hidden), data=data)
    return {"cards": cards, "stats": study.stats(data=data)}


@app.get("/api/study/session")
def study_session(mode: str = "today", subject: str | None = None, lecture: str | None = None, n: int | None = None):
    return study.session(mode, subject or None, lecture or None, n)


@app.get("/api/study/progress")
def study_progress():
    return study.progress()


_study_log = {"n": 0, "t": 0.0}


@app.post("/api/study/answer")
async def study_answer(request: Request):
    b = await request.json()
    try:
        r = study.answer(str(b.get("key")), b.get("rating"), b.get("known"), int(b.get("ms") or 0))
    except ValueError as e:
        raise HTTPException(400, str(e))
    _study_log["n"] += 1
    if time.time() - _study_log["t"] > 1200:  # у журнал — раз на 20 хв, а не кожну відповідь
        applog.event("study", mode="cards", answers=_study_log["n"])
        _study_log.update(n=0, t=time.time())
    bump()
    return r


@app.post("/api/study/activity")
async def study_activity(request: Request):
    b = await request.json()
    r = study.log_activity(str(b.get("mode") or ""), int(b.get("n") or 0), int(b.get("correct") or 0),
                           int(b.get("ms") or 0), str(b.get("subject_id") or ""), b.get("mistakes") or [])
    applog.event("study", mode=str(b.get("mode") or ""), answers=int(b.get("n") or 0), correct=int(b.get("correct") or 0))
    bump()
    return r


@app.patch("/api/study/card")
async def study_edit(request: Request):
    b = await request.json()
    key = str(b.get("key") or "")
    if not key:
        raise HTTPException(400, "Немає key")
    r = study.edit(key, b)
    bump()
    return r


@app.post("/api/study/custom")
async def study_custom(request: Request):
    try:
        r = study.add_custom(await request.json())
    except ValueError as e:
        raise HTTPException(400, str(e))
    bump()
    return r


@app.delete("/api/study/custom/{cid}")
def study_custom_del(cid: str):
    r = study.delete_custom(cid)
    bump()
    return r


@app.post("/api/study/explain")
async def study_explain(request: Request):
    b = await request.json()
    r = study.request_explain(str(b.get("key") or ""), str(b.get("note") or ""))
    lectures.write_queue()
    bump()
    return r


@app.delete("/api/study/explain")
def study_explain_cancel(key: str):
    r = study.cancel_explain(key)
    lectures.write_queue()
    bump()
    return r


@app.post("/api/study/reset")
async def study_reset(request: Request):
    b = await request.json()
    r = {"reset": study.reset(b.get("subject") or None)}
    bump()
    return r


# ---------------------------------------------------------------- заняття за типом (2.0)
@app.get("/api/subjects/{sid}/course")
def subject_course(sid: str):
    return {"memory": course.memory(sid), "map": course.course_map(sid)}


@app.get("/api/lectures/{lid}/help")
def lecture_help(lid: str):
    return course.help_list(lid)


@app.post("/api/lectures/{lid}/help")
async def lecture_help_ask(lid: str, request: Request):
    b = await request.json()
    try:
        r = course.ask_help(lid, str(b.get("q") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    bump()
    return r


@app.get("/api/lectures/{lid}/plan")
def lecture_plan(lid: str):
    return course.plan_info(lid)


@app.post("/api/lectures/{lid}/plan")
async def lecture_plan_req(lid: str, request: Request):
    b = {}
    try:
        b = await request.json()
    except Exception:
        pass
    try:
        r = course.request_plan(lid, note=str(b.get("note") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    bump()
    return r


@app.delete("/api/lectures/{lid}/plan")
def lecture_plan_cancel(lid: str):
    r = course.cancel_plan(lid)
    bump()
    return r


@app.post("/api/lectures/{lid}/eportal-new")
async def lecture_eportal_new(lid: str, request: Request):
    b = await request.json()
    eportal.eportal_new_action(lid, str(b.get("action") or "dismiss"))
    bump()
    return lectures.enrich(lectures.read_meta(lid), full=True)


@app.delete("/api/lectures/{lid}/help/{hid}")
def lecture_help_del(lid: str, hid: str):
    r = course.delete_help(lid, hid)
    bump()
    return r


@app.post("/api/lectures/{lid}/submitted")
async def lecture_submitted(lid: str, request: Request):
    b = await request.json()
    r = course.set_submitted(lid, bool(b.get("done", True)))
    lectures.write_queue()
    bump()
    return r


@app.post("/api/lectures/{lid}/checklist/{cid}")
async def lecture_check(lid: str, cid: str, request: Request):
    b = await request.json()
    r = course.set_check(lid, cid, bool(b.get("done")))
    bump()
    return r


@app.get("/api/checklists")
def checklists(all: int = 0):
    return course.all_checklists(include_done=bool(all))


# ---------------------------------------------------------------- trash & backups
@app.get("/api/trash")
def get_trash():
    return lectures.list_trash()


@app.post("/api/trash/{tid}/restore")
def restore(tid: str):
    lid = lectures.restore(tid)
    bump()
    return {"id": lid}


@app.get("/api/backups")
def backups():
    return storage.list_backups()


@app.post("/api/backups")
def backup_now():
    p = storage.make_backup("manual")
    if not p:
        raise HTTPException(500, "Не вдалося створити копію")
    return {"name": p.name}


@app.get("/api/backups/{name}")
def get_backup(name: str):
    p = (storage.BACKUPS_DIR / name).resolve()
    if storage.BACKUPS_DIR.resolve() not in p.parents or not p.is_file():
        raise HTTPException(404, "Не знайдено")
    return FileResponse(p, filename=p.name)


# ---------------------------------------------------------------- whisper
@app.post("/api/whisper/install")
def whisper_install():
    transcriber.install()
    return transcriber.status()


@app.post("/api/whisper/install-gpu")
def whisper_install_gpu():
    transcriber.install_gpu()
    return transcriber.status()


@app.get("/api/whisper")
def whisper_status():
    return transcriber.status()


@app.get("/api/remote")
def remote_status():
    return remote.status(_state["port"])


@app.post("/api/remote/enable")
def remote_enable():
    if BETA:
        raise HTTPException(400, "У беті доступ через Tailscale вимкнено (він налаштований на основну версію)")
    return remote.enable(_state["port"])


@app.post("/api/remote/disable")
def remote_disable():
    if BETA:
        raise HTTPException(400, "У беті доступ через Tailscale вимкнено")
    return remote.disable(_state["port"])


# ---------------------------------------------------------------- USOS / ePortal
@app.get("/api/usos")
def usos_status():
    return usos.public_status()


@app.post("/api/usos/connect")
async def usos_connect(request: Request):
    _no_beta("USOS")
    body = await request.json()
    try:
        r = usos.connect(str(body.get("url") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    bump()
    return r


@app.post("/api/usos/sync")
def usos_sync():
    _no_beta("ePortal/USOS")
    if not usos.load().get("url"):
        raise HTTPException(400, "USOS не підключено")
    usos.sync_async()
    return {**usos.public_status(), "running": True}


@app.post("/api/usos/disconnect")
def usos_disconnect():
    _no_beta("ePortal/USOS")
    r = usos.disconnect()
    bump()
    return r


@app.get("/api/health")
def health():
    """Стан застосунку (2.2): синхронізації, помилки за добу, розшифровка, Claude — з data/logs/events.jsonl."""
    return applog.summary()


@app.get("/api/eportal")
def eportal_status():
    return eportal.public_status()


@app.post("/api/eportal/connect")
def eportal_connect():
    _no_beta("ePortal/USOS")
    return eportal.start_connect()


@app.post("/api/eportal/token")
async def eportal_token(request: Request):
    _no_beta("ePortal")
    body = await request.json()
    try:
        r = eportal.finish_connect(str(body.get("link") or ""))
    except (ValueError, eportal.MoodleError) as e:
        raise HTTPException(400, str(e))
    except OSError as e:
        raise HTTPException(502, f"Немає зв'язку з ePortalem: {e}")
    bump()
    return r


@app.post("/api/eportal/sync")
def eportal_sync():
    _no_beta("ePortal/USOS")
    if not eportal.load().get("token"):
        raise HTTPException(400, "ePortal не підключено")
    eportal.sync_async()
    return {**eportal.public_status(), "running": True}


@app.post("/api/eportal/course")
async def eportal_course(request: Request):
    body = await request.json()
    return eportal.set_course_subject(int(body.get("course_id")), body.get("subject_id") or None)


@app.post("/api/eportal/disconnect")
def eportal_disconnect():
    _no_beta("ePortal/USOS")
    r = eportal.disconnect()
    bump()
    return r


@app.post("/api/shutdown")
def shutdown():
    """Вимикає сервер (корисно, якщо його запущено без вікна)."""
    storage.make_backup("shutdown")
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return {"ok": True}


# ---------------------------------------------------------------- planner
@app.get("/api/planner")
def planner_view(start: str | None = None, days: int = 28, lat: float | None = None, lon: float | None = None):
    try:
        d0 = date.fromisoformat(start) if start else date.today()
    except ValueError:
        d0 = date.today()
    d0 = d0 - timedelta(days=d0.weekday())
    out = planner.plan(d0, max(1, min(int(days), 120)), lat, lon)
    out["tasks"] = semester.place_tasks(out["days"])  # 2.3 (E2): що робити у вільних вікнах
    return out


@app.post("/api/planner/geocode")
async def planner_geocode(request: Request):
    body = await request.json()
    try:
        g = planner.geocode(str(body.get("address") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except OSError as e:
        raise HTTPException(502, f"Немає зв'язку з OpenStreetMap: {e}")
    st = schedule.save_settings({"planner_address": str(body.get("address") or "").strip()[:300],
                                 "planner_lat": g["lat"], "planner_lon": g["lon"], "planner_place": g["place"][:300]})
    bump()
    return {**g, "settings": st}


# ---------------------------------------------------------------- 2.3: семестр, звіти, календар, сповіщення
@app.get("/api/semester")
def semester_view():
    return semester.semester()


@app.post("/api/semester/grade")
async def semester_grade(request: Request):
    b = await request.json()
    try:
        r = semester.add_grade(str(b.get("subject_id") or ""), str(b.get("component") or ""), b.get("value"), str(b.get("title") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    bump()
    return r


@app.delete("/api/semester/grade/{sid}/{gid}")
def semester_grade_del(sid: str, gid: str):
    r = semester.delete_grade(sid, gid)
    bump()
    return r


@app.post("/api/subjects/{sid}/exam-prep")
async def exam_prep(sid: str, request: Request):
    b = await request.json()
    try:
        r = semester.request_exam_prep(sid, str(b.get("date") or ""), str(b.get("title") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    lectures.write_queue()
    bump()
    return r


@app.delete("/api/subjects/{sid}/exam-prep")
def exam_prep_cancel(sid: str):
    r = semester.cancel_exam_prep(sid)
    lectures.write_queue()
    bump()
    return r


@app.get("/api/subjects/{sid}/szpargalka.pdf")
def szpargalka(sid: str, download: int = 0):
    p = storage.DATA_DIR / "subjects" / sid / "szpargalka.pdf"
    if not p.resolve().is_relative_to((storage.DATA_DIR / "subjects").resolve()) or not p.is_file():
        raise HTTPException(404, "Шпаргалки ще немає")
    return FileResponse(p, filename=f"szpargalka_{sid}.pdf" if download else None,
                        content_disposition_type="attachment" if download else "inline", headers={"Cache-Control": "no-store"})


@app.post("/api/lectures/{lid}/report")
async def lecture_report(lid: str, request: Request):
    b = await request.json()
    try:
        course.request_report(lid, str(b.get("kind") or ""), str(b.get("note") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    lectures.write_queue()
    bump()
    return get_lecture(lid)


@app.delete("/api/lectures/{lid}/report")
def lecture_report_cancel(lid: str):
    course.cancel_report(lid)
    lectures.write_queue()
    bump()
    return get_lecture(lid)


# ---------------------------------------------------------------- 2.4: «Проєкт» — по одному кроку, одне місце для файлів
def _proj(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ValueError as e:
        raise HTTPException(409, str(e))


# ---------------------------------------------------------------- 2.9: «Поділитися конспектами»
@app.get("/api/share/subjects")
def share_subjects():
    return share.subjects_summary()


@app.post("/api/share/export")
async def share_export(request: Request):
    b = await request.json()
    try:
        p = share.export(list(b.get("subjects") or []), b.get("options") or {}, str(b.get("author") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return FileResponse(p, filename=f"Konspekt_konspekty_{datetime.now():%Y-%m-%d}.zip", media_type="application/zip")


def _share_tmp(token: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{12}", token or ""):
        raise HTTPException(404, "Пакет не знайдено — завантажте його ще раз")
    p = storage.TMP_DIR / f"share_in_{token}.zip"
    if not p.exists():
        raise HTTPException(404, "Пакет не знайдено — завантажте його ще раз")
    return p


@app.post("/api/share/preview")
async def share_preview(file: UploadFile = File(...)):
    storage.TMP_DIR.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:12]
    p = storage.TMP_DIR / f"share_in_{token}.zip"
    size = 0
    with open(p, "wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > share.MAX_TOTAL:
                f.close()
                p.unlink(missing_ok=True)
                raise HTTPException(400, "Пакет завеликий")
            f.write(chunk)
    try:
        return {"token": token, **share.preview(p)}
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        p.unlink(missing_ok=True)
        raise HTTPException(400, str(e) or "Пакет пошкоджено")


@app.post("/api/share/import")
async def share_import(request: Request):
    b = await request.json()
    p = _share_tmp(str(b.get("token") or ""))
    try:
        r = share.apply(p)
    except ValueError as e:
        raise HTTPException(400, str(e))
    p.unlink(missing_ok=True)
    bump()
    return r


# ---------------------------------------------------------------- 2.7: «Робота в чаті» (Cowork)
def _chat_target(kind: str, key: str):
    if kind == "lecture":
        lectures.lecture_dir(key)  # 404, якщо заняття немає
        return chat.lecture_info, chat.build_lecture
    if kind == "project":
        return chat.project_info, chat.build_project
    raise HTTPException(404, "Невідомий тип")


@app.get("/api/chat/{kind}/{key}")
def chat_get(kind: str, key: str):
    return _chat_target(kind, key)[0](key)


@app.post("/api/chat/{kind}/{key}")
async def chat_build(kind: str, key: str, request: Request):
    b = await request.json()
    r = _proj(_chat_target(kind, key)[1], key, str(b.get("note") or ""))
    applog.event("chat_built", what=kind, key=key, note=bool(b.get("note")))
    return r


@app.get("/api/chat/{kind}/{key}/zip")
def chat_zip(kind: str, key: str):
    _chat_target(kind, key)
    p = _proj(chat.make_zip, kind, key)
    return FileResponse(p, filename=f"Konspekt_{key}.zip", media_type="application/zip")


@app.post("/api/chat/{kind}/{key}/open-folder")
def chat_open_folder(kind: str, key: str, request: Request):
    if _is_remote(request):
        raise HTTPException(400, "Лише на ПК")
    _open_path(Path(_chat_target(kind, key)[0](key)["folder"]))
    return {"ok": True}


@app.get("/api/subjects/{sid}/project")
def project_get(sid: str):
    return project.info(sid)


@app.post("/api/subjects/{sid}/project")
async def project_create(sid: str, request: Request):
    b = await request.json()
    r = _proj(project.create, sid, str(b.get("title") or ""))
    bump()
    return r


@app.post("/api/subjects/{sid}/project/step")
async def project_step(sid: str, request: Request):
    b = await request.json()
    r = _proj(project.request_step, sid, str(b.get("note") or ""), str(b.get("kind") or "next"))
    lectures.write_queue()
    bump()
    return r


@app.delete("/api/subjects/{sid}/project/step")
def project_step_cancel(sid: str):
    r = project.cancel_step(sid)
    lectures.write_queue()
    bump()
    return r


@app.post("/api/subjects/{sid}/project/step/{n}/done")
async def project_step_done(sid: str, n: int, request: Request):
    b = await request.json()
    r = project.set_done(sid, n, bool(b.get("done", True)))
    bump()
    return r


@app.post("/api/subjects/{sid}/project/stage-done")
async def project_stage_done(sid: str, request: Request):
    b = await request.json()
    r = project.stage_done(sid, str(b.get("stage") or ""), bool(b.get("done", True)))
    lectures.write_queue()
    bump()
    return r


@app.post("/api/subjects/{sid}/project/stage")
async def project_stage(sid: str, request: Request):
    b = await request.json()
    r = project.set_stage(sid, str(b.get("stage") or ""))
    bump()
    return r


@app.post("/api/subjects/{sid}/project/files")
async def project_upload(sid: str, file: UploadFile = File(...), area: str = Form("work")):
    if not project.exists(sid):
        raise HTTPException(404, "Проєкту ще немає")
    tmp = storage.TMP_DIR / f"proj_{os.getpid()}_{time.time_ns()}.part"
    storage.ensure_dirs()
    with open(tmp, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
    try:
        r = _proj(project.put_file, sid, area, file.filename or "plik", tmp)
    finally:
        if tmp.exists():
            tmp.unlink()
    lectures.write_queue()
    bump()
    return r


@app.post("/api/subjects/{sid}/project/promote")
async def project_promote(sid: str, request: Request):
    b = await request.json()
    r = project.promote(sid, str(b.get("name") or ""), str(b.get("as_name") or ""))
    bump()
    return r


@app.get("/api/subjects/{sid}/project/file/{area}/{name:path}")
def project_file(sid: str, area: str, name: str, download: int = 0):
    p = project.file_path(sid, area, name)
    return FileResponse(p, filename=p.name if download else None,
                        content_disposition_type="attachment" if download else "inline", headers={"Cache-Control": "no-store"})


@app.get("/api/calendar-info")
def calendar_info():
    r = remote.status(_state["port"])
    path = f"/api/calendar.ics?k={semester.calendar_key()}"
    return {"tailscale": (r.get("url") + path) if r.get("url") else None, "local": f"http://127.0.0.1:{_state['port']}{path}"}


@app.get("/api/calendar.ics")
def calendar_ics(k: str = ""):
    import hmac
    if not k or not hmac.compare_digest(k, semester.calendar_key()):
        raise HTTPException(403, "Неправильний ключ календаря")
    applog.event("calendar_fetch")
    return PlainTextResponse(semester.ics(), media_type="text/calendar; charset=utf-8",
                             headers={"Content-Disposition": "inline; filename=konspekt.ics", "Cache-Control": "no-store"})


@app.get("/api/push")
def push_info():
    return {"public_key": push.public_key(), **push.status()}


@app.post("/api/push/subscribe")
async def push_subscribe(request: Request):
    b = await request.json()
    try:
        return push.subscribe(b.get("subscription") or {}, str(b.get("device") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/push/unsubscribe")
async def push_unsubscribe(request: Request):
    b = await request.json()
    return push.unsubscribe(str(b.get("endpoint") or ""))


@app.post("/api/push/test")
def push_test():
    n = push.notify("test", "Конспект: перевірка сповіщень", "Якщо ти це бачиш — усе працює", "#/settings", force=True)
    if not n:
        raise HTTPException(400, "Немає підписаних пристроїв")
    return {"sent_to": n}


# ---------------------------------------------------------------- frontend
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    """2.3 (E7): service worker з кореня, щоб охоплював увесь застосунок (офлайн і сповіщення)."""
    return FileResponse(STATIC / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC / "favicon.ico", media_type="image/x-icon")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


# ---------------------------------------------------------------- entry point
def _port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _is_ours(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1.5) as r:
            return b"konspekt" in r.read()
    except Exception:
        return False


def _lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--lan", action="store_true", help="доступ з телефона в тій самій Wi-Fi мережі")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    if sys.stdout is None or sys.stderr is None:  # запуск через pythonw (без вікна)
        storage.ensure_dirs()
        lp = storage.DATA_DIR / "server.log"
        if lp.exists() and lp.stat().st_size > 2_000_000:
            lp.replace(lp.with_suffix(".old.log"))
        log = open(lp, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log

    if _is_ours(args.port):
        print(f"Конспект уже запущено: http://127.0.0.1:{args.port}")
        if not args.no_browser:
            webbrowser.open(f"http://127.0.0.1:{args.port}")
        return

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    port = args.port
    while not _port_free(host, port):
        port += 1
        if port > args.port + 50:
            print("Не знайдено вільного порту")
            sys.exit(1)

    _state["port"] = port
    if port != args.port:
        print(f"  [!] Порт {args.port} зайнятий — використовую {port}. Доступ через Tailscale треба буде перепідключити.")
    url = f"http://127.0.0.1:{port}"
    print("=" * 60)
    print(f"  Конспект {VERSION}")
    print(f"  Відкрийте: {url}")
    if args.lan:
        print(f"  З телефона (та сама Wi-Fi): http://{_lan_ip()}:{port}")
    print(f"  Дані: {storage.DATA_DIR}")
    print("  Зупинити: закрийте це вікно або Ctrl+C")
    print("=" * 60)
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
