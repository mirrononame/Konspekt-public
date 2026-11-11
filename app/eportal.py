"""ePortal PWr (Moodle): підключення через офіційний «мобільний» вхід і синхронізація матеріалів.

Підключення (без пароля в застосунку):
  1. Застосунок реєструє в Windows протокол moodlemobile:// (лише для поточного користувача).
  2. Відкриває у браузері, де ви вже ввійшли в ePortal,
     https://eportal.pwr.edu.pl/admin/tool/mobile/launch.php?service=moodle_mobile_app&passport=…&urlscheme=moodlemobile
  3. ePortal повертає moodlemobile://token=… → moodle_callback.py кладе його в data/eportal_inbox.json,
     сервер перевіряє підпис md5(wwwroot+passport) і зберігає токен у secrets/eportal.json (лише на ПК).
Запасний варіант — вставити посилання moodlemobile://token=… вручну.

Синхронізація: курси → предмети розкладу; розділи з датами → plan.json (source "eportal",
ручні плани не перезаписуються); відкриті файли (resource/folder) → subjects/<id>/files/.
Захищені модулі (securepdf тощо) НЕ завантажуються.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

from . import applog, storage

WWWROOT = "https://eportal.pwr.edu.pl"
EP_FILE = storage.SECRETS_DIR / "eportal.json"
INBOX = storage.DATA_DIR / "eportal_inbox.json"
DOWNLOAD_MODS = {"resource", "folder"}
MAX_FILE = 80 * 1024 * 1024
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Konspekt/1.4 (MoodleMobile-compatible)"
_state = {"running": False}
_lock = threading.Lock()


class MoodleError(Exception):
    def __init__(self, msg, code=""):
        super().__init__(msg)
        self.code = code


def load() -> dict:
    d = storage.read_json(EP_FILE, {}) or {}
    d.setdefault("courses", [])
    d.setdefault("course_map", {})
    d.setdefault("files", {})
    return d


def _save(d: dict) -> None:
    storage.write_json(EP_FILE, d)


def _recent(iso, minutes: int = 10) -> bool:
    try:
        return time.time() - datetime.fromisoformat(iso).timestamp() < minutes * 60
    except Exception:
        return False


def public_status() -> dict:
    d = load()
    return {"connected": bool(d.get("token")), "user": d.get("user", ""), "synced_at": d.get("synced_at"),
            "status": d.get("status", "idle"), "message": d.get("message", ""), "running": _state["running"],
            "pending": bool(d.get("passport")) and not d.get("token") and _recent(d.get("passport_at")),
            "protocol": d.get("protocol_registered", False),
            "courses": [{**c, "subject_id": d["course_map"].get(str(c["id"]))} for c in d["courses"]],
            "files": sum(1 for f in d["files"].values() if f.get("saved"))}


# ---------------------------------------------------------------- connect
def _callback_script() -> Path:
    return storage.APP_DIR / "moodle_callback.py"


def register_protocol() -> bool:
    """HKCU\\Software\\Classes\\moodlemobile → pythonw moodle_callback.py <data> "%1" (лише Windows)."""
    if sys.platform != "win32":
        return False
    import winreg
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    exe = pyw if pyw.exists() else exe
    cmd = f'"{exe}" "{_callback_script()}" "{storage.DATA_DIR}" "%1"'
    base = r"Software\Classes\moodlemobile"
    d = load()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
            prev = winreg.QueryValueEx(k, "")[0]
            if "moodle_callback.py" not in prev:
                d["protocol_prev"] = prev  # напр., офіційний застосунок Moodle — відновимо при відключенні
    except OSError:
        pass
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "URL:Konspekt ePortal login")
        winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
    d["protocol_registered"] = True
    _save(d)
    return True


def unregister_protocol() -> None:
    if sys.platform != "win32":
        return
    import winreg
    d = load()
    base = r"Software\Classes\moodlemobile"
    try:
        if d.get("protocol_prev"):
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, d["protocol_prev"])
        else:
            for sub in (r"\shell\open\command", r"\shell\open", r"\shell", ""):
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, base + sub)
                except OSError:
                    pass
    except OSError:
        pass


def start_connect() -> dict:
    with _lock:
        d = load()
        d["passport"] = secrets.token_hex(8)
        d["passport_at"] = storage.now_iso()
        d["status"], d["message"] = "pending", "Чекаю підтвердження входу з браузера…"
        _save(d)
    try:
        reg = register_protocol()
    except Exception as e:
        reg = False
        applog.error("eportal", "protocol registration failed:", e)
    q = urllib.parse.urlencode({"service": "moodle_mobile_app", "passport": d["passport"], "urlscheme": "moodlemobile"})
    return {**public_status(), "launch_url": f"{WWWROOT}/admin/tool/mobile/launch.php?{q}", "protocol": reg}


def _decode_token(raw: str, passport: str | None) -> tuple[str, str]:
    raw = (raw or "").strip().strip('"')
    m = re.search(r"token=([A-Za-z0-9+/=_-]+)", raw)
    payload = m.group(1) if m else raw
    if re.fullmatch(r"[0-9a-f]{32}", payload):
        return payload, ""  # уже готовий токен (наприклад, із «Klucze bezpieczeństwa»)
    payload += "=" * (-len(payload) % 4)
    try:
        dec = base64.b64decode(payload.replace("-", "+").replace("_", "/")).decode("utf-8", "replace")
    except Exception:
        raise ValueError("Не вдалося прочитати посилання входу. Скопіюйте його повністю (moodlemobile://token=…)")
    parts = dec.split(":::")
    if len(parts) < 2 or not re.fullmatch(r"[0-9a-f]{32}", parts[1]):
        raise ValueError("Посилання не містить токена ePortal")
    if passport:
        ok = {hashlib.md5((w + passport).encode()).hexdigest() for w in (WWWROOT, WWWROOT + "/")}
        if parts[0] not in ok:
            raise ValueError("Підпис не збігається — це посилання від іншого запиту. Натисніть «Підключити» ще раз.")
    return parts[1], parts[2] if len(parts) > 2 else ""


def finish_connect(raw: str, check_passport: bool = True) -> dict:
    d = load()
    passport = d.get("passport") if check_passport else None
    if check_passport and not passport and "token=" in raw:
        raise ValueError("Немає активного запиту підключення. Натисніть «Підключити ePortal».")
    token, private = _decode_token(raw, passport)
    info = _call("core_webservice_get_site_info", token=token)
    with _lock:
        d = load()
        d.update(token=token, privatetoken=private, userid=info.get("userid"),
                 user=info.get("fullname") or info.get("username", ""), site=info.get("sitename", ""),
                 connected_at=storage.now_iso(), status="ok", message="Підключено")
        d.pop("passport", None)
        _save(d)
    sync_async()
    return public_status()


def check_inbox() -> bool:
    """Викликається сканером: забирає токен, який поклав moodle_callback.py."""
    if not INBOX.exists():
        return False
    try:
        data = json.loads(INBOX.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    INBOX.unlink(missing_ok=True)
    url = str(data.get("url") or "")
    if not url:
        return False
    try:
        finish_connect(url)
    except Exception as e:
        d = load()
        d.update(status="error", error_at=time.time(), message=str(e)[:300])
        _save(d)
    return True


def disconnect() -> dict:
    unregister_protocol()
    with _lock:
        d = load()
        _save({"files": d.get("files", {}), "course_map": d.get("course_map", {})})  # пам'ятаємо, що вже скачано
    return public_status()


def set_course_subject(course_id: int, subject_id: str | None) -> dict:
    with _lock:
        d = load()
        if subject_id:
            d["course_map"][str(course_id)] = subject_id
        else:
            d["course_map"][str(course_id)] = ""  # «не прив'язувати»
        _save(d)
    sync_async()
    return public_status()


# ---------------------------------------------------------------- Moodle API
def _flat(prefix: str, v, out: list):
    if isinstance(v, dict):
        for k, x in v.items():
            _flat(f"{prefix}[{k}]", x, out)
    elif isinstance(v, (list, tuple)):
        for i, x in enumerate(v):
            _flat(f"{prefix}[{i}]", x, out)
    else:
        out.append((prefix, str(int(v)) if isinstance(v, bool) else str(v)))


def _call(fn: str, token: str | None = None, **params):
    token = token or load().get("token")
    if not token:
        raise MoodleError("ePortal не підключено", "notoken")
    pairs = [("wstoken", token), ("wsfunction", fn), ("moodlewsrestformat", "json")]
    for k, v in params.items():
        _flat(k, v, pairs)
    req = urllib.request.Request(f"{WWWROOT}/webservice/rest/server.php", data=urllib.parse.urlencode(pairs).encode(),
                                 headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=40) as r:
        res = json.loads(r.read().decode("utf-8", "replace") or "null")
    if isinstance(res, dict) and res.get("exception"):
        code = res.get("errorcode", "")
        if code in ("invalidtoken", "accessexception"):
            raise MoodleError("Токен ePortalu більше не діє — підключіть ePortal ще раз.", "invalidtoken")
        raise MoodleError(res.get("message") or code, code)
    return res


def _download(url: str, target: Path, token: str) -> int:
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(f"{url}{sep}token={urllib.parse.quote(token)}", headers={"User-Agent": UA})
    tmp = storage.TMP_DIR / f"ep_{secrets.token_hex(6)}.part"
    size = 0
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            ctype = r.headers.get("Content-Type", "")
            first = True
            while chunk := r.read(1024 * 256):
                if first and "json" in ctype and chunk.lstrip().startswith(b"{"):
                    raise MoodleError("Файл недоступний (немає доступу)", "nofile")
                first = False
                size += len(chunk)
                if size > MAX_FILE:
                    raise MoodleError("Файл завеликий", "toobig")
                f.write(chunk)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    return size


# ---------------------------------------------------------------- matching & plan
def _norm(s: str) -> str:
    tr = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
    return re.sub(r"[^a-z0-9]+", " ", (s or "").translate(tr).lower()).strip()


def _code_core(code: str) -> str:
    m = re.search(r"([A-Z]{2}\d{4})", code or "")
    return m.group(1) if m else ""


def match_subject(course: dict, subjects: list[dict]) -> str | None:
    hay = " ".join(str(course.get(k) or "") for k in ("fullname", "shortname", "idnumber"))
    for s in subjects:
        core = _code_core(s.get("usos_code", ""))
        if core and core in hay.upper():
            return s["id"]
    nh = f" {_norm(hay)} "
    best = None
    for s in subjects:
        n = _norm(s["name"])
        if n and f" {n} " in nh and (not best or len(n) > len(best[1])):
            best = (s["id"], n)
    return best[0] if best else None


_DATE_RX = [
    (re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})"), lambda g: (int(g[0]), int(g[1]), int(g[2]))),
    (re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b"), lambda g: (int(g[2]), int(g[1]), int(g[0]))),
]


def section_date(name: str) -> str:
    for rx, f in _DATE_RX:
        m = rx.search(name or "")
        if m:
            try:
                return date(*f(m.groups())).isoformat()
            except ValueError:
                pass
    return ""


def _clean_title(name: str) -> str:
    t = re.sub(r"\(?\b(20\d{2}[-./]\d{1,2}[-./]\d{1,2}|\d{1,2}[./]\d{1,2}[./]20\d{2})\b\)?", "", name or "")
    return re.sub(r"\s+", " ", t).strip(" -–—:|")


def _strip_html(s: str) -> str:
    import html as h
    return re.sub(r"\s+", " ", h.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def build_plan(sections: list[dict]) -> list[dict]:
    items = []
    for sec in sections:
        name = sec.get("name") or ""
        dt = section_date(name) or section_date(_strip_html(sec.get("summary", ""))[:200])
        if not dt:
            continue
        topics, links = [], []
        summ = _strip_html(sec.get("summary", ""))
        if summ:
            topics += [t.strip(" -•") for t in re.split(r"[;\n•]| - ", summ) if 3 < len(t.strip(" -•")) < 200][:8]
        for m in sec.get("modules", []):
            if not m.get("visible", 1) or m.get("modname") == "label":
                continue
            if m.get("url"):
                links.append({"title": (m.get("name") or "")[:200], "url": m["url"]})
        items.append({"date": dt, "title": _clean_title(name) or name, "topics": topics, "links": links[:20]})
    return items


def _write_plan(sid: str, items: list[dict]) -> bool:
    from . import materials
    d = materials.subject_dir(sid)
    if materials.get(sid).get("parse_pending"):
        return False  # чекає на Claude — не заважаємо
    cur = storage.read_json(d / "plan.json", {}) or {}
    if cur.get("items") and cur.get("source") not in (None, "eportal"):
        return False  # ручний план або план від Claude — не чіпаємо
    by_date: dict = {}
    for it in items:
        if it["date"] in by_date:  # кілька курсів (W + L) на одну дату — об'єднуємо
            x = by_date[it["date"]]
            x["topics"] += [t for t in it["topics"] if t not in x["topics"]]
            x["links"] += it["links"]
        else:
            by_date[it["date"]] = {**it}
    clean = sorted(by_date.values(), key=lambda x: x["date"])
    if [(i["date"], i["title"]) for i in clean] == [(i.get("date"), i.get("title")) for i in cur.get("items", [])] \
            and cur.get("source") == "eportal":
        return False
    storage.write_json(d / "plan.json", {"updated_at": storage.now_iso(), "source": "eportal", "items": clean})
    return True


# ---------------------------------------------------------------- sync
def sync() -> dict:
    from . import materials
    from .schedule import load_schedule
    d = load()
    if not d.get("token"):
        return public_status()
    _state["running"] = True
    stats = {"courses": 0, "plans": 0, "files": 0, "skipped_protected": 0}
    try:
        token = d["token"]
        uid = d.get("userid") or _call("core_webservice_get_site_info").get("userid")
        courses = _call("core_enrol_get_users_courses", userid=uid) or []
        subjects = load_schedule()["subjects"]
        sids = {s["id"] for s in subjects}
        today = time.time()
        cur = [c for c in courses if not c.get("enddate") or c["enddate"] > today - 120 * 86400]
        d["courses"] = [{"id": c["id"], "fullname": c.get("fullname", ""), "shortname": c.get("shortname", "")} for c in cur]
        for c in cur:
            key = str(c["id"])
            if key not in d["course_map"] or (d["course_map"][key] and d["course_map"][key] not in sids):
                d["course_map"][key] = match_subject(c, subjects) or ""
        plan_items: dict[str, list] = {}
        for c in cur:
            sid = d["course_map"].get(str(c["id"]))
            if not sid or sid not in sids:
                continue
            stats["courses"] += 1
            sections = _call("core_course_get_contents", courseid=c["id"]) or []
            plan_items.setdefault(sid, []).extend(build_plan(sections))
            folder = materials.subject_dir(sid) / "files"
            for sec in sections:
                for m in sec.get("modules", []):
                    if m.get("modname") not in DOWNLOAD_MODS:
                        if m.get("modname") in ("securepdf",):
                            stats["skipped_protected"] += 1
                        continue
                    for f in m.get("contents") or []:
                        if f.get("type") != "file" or not f.get("fileurl"):
                            continue
                        fk = f"{c['id']}:{m.get('id')}:{f.get('filepath', '/')}{f.get('filename', '')}"
                        rec = d["files"].get(fk)
                        info = {"subject_id": sid, "course_id": c["id"], "course_type": course_type(c),
                                "section": (sec.get("name") or "")[:200], "module": (m.get("name") or "")[:200],
                                "filename": f.get("filename", ""), "uploaded": f.get("timecreated") or f.get("timemodified")}
                        if rec and rec.get("timemodified") == f.get("timemodified"):
                            rec.update(info)  # уже скачано (або користувач видалив — не повертаємо)
                            continue
                        if (f.get("filesize") or 0) > MAX_FILE:
                            d["files"][fk] = {"timemodified": f.get("timemodified"), "saved": "", "note": "too big"}
                            continue
                        name = storage.safe_filename(f.get("filename") or "file")
                        target = folder / rec["saved"] if rec and rec.get("saved") else storage.unique_path(folder, name)
                        try:
                            _download(f["fileurl"], target, token)
                            d["files"][fk] = {**info, "timemodified": f.get("timemodified"), "saved": target.name}
                            stats["files"] += 1
                        except MoodleError as e:
                            d["files"][fk] = {**info, "timemodified": f.get("timemodified"), "saved": "", "note": str(e)}
                        _save(d)
        for sid, items in plan_items.items():
            if items and _write_plan(sid, items):
                stats["plans"] += 1
        _save(d)
        try:
            _sync_deadlines(d, cur)
        except MoodleError as e:
            applog.error("eportal deadlines", e)
        try:
            stats["attached"] = attach_recent()
        except Exception as e:
            applog.error("eportal attach", e)
        msg = f"Курсів: {stats['courses']}, нових файлів: {stats['files']}, планів оновлено: {stats['plans']}"
        if stats["skipped_protected"]:
            msg += f", захищених PDF пропущено: {stats['skipped_protected']}"
        unmatched = sum(1 for c in cur if not d["course_map"].get(str(c["id"])))
        if unmatched:
            msg += f". Не прив'язано курсів: {unmatched}"
        d.update(synced_at=storage.now_iso(), status="ok", message=msg, last_stats=stats)
    except MoodleError as e:
        d.update(status="expired" if e.code == "invalidtoken" else "error", message=str(e)[:300])
        if e.code == "invalidtoken":
            d.pop("token", None)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        d.update(status="error", error_at=time.time(), message=f"Немає зв'язку з ePortalem: {e}")
    except Exception as e:
        d.update(status="error", error_at=time.time(), message=str(e)[:300])
    finally:
        _save(d)
        _state["running"] = False
        applog.event("eportal_sync", ok=d.get("status") == "ok", msg=str(d.get("message") or "")[:200],
                     files=stats.get("files", 0), attached=stats.get("attached", 0))
    return public_status()


def sync_async() -> None:
    if _state["running"]:
        return
    _state["running"] = True
    threading.Thread(target=lambda: (_state.update(running=False), sync()), daemon=True, name="eportal-sync").start()


def due() -> bool:
    d = load()
    if not d.get("token") or _state["running"]:
        return False
    if d.get("status") == "error" and time.time() - float(d.get("error_at") or 0) < 1800:
        return False  # після помилки — пауза 30 хв, щоб не смикати сервер
    if any("section" not in f for f in d.get("files", {}).values()) or "deadlines_at" not in d:
        return True  # оновлення 1.5: дозбираємо назви розділів і дедлайни
    try:
        return time.time() - datetime.fromisoformat(d.get("synced_at")).timestamp() > 12 * 3600
    except Exception:
        return True


# ---------------------------------------------------------------- course type
def course_type(c: dict) -> str:
    """«W04ITE-SI0011G # L # …» → L; або за словами «Wykład / Laboratorium / Projekt / Ćwiczenia»."""
    hay = f"{c.get('fullname', '')} {c.get('shortname', '')}"
    m = re.search(r"#\s*([WLPCS])\s*#", hay)
    if m:
        return m.group(1)
    n = _norm(hay)
    for word, t in (("wyklad", "W"), ("laborator", "L"), ("projekt", "P"), ("cwiczen", "C"), ("seminar", "S")):
        if word in n:
            return t
    return ""


# ---------------------------------------------------------------- deadlines
DEADLINES_FILE = storage.DATA_DIR / "deadlines.json"   # ручні дедлайни й «виконано»


def _sync_deadlines(d: dict, courses: list[dict]) -> None:
    now = int(time.time())
    events, after = [], 0
    for _ in range(5):  # сторінками по 20: ePortal відкидав limitnum=50 («Limit must be between 1 and 50»)
        params = {"timesortfrom": now - 14 * 86400, "timesortto": now + 120 * 86400, "limitnum": 20}
        if after:
            params["aftereventid"] = after
        page = (_call("core_calendar_get_action_events_by_timesort", **params) or {}).get("events", [])
        events += page
        if len(page) < 20:
            break
        after = page[-1].get("id") or 0
    out = []
    for e in events:
        cid = str((e.get("course") or {}).get("id") or e.get("courseid") or "")
        out.append({"id": f"ep{e.get('id')}", "title": e.get("activityname") or e.get("name") or "",
                    "what": e.get("name") or "", "due": datetime.fromtimestamp(e.get("timesort") or e.get("timestart") or now)
                    .astimezone().isoformat(timespec="minutes"),
                    "course": (e.get("course") or {}).get("fullname", ""), "subject_id": d["course_map"].get(cid) or "",
                    "module": e.get("modulename", ""), "url": e.get("url") or (e.get("action") or {}).get("url", ""),
                    "action": (e.get("action") or {}).get("name", ""), "source": "eportal"})
    d["deadlines"] = out
    d["deadlines_at"] = storage.now_iso()
    _save(d)
    applog.event("eportal_deadlines", ok=True, count=len(out))


def deadlines_due() -> bool:
    d = load()
    if not d.get("token") or _state["running"]:
        return False
    try:
        return time.time() - datetime.fromisoformat(d.get("deadlines_at")).timestamp() > 3600
    except Exception:
        return True


def refresh_deadlines() -> None:
    def run():
        d = load()
        try:
            _sync_deadlines(d, d.get("courses", []))
        except Exception as e:
            applog.error("eportal deadlines", e)
            applog.event("eportal_deadlines", ok=False, msg=str(e)[:200])
            d = load()
            d["deadlines_at"] = storage.now_iso()  # спроба була — наступна через годину, а не щотику сканера
            _save(d)
    threading.Thread(target=run, daemon=True, name="eportal-deadlines").start()


def list_deadlines() -> list[dict]:
    loc = storage.read_json(DEADLINES_FILE, {}) or {}
    done = set(loc.get("done", []))
    from . import semester
    items = list(load().get("deadlines", [])) + list(loc.get("manual", [])) + _lecture_todos() + semester.exam_deadlines()
    for it in items:
        it["done"] = it["id"] in done
    items.sort(key=lambda x: x.get("due") or "")
    return items


def _lecture_todos() -> list[dict]:
    """Завдання, які Claude виписав з заняття (result.json → todos) і з плану до лаби (plan.json → todos) — теж дедлайни."""
    out = []
    if not storage.LECTURES_DIR.exists():
        return out
    for d in storage.LECTURES_DIR.iterdir():
        res = storage.read_json(d / "output" / "result.json", {}) if (d / "output" / "result.json").exists() else {}
        todos = [(f"lec:{d.name}:{i}", t) for i, t in enumerate(res.get("todos") or [])] \
            if isinstance(res, dict) and isinstance(res.get("todos"), list) else []
        pj = storage.read_json(d / "output" / "plan.json", {}) if (d / "output" / "plan.json").exists() else {}
        if isinstance(pj, dict) and isinstance(pj.get("todos"), list):  # 2.1: дедлайни з плану до заняття
            titles = {str(t.get("title") or "").strip().lower() for _, t in todos if isinstance(t, dict)}
            for t in pj["todos"]:
                k = str(t.get("title") or "").strip().lower() if isinstance(t, dict) else ""
                if k and k not in titles:
                    todos.append((f"lecp:{d.name}:{hashlib.sha1(k.encode('utf-8')).hexdigest()[:8]}", t))
                    titles.add(k)
        if not todos:
            continue
        meta = storage.read_json(d / "meta.json", {}) or {}
        for tid, t in todos[:30]:
            if not isinstance(t, dict):
                continue
            due = str(t.get("due") or "")[:16]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?", due):
                continue
            out.append({"id": tid, "title": str(t.get("title") or "")[:200], "due": due if "T" in due else due + "T23:59",
                        "subject_id": meta.get("subject_id", ""), "what": str(t.get("what") or "")[:200],
                        "url": f"#/lecture/{d.name}", "source": "lecture", "est_min": t.get("est_min")})
    return out


def add_deadline(body: dict) -> list[dict]:
    title = str(body.get("title") or "").strip()[:200]
    due = str(body.get("due") or "").strip()[:16]
    if not title or not re.fullmatch(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?", due):
        raise ValueError("Вкажіть назву і дату")
    if "T" not in due:
        due += "T23:59"
    with _lock:
        loc = storage.read_json(DEADLINES_FILE, {}) or {}
        loc.setdefault("manual", []).append({"id": "m" + secrets.token_hex(4), "title": title, "due": due,
                                             "subject_id": str(body.get("subject_id") or ""), "what": str(body.get("what") or "")[:200],
                                             "source": "manual"})
        storage.write_json(DEADLINES_FILE, loc)
    return list_deadlines()


def set_deadline(did: str, done: bool | None = None, delete: bool = False) -> list[dict]:
    with _lock:
        loc = storage.read_json(DEADLINES_FILE, {}) or {}
        if delete:
            loc["manual"] = [x for x in loc.get("manual", []) if x["id"] != did]
        if done is not None:
            s = set(loc.get("done", []))
            (s.add if done else s.discard)(did)
            loc["done"] = sorted(s)
        storage.write_json(DEADLINES_FILE, loc)
    return list_deadlines()


# ---------------------------------------------------------------- slides → lecture
def _lecture_ordinal(meta: dict) -> int:
    """Котра це лекція (заняття цього типу) з предмета: за USOS, інакше за лекціями в застосунку."""
    from . import usos, lectures
    sid, typ, ds = meta.get("subject_id"), meta.get("type") or "W", meta.get("date") or ""
    evs = usos.load().get("events", [])
    dates = sorted({e["date"] for e in evs if e.get("subject_id") == sid and e.get("type") == typ})
    if dates:
        return sum(1 for x in dates if x <= ds) or 1
    others = [m for m in lectures.list_all() if m.get("subject_id") == sid and m.get("type") == typ]
    return sum(1 for m in others if (m.get("date") or "") <= ds) or 1


def _date_variants(ds: str) -> list[str]:
    try:
        dt = date.fromisoformat(ds)
    except Exception:
        return []
    return [dt.isoformat(), dt.strftime("%d.%m.%Y"), dt.strftime("%d.%m.%y"), dt.strftime("%Y%m%d"),
            dt.strftime("%d-%m-%Y"), dt.strftime("%d_%m_%Y"), f"{dt.day}.{dt.month}.{dt.year}", dt.strftime("%d.%m")]


# ---------------------------------------------------------------- 2.1: підбір файлів до заняття за змістом
TEXT_CACHE = "eportal_text.json"   # data/cache/ — ключові слова файлів (щоб не читати PDF щоразу)
_STOP = set("""
oraz ktore ktory ktora ktorych ktorym jest beda bedzie mozna moze takze tylko przez przy jako jakie jaki jesli jezeli
ponizej powyzej zadanie zadania zadan strona stron slajd slajdy wyklad wykladu wyklady laboratorium cwiczenie cwiczenia
projekt projektu politechnika wroclawska wydzial katedra prowadzacy student studenci semestr przedmiot materialy plik
temat tematy czesc punkt punkty przyklad przyklady rysunek tabela nalezy naszego naszej swoje sobie wszystkie wszystkich
ktorego kazdy kazda kazde innych inne inny takie tutaj teraz wtedy gdzie kiedy dlaczego wiecej mniej bardzo dobrze
these those which there their about after before between other using based figure table example lecture chapter
""".split())


def _kw(text: str, top: int = 120) -> dict[str, int]:
    """Ключові слова тексту: без діакритики, ≥5 літер, без стоп-слів, «основа» = перші 7 літер."""
    import unicodedata
    t = unicodedata.normalize("NFKD", (text or "").lower().replace("ł", "l"))
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    cnt: dict[str, int] = {}
    for w in re.findall(r"[a-z]{5,}", t):
        if w in _STOP:
            continue
        k = w[:7]
        cnt[k] = cnt.get(k, 0) + 1
    return dict(sorted(cnt.items(), key=lambda x: -x[1])[:top])


def _file_text(p: Path, limit: int = 30000) -> str:
    ext = p.suffix.lower()
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            r = PdfReader(str(p))
            out = []
            for pg in r.pages[:6]:
                out.append(pg.extract_text() or "")
                if sum(map(len, out)) > limit:
                    break
            return "\n".join(out)[:limit]
        if ext in (".pptx", ".docx", ".odp", ".odt"):
            import zipfile
            with zipfile.ZipFile(p) as z:
                names = sorted(n for n in z.namelist() if re.match(r"(ppt/slides/slide\d+|word/document|content)\.xml$", n))[:15]
                xml = " ".join(z.read(n).decode("utf-8", "replace") for n in names)
            return re.sub(r"<[^>]+>", " ", xml)[:limit]
        if ext in (".txt", ".md", ".html", ".htm", ".csv"):
            return p.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception as e:
        applog.error("eportal text", p.name, e)
    return ""


def _file_kw(sid: str, saved: str) -> dict[str, int]:
    p = storage.DATA_DIR / "subjects" / sid / "files" / saved
    if not p.exists():
        return {}
    cache_p = storage.DATA_DIR / "cache" / TEXT_CACHE
    cache = storage.read_json(cache_p, {}) or {}
    key = f"{sid}/{saved}"
    st = p.stat()
    rec = cache.get(key)
    if rec and rec.get("mtime") == int(st.st_mtime) and rec.get("size") == st.st_size:
        return rec.get("kw") or {}
    kw = _kw(_file_text(p))
    cache[key] = {"mtime": int(st.st_mtime), "size": st.st_size, "kw": kw}
    try:
        cache_p.parent.mkdir(parents=True, exist_ok=True)
        storage.write_json(cache_p, cache)
    except OSError:
        pass
    return kw


def _lecture_kw(meta: dict) -> dict[str, int]:
    """Про що заняття → {слово: вага}: тема з плану, назви й теми з result.json, нотатки (вага 3), початок розшифровки (1)."""
    from . import materials
    d = storage.LECTURES_DIR / meta["id"]
    strong = [meta.get("title") or "", meta.get("user_notes") or ""]
    pi = materials.plan_item(meta.get("subject_id"), meta.get("date")) or {}
    strong += [pi.get("title") or ""] + [str(x) for x in pi.get("topics") or []]
    res = storage.read_json(d / "output" / "result.json", {}) if (d / "output" / "result.json").exists() else {}
    if isinstance(res, dict):
        strong += [str(res.get("title") or "")] + [str(x) for x in res.get("topics") or []]
    weak = ""
    tr = d / "transcript.txt"
    if tr.exists():
        try:
            weak = tr.read_text(encoding="utf-8", errors="replace")[:8000]
        except OSError:
            pass
    out = {w: 1 for w in _kw(weak, top=150)}
    for w in _kw("\n".join(strong), top=60):
        out[w] = 3
    return out


TASK_RX = re.compile(r"lab|instrukc|zadani|cwiczen|ćwiczen|projekt|etap|lista|sprawozd|task|assignment", re.I)


def is_task_file(f: dict, lecture_type: str) -> bool:
    """Для лаб/проєктів/вправ файл з ePortalu — це умова завдання (task/), а не слайди."""
    if lecture_type not in ("L", "P", "C", "S"):
        return False
    ct = f.get("course_type") or ""
    if ct and ct == lecture_type:
        return True
    return bool(TASK_RX.search(f"{f.get('section', '')} {f.get('module', '')} {f.get('filename') or f.get('saved', '')}"))


def candidates(lid: str, with_content: bool = True) -> list[dict]:
    from . import lectures
    meta = lectures.read_meta(lid)
    sid, typ, ds = meta.get("subject_id"), meta.get("type") or "W", meta.get("date") or ""
    if not sid:
        return []
    n = _lecture_ordinal(meta)
    mn = re.search(r"(?i)\b(?:lab\w*|laboratorium|ćw\w*|cw\w*|projekt\w*|etap\w*|temat\w*|lista)\s*(?:nr\.?|№|#)?\s*(\d{1,2})\b",
                   f"{meta.get('title') or ''} {meta.get('user_notes') or ''}")
    if mn:
        n = int(mn.group(1))  # студент сам написав «Lab 3» — це точніше за порядковий номер
    attached = set(meta.get("eportal_attached", []))
    try:
        day_ts = datetime.fromisoformat(ds + "T12:00").timestamp()
    except Exception:
        day_ts = 0
    out = []
    for fk, f in load().get("files", {}).items():
        if f.get("subject_id") != sid or not f.get("saved"):
            continue
        name = f"{f.get('section', '')} | {f.get('module', '')} | {f.get('filename') or f['saved']}"
        low = name.lower()
        score, why = 0.0, []
        ct = f.get("course_type") or ""
        if ct and ct != typ:
            score -= 2
        elif ct == typ:
            score += 0.5
        if any(v in name for v in _date_variants(ds)[:7]):
            score += 4; why.append("дата")
        pref = {"W": "w|wyk|wyklad|wykład|lecture|lec|lect", "L": "l|lab|laboratorium|lista|cw|ćw|ćwiczenie|cwiczenie",
                "C": "c|cw|ćw|cwiczenia|ćwiczenia|lista", "P": "p|proj|projekt|etap", "S": "s|sem|seminarium"}.get(typ, "w")
        rx_n = rf"(?:\b|_)(?:{pref}|temat|t|cz|część|nr|zajecia|zajęcia|#)[ ._-]*0*{n}(?!\d)"
        if re.search(rx_n, low):
            score += 3; why.append(f"№{n}")
        elif re.search(rf"(?:^|[\s|_(\[-])0*{n}(?:[ ._)\]-]|$)", low):
            score += 1; why.append(f"число {n}")
        up = f.get("uploaded") or f.get("timemodified") or 0
        if day_ts and up and -4 * 86400 <= up - day_ts <= 1.5 * 86400:
            score += 1.5; why.append("додано біля дати заняття")
        p = storage.DATA_DIR / "subjects" / sid / "files" / f["saved"]
        if not p.exists():
            continue
        out.append({"key": fk, "file": f["saved"], "section": f.get("section", ""), "module": f.get("module", ""),
                    "course_type": ct, "score": score, "why": why, "attached": fk in attached,
                    "size": p.stat().st_size, "as_task": is_task_file(f, typ),
                    "uploaded": up})
    if with_content and out:
        _content_scores(meta, sid, out)
        if not mn:
            _fix_ordinal(out, n, pref)
    for x in out:
        x["score"] = round(x["score"], 1)
    out.sort(key=lambda x: (-x["score"], x["file"]))
    return out


def _fix_ordinal(out: list[dict], n: int, pref: str) -> None:
    """Порядковий номер з USOS буває зсунутий (перше заняття — організаційне). Якщо лідер за змістом має у назві
    свій номер («[1] …», «Lab1 …») і він інший, то бонус «№n» у решти файлів хибний — знімаємо його."""
    lead = [x for x in out if any(w.startswith("зміст:") for w in x["why"])]
    if len(lead) != 1:
        return
    k = 0
    for s in (lead[0]["file"], lead[0]["section"]):  # «[1] Szacowanie pasma.pdf», розділ «Temat 1: …»
        m = re.search(rf"^\s*[\[(]0*(\d{{1,2}})[a-z]?[\])]|(?:\b|_)(?:{pref}|temat|nr|zajecia|zajęcia)[ ._-]*0*(\d{{1,2}})(?!\d)",
                      (s or "").lower())
        if m:
            k = int(m.group(1) or m.group(2))
            break
    if not k or k == n:
        return
    for x in out:
        for w, pts in ((f"№{n}", 3), (f"число {n}", 1)):
            if w in x["why"]:
                x["score"] -= pts
                x["why"] = [y for y in x["why"] if y != w] + [f"{w} не збігається зі змістом (№{k})"]


def _content_scores(meta: dict, sid: str, out: list[dict]) -> None:
    """Збіг ключових слів файлу з темою заняття. Вага слова = рідкісність серед файлів предмета (idf) × вага в темі
    заняття (назва/план/теми = 3, розшифровка = 1) × вага у файлі (назва файлу = 2, текст = 1)."""
    import math
    lk = _lecture_kw(meta)
    if len(lk) < 4:
        return
    typ = meta.get("type") or "W"
    pool = [x for x in out if not x.get("course_type") or x["course_type"] == typ]  # файли іншого типу заняття не змагаються
    if not pool:
        return
    kws = {}
    for x in pool:
        k = {w: 1 for w in _file_kw(sid, x["file"])}
        for w in _kw(f"{x.get('module', '')} {x['file']}", top=30):
            k[w] = 2
        kws[x["key"]] = k
    nfiles = max(1, len(kws))
    df: dict[str, int] = {}
    for k in kws.values():
        for w in k:
            df[w] = df.get(w, 0) + 1
    sc = {}
    for x in pool:
        fk = kws[x["key"]]
        shared = [w for w in fk if w in lk]
        sc[x["key"]] = (sum(math.log(1 + nfiles / df[w]) * lk[w] * fk[w] for w in shared), shared)
    best = max((v for v, _ in sc.values()), default=0)
    if best <= 0:
        return
    top = [k for k, (v, sh) in sc.items() if v >= 0.75 * best and len(sh) >= 3]
    max_top = 1 if typ in ("L", "P", "C", "S") else 2  # умова лаби — лише явний лідер (вона одразу запускає план)
    if max_top == 1 and len(top) > 1:
        vals = sorted((v for v, _ in sc.values()), reverse=True)
        top = top[:0] if vals[1] * 1.25 > vals[0] else [k for k, (v, _) in sc.items() if v == best]
    for x in pool:
        v, shared = sc[x["key"]]
        if v <= 0 or len(shared) < 3:
            continue
        label = ", ".join(sorted(shared, key=lambda w: -lk[w] * kws[x["key"]][w])[:4])
        if x["key"] in top and len(top) <= max_top and v >= 12:
            x["score"] += 3; x["why"].append("зміст: " + label)
        elif v >= 0.5 * best and v >= 6:
            x["score"] += 1; x["why"].append("схожий зміст: " + label)


def attach(lid: str, key: str, as_task: bool | None = None) -> dict:
    from . import compact, course, lectures
    f = load().get("files", {}).get(key)
    if not f or not f.get("saved"):
        raise KeyError(key)
    src = storage.DATA_DIR / "subjects" / f["subject_id"] / "files" / f["saved"]
    if not src.exists():
        raise KeyError(key)
    meta0 = lectures.read_meta(lid)
    if as_task is None:
        as_task = is_task_file(f, meta0.get("type") or "W")
    kind = "task" if as_task else lectures.kind_of(src.name)
    if kind == "audio":
        kind = "other"
    folder = storage.LECTURES_DIR / lid / lectures.KIND_DIRS[kind]
    folder.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(src.read_bytes()).hexdigest()
    added = []

    def fn(m):
        att = m.setdefault("eportal_attached", [])
        if key not in att:
            att.append(key)
        seen = m.setdefault("eportal_seen", [])
        if key not in seen:
            seen.append(key)
        if any(x.get("sha256") == h for x in m["files"]):
            return
        target = storage.unique_path(folder, src.name)
        compact.link_or_copy(src, target)  # той самий файл — без другої копії на диску
        m["files"].append({"name": target.name, "kind": kind, "size": target.stat().st_size, "sha256": h,
                           "added_at": storage.now_iso(), "source": "eportal"})
        added.append(target.name)
    meta = lectures.mutate(lid, fn)
    if added and kind == "task":
        try:
            course.on_task_added(lid)  # 2.1: нова умова з ePortalu → план у черзі Claude
        except Exception as e:
            applog.error("plan", e)
        meta = lectures.read_meta(lid)
    return meta


def _seen_keys(meta: dict) -> set[str]:
    seen = set(meta.get("eportal_seen") or [])
    if not seen and meta.get("eportal_auto_done"):  # 2.0 → 2.1: усе, що було на ePortalu до попередньої перевірки
        try:
            ts = datetime.fromisoformat(meta["eportal_auto_done"]).timestamp()
        except Exception:
            ts = 0
        seen = {k for k, f in load().get("files", {}).items()
                if f.get("subject_id") == meta.get("subject_id") and (f.get("uploaded") or f.get("timemodified") or 0) <= ts}
    return seen | set(meta.get("eportal_attached") or [])


def auto_attach(lid: str) -> int:
    """Прикріплює найімовірніші файли (бал ≥ 3 і явний лідер) — лише з тих, що ще не розглядались для цього заняття.
    Для вже обробленого заняття — ще й позначка «нові матеріали з ePortalu» (оновлення конспекту — кнопкою)."""
    from . import lectures
    meta = lectures.read_meta(lid)
    seen = _seen_keys(meta)
    has_content = len(_lecture_kw(meta)) >= 4
    if has_content and not meta.get("eportal_content_checked"):
        seen = set(meta.get("eportal_attached") or [])  # з'явилась тема/розшифровка — переглянути все ще раз за змістом
    c = [x for x in candidates(lid) if x["key"] not in seen]
    if not c:
        if has_content and not meta.get("eportal_content_checked"):
            lectures.mutate(lid, lambda m: m.__setitem__("eportal_content_checked", storage.now_iso()))
        return 0
    own_slides = any(f.get("kind") == "slides" and f.get("source") != "eportal" for f in meta.get("files", []))
    good = [x for x in c if x["score"] >= 3 and (x["as_task"] or not own_slides)]  # свої слайди вже є — слайди не дублюємо
    if (meta.get("type") or "W") == "P":  # 2.4: до зустрічі проєкту — лише умови/вимоги, не підручники й слайди
        good = [x for x in good if x["as_task"]]
    n, names = 0, []
    if good:
        top = good[0]["score"]
        for x in good:
            if x["score"] >= top - 0.5 and not x["attached"]:
                attach(lid, x["key"])
                n += 1
                names.append(x["file"])
    was_done = lectures.enrich(meta)["status"] == "done"

    def fn(m):
        s2 = set(m.get("eportal_seen") or []) | seen | {x["key"] for x in c}
        m["eportal_seen"] = sorted(s2)
        m["eportal_auto_done"] = storage.now_iso()
        if has_content:
            m["eportal_content_checked"] = m.get("eportal_content_checked") or storage.now_iso()
        if names and was_done:
            new = m.setdefault("eportal_new", [])
            for nm in names:
                if not any(e.get("name") == nm for e in new):
                    new.append({"name": nm, "at": storage.now_iso()})
    lectures.mutate(lid, fn)
    return n


def eportal_new_action(lid: str, action: str) -> dict:
    """«Нові матеріали з ePortalu» на обробленому занятті: update — у чергу Claude на оновлення, dismiss — сховати."""
    from . import lectures
    meta = lectures.read_meta(lid)
    names = [e.get("name") for e in meta.get("eportal_new") or [] if e.get("name")]
    lectures.mutate(lid, lambda m: m.pop("eportal_new", None))
    if action == "update" and names:
        instr = ((meta.get("claude") or {}).get("instructions") or "").strip()
        add = ("Z ePortalu doszły nowe materiały: " + ", ".join(names) +
               ". Zaktualizuj konspekt/przewodnik i karty (zachowaj postęp przez \"prev\"), uwzględniając te pliki.")
        lectures.request_claude(lid, (instr + "\n" + add).strip() if add not in instr else instr)
    return lectures.read_meta(lid)


def attach_recent(days: int = 30) -> int:
    """Після синхронізації: заняття за останні дні отримують нові підхожі файли з ePortalu (і вже оброблені теж)."""
    from . import lectures
    n = 0
    limit = (date.today().toordinal() - days)
    for m in lectures.list_all():
        try:
            if date.fromisoformat(m.get("date") or "1970-01-01").toordinal() < limit:
                continue
        except ValueError:
            continue
        try:
            n += auto_attach(m["id"])
        except Exception as e:
            applog.error("auto_attach", m["id"], e)
    return n