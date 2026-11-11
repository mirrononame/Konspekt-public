"""Синхронізація розкладу з USOSweb PWr за посиланням «udostępnij plan» (з токеном).

Посилання має вигляд
    https://web.usos.pwr.edu.pl/kontroler.php?_action=katalog2/osoby/pokazPlanZajecStudenta&token=…
Сторінка показує план одного тижня; інший тиждень — параметр &plan_week_sel_week=YYYY-MM-DD.
Ми проходимо всі тижні семестру й зберігаємо **конкретні дати** занять — тож парні/непарні
тижні, свята й перенесення враховуються автоматично.

Дані: data/usos.json (без посилання), посилання з токеном — secrets/usos_url.json  {url, synced_at, weeks:[понеділки], events:[…], status, message}
"""
from __future__ import annotations

import html as htmllib
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from . import applog, storage

USOS_FILE = storage.DATA_DIR / "usos.json"           # розклад з USOS — Claude теж його читає
URL_FILE = storage.SECRETS_DIR / "usos_url.json"      # 2.7: посилання з токеном — окремо, поза data
DAYS_PL = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
TYPE_MAP = {"W": "W", "L": "L", "P": "P", "C": "C", "S": "S", "E": "W"}
_state = {"running": False}
_lock = threading.Lock()


def load() -> dict:
    d = storage.read_json(USOS_FILE, {}) or {}
    if d.get("url"):  # формат до 2.7: токен лежав у data/usos.json
        _save(d)
        storage.write_json(USOS_FILE, {k: v for k, v in d.items() if k != "url"})  # вдруге — щоб і .bak був без токена
    d["url"] = (storage.read_json(URL_FILE, {}) or {}).get("url")
    d.setdefault("events", [])
    d.setdefault("weeks", [])
    return d


def _save(d: dict) -> None:
    storage.write_json(URL_FILE, {"url": d.get("url")})
    storage.write_json(USOS_FILE, {k: v for k, v in d.items() if k != "url"})


def public_status() -> dict:
    d = load()
    return {"connected": bool(d.get("url")), "synced_at": d.get("synced_at"), "status": d.get("status", "idle"),
            "message": d.get("message", ""), "events": len(d["events"]), "weeks": len(d["weeks"]),
            "running": _state["running"], "first": min((e["date"] for e in d["events"]), default=None),
            "last": max((e["date"] for e in d["events"]), default=None)}


def validate_url(url: str) -> str:
    url = (url or "").strip()
    p = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(p.query)
    if p.scheme != "https" or not (p.netloc == "usos.pwr.edu.pl" or p.netloc.endswith(".usos.pwr.edu.pl")) or "token" not in q:
        raise ValueError("Це не схоже на посилання «Udostępnij plan» з USOSweb PWr (потрібен https://web.usos.pwr.edu.pl/…&token=…)")
    # прибираємо вибраний тиждень, якщо користувач скопіював його разом із посиланням
    q.pop("plan_week_sel_week", None)
    return urllib.parse.urlunparse(p._replace(query=urllib.parse.urlencode({k: v[0] for k, v in q.items()}, safe="/")))


def connect(url: str) -> dict:
    url = validate_url(url)
    with _lock:
        d = load()
        d["url"] = url
        d["status"] = "pending"
        _save(d)
    sync_async()
    return public_status()


def disconnect() -> dict:
    with _lock:
        _save({"events": [], "weeks": []})
    return public_status()


# ---------------------------------------------------------------- fetch & parse
_opener = None


def _fetch(url: str) -> str:
    """USOSweb спочатку ставить cookie сесії й робить редирект — тому потрібен «браузер» з cookies."""
    global _opener
    import http.cookiejar
    if _opener is None:
        _opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "pl,en;q=0.8"})
    # USOS іноді віддає 502/503/504 (перевантаження, оновлення) або 429 — пробуємо ще кілька разів з паузою
    delays = [3, 8, 20]
    for attempt in range(len(delays) + 1):
        try:
            with _opener.open(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == len(delays):
                raise
            try:
                wait = min(60, int(e.headers.get("Retry-After") or delays[attempt]))
            except ValueError:
                wait = delays[attempt]
        except (urllib.error.URLError, TimeoutError):
            if attempt == len(delays):
                raise
            wait = delays[attempt]
        time.sleep(wait)


def _text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", htmllib.unescape(s)).strip()


def parse_week(page: str, monday: date) -> list[dict]:
    """Розбирає <usos-timetable>: заголовки днів <h4> і блоки <timetable-entry>."""
    m = re.search(r"<usos-timetable[\s\S]*?</usos-timetable>", page)
    if not m:
        if "pokazPlanZajecStudenta" not in page and "timetable" not in page:
            raise ValueError("Сторінка USOS не містить плану (можливо, посилання застаріло)")
        return []
    tt = m.group(0)
    events = []
    parts = re.split(r"<h4[^>]*>", tt)[1:]
    for part in parts:
        day_name = _text(part.split("</h4>", 1)[0]).lower()
        if day_name not in DAYS_PL:
            continue
        d = monday + timedelta(days=DAYS_PL.index(day_name))
        for em in re.finditer(r"<timetable-entry([^>]*)>([\s\S]*?)</timetable-entry>", part):
            attrs, body = em.group(1), em.group(2)
            name = htmllib.unescape(re.search(r'\bname="([^"]*)"', attrs).group(1)) if 'name="' in attrs else ""
            code = (re.search(r'name-id="([^"]*)"', attrs) or [None, ""])[1]
            info = _text((re.search(r'slot="info"[^>]*>([\s\S]*?)</div>', body) or [None, ""])[1])
            ev = _text((re.search(r'slot="dialog-event"[^>]*>([\s\S]*?)</span>', body) or [None, ""])[1])
            tm = re.findall(r"(\d{1,2}):(\d{2})", ev)
            if len(tm) < 2:
                t0 = re.search(r'slot="time"[^>]*>(\d{1,2}):(\d{2})', body)
                if not t0:
                    continue
                tm = [t0.groups(), t0.groups()]
            start = f"{int(tm[0][0]):02d}:{tm[0][1]}"
            end = f"{int(tm[1][0]):02d}:{tm[1][1]}"
            im = re.match(r"\s*([A-ZŁ]+)\s*,?\s*(?:gr\.\s*(\d+))?\s*(?:\((.*)\))?", info)
            typ = TYPE_MAP.get((im.group(1) if im else "W")[:1], "W")
            group = im.group(2) if im else ""
            place = (im.group(3) or "") if im else ""
            room = place.replace(", bud.", " bud.").strip()
            pm = re.search(r'slot="dialog-person"[^>]*>([\s\S]*?)</div>', body)
            lecturers = []
            if pm:
                anchors = re.findall(r"<a\b[^>]*>([\s\S]*?)</a>", pm.group(1))
                raw = [_text(a) for a in anchors] if anchors else re.split(r",\s*", _text(pm.group(1)))
                lecturers = [l.strip(" ,") for l in raw if l.strip(" ,")]
            link = re.search(r'slot="dialog-info"[\s\S]*?href=["\']([^"\']+)', body)
            kind = _text((re.search(r'slot="dialog-info"[^>]*>([\s\S]*?)</span>', body) or [None, ""])[1])
            events.append({
                "date": d.isoformat(), "start": start, "end": end, "name": name, "code": code,
                "type": typ, "group": group, "room": room, "lecturers": lecturers, "kind": kind,
                "url": htmllib.unescape(link.group(1)) if link else "",
            })
    return events


def _week_url(url: str, monday: date) -> str:
    return url + ("&" if "?" in url else "?") + "plan_week_sel_week=" + monday.isoformat()


def sync(max_weeks: int = 26) -> dict:
    """Повна синхронізація (у фоні). Тижні: від початку семестру до 4 порожніх тижнів поспіль."""
    from .schedule import load_settings
    d = load()
    url = d.get("url")
    if not url:
        return public_status()
    _state["running"] = True
    global _opener
    _opener = None  # нова сесія USOS на кожну синхронізацію
    try:
        today = date.today()
        try:
            sem = date.fromisoformat(load_settings().get("semester_start"))
        except Exception:
            sem = today
        start = min(sem, today) - timedelta(days=min(sem, today).weekday())
        events, weeks, empty_run, seen_any, partial = [], [], 0, False, ""
        for i in range(max_weeks):
            monday = start + timedelta(weeks=i)
            try:
                page = _fetch(_week_url(url, monday))
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if not events:
                    raise
                partial = f" (частково: USOS перестав відповідати на тижні {monday.isoformat()} — {e})"
                break
            ev = parse_week(page, monday)
            weeks.append(monday.isoformat())
            events.extend(ev)
            if ev:
                seen_any, empty_run = True, 0
            else:
                empty_run += 1
                if seen_any and empty_run >= 4 and monday > today:
                    break
            time.sleep(1.0)  # чемно щодо сервера USOS (частіші запити він може відкидати з 503)
        if not events:
            raise ValueError("У плані немає жодного заняття. Перевірте посилання.")
        d.update(events=events, weeks=weeks, synced_at=storage.now_iso(), status="ok",
                 message=f"Завантажено {len(events)} занять за {len(weeks)} тижнів{partial}")
        _save(d)
        apply_to_schedule(events)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        code = getattr(e, "code", None)
        if code in (429, 500, 502, 503, 504):
            msg = (f"USOS тимчасово недоступний (HTTP {code}). Сайт перевантажений або оновлюється — "
                   "спробую автоматично через 30 хв, або натисніть «Оновити зараз» пізніше.")
        elif code in (400, 401, 403, 404):  # 2.7: USOS відкидає саме посилання — найчастіше воно застаріло
            msg = (f"USOS не приймає посилання на план (HTTP {code}). Найімовірніше, воно застаріло: у USOSweb відкрий "
                   "«Mój plan» → «Udostępnij plan», скопіюй нове посилання і встав його тут.")
        else:
            msg = f"Немає зв'язку з USOS: {e}"
        d.update(status="error", error_at=time.time(), message=msg)
        _save(d)
    except Exception as e:
        d.update(status="error", error_at=time.time(), message=str(e)[:300])
        _save(d)
    finally:
        _state["running"] = False
        applog.event("usos_sync", ok=d.get("status") == "ok", msg=str(d.get("message") or "")[:200],
                     events=len(d.get("events") or []))
    return public_status()


def sync_async() -> None:
    if _state["running"]:
        return
    threading.Thread(target=sync, daemon=True, name="usos-sync").start()


def due() -> bool:
    d = load()
    if not d.get("url") or _state["running"]:
        return False
    pause = 6 * 3600 if str(d.get("message", "")).startswith("USOS не приймає") else 1800  # застаріле посилання саме не оживе
    if d.get("status") == "error" and time.time() - float(d.get("error_at") or 0) < pause:
        return False  # після помилки — пауза, щоб не смикати сервер
    try:
        last = datetime.fromisoformat(d.get("synced_at")).timestamp()
    except Exception:
        return True
    return time.time() - last > 12 * 3600


# ---------------------------------------------------------------- schedule integration
def _norm(s: str) -> str:
    tr = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
    return re.sub(r"[^a-z0-9]+", " ", (s or "").translate(tr).lower()).strip()


def _short(name: str) -> str:
    words = [w for w in re.split(r"[\s\-]+", name) if w]
    letters = "".join(w[0].upper() if w[0].isalpha() else w for w in words if w.lower() not in ("i", "a", "w", "z", "na", "do")
                      )
    return (letters or name[:4]).replace("1", "1")[:8]


def _fuzzy(name: str, subjects: list[dict]):
    """Схожа назва (напр. «Bazy danych II» ↔ «Bazy danych 2») — щоб не плодити дублікати предметів."""
    a = set(_norm(name).replace(" ii", " 2").split())
    best, score = None, 0.0
    for s in subjects:
        if s.get("usos_code"):
            continue
        b = set(_norm(s["name"]).replace(" ii", " 2").split())
        if a and b:
            sc = len(a & b) / max(len(a), len(b))
            if sc > score:
                best, score = s, sc
    return best if score >= 0.75 else None


def apply_to_schedule(events: list[dict]) -> None:
    """Оновлює предмети й тижневий шаблон занять у schedule.json за даними USOS (із резервною копією)."""
    from .schedule import PALETTE, load_schedule, save_schedule, week_info, load_settings
    storage.make_backup("before-usos")
    sched = load_schedule()
    settings = load_settings()
    subjects = sched["subjects"]
    by_norm = {_norm(s["name"]): s for s in subjects}
    by_code = {s.get("usos_code"): s for s in subjects if s.get("usos_code")}
    for ev in events:
        s = by_code.get(ev["code"]) or by_norm.get(_norm(ev["name"])) or _fuzzy(ev["name"], subjects)
        if not s:
            sid = re.sub(r"[^a-z0-9]", "", _norm(_short(ev["name"])))[:10] or "s"
            base, k = sid, 2
            while any(x["id"] == sid for x in subjects):
                sid, k = f"{base}{k}", k + 1
            s = {"id": sid, "name": ev["name"], "short": _short(ev["name"]), "color": PALETTE[len(subjects) % len(PALETTE)]}
            subjects.append(s)
            by_norm[_norm(ev["name"])] = s
        if ev["code"]:
            s["usos_code"] = ev["code"]
            by_code[ev["code"]] = s
        ev["subject_id"] = s["id"]
    # тижневий шаблон: (предмет, тип, день, час, аудиторія) → у які тижні трапляється
    groups: dict = {}
    for ev in events:
        d = date.fromisoformat(ev["date"])
        k = (ev["subject_id"], ev["type"], d.weekday(), ev["start"], ev["end"], ev["room"])
        groups.setdefault(k, []).append(week_info(d, settings)["even"])
    classes = []
    for (sid, typ, day, st, en, room), par in groups.items():
        if len(par) < 2 and len(groups) > 1:
            # одноразові заняття (перенесення) не робимо частиною шаблону — їх видно в конкретних датах
            continue
        parity = "even" if all(par) else "odd" if not any(par) else "all"
        classes.append({"subject_id": sid, "day": day, "start": st, "end": en, "type": typ, "room": room, "parity": parity})
    classes.sort(key=lambda c: (c["day"], c["start"]))
    if classes:
        sched["classes"] = classes
    sched["subjects"] = subjects
    save_schedule(sched)
    # події з прив'язкою до предметів
    d = load()
    d["events"] = events
    _save(d)


def events_on(day: date) -> list[dict] | None:
    """Заняття на конкретну дату з USOS; None — якщо цей тиждень не синхронізовано."""
    d = load()
    monday = (day - timedelta(days=day.weekday())).isoformat()
    if monday not in d.get("weeks", []):
        return None
    ds = day.isoformat()
    return [e for e in d["events"] if e["date"] == ds]
