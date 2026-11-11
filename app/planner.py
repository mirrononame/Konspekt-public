"""Планер: вільні дні, свята в Польщі, вікна для праці та план дня (підйом / вихід / дорога).

Дорога рахується від домашньої адреси (з налаштувань) або від поточного місця телефона
до будинку PWr, де відбувається перша пара. Маршрути — OSRM (OpenStreetMap), координати —
Nominatim / Overpass; усе кешується в data/planner_cache.json. Без інтернету — оцінка за відстанню.
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta

from . import applog, schedule, storage, usos

CACHE_FILE = storage.DATA_DIR / "planner_cache.json"
UA = "Konspekt/1.5 (prywatna aplikacja studenta PWr; planer dojazdu)"
CAMPUS = {"lat": 51.1079, "lon": 17.0620, "name": "Кампус PWr (Wybrzeże Wyspiańskiego 27)"}
BBOX = (51.085, 17.020, 51.130, 17.100)  # район головного кампусу PWr (S, W, N, E)
MODES = {"transit": "Громадський транспорт", "foot": "Пішки", "bike": "Велосипед", "car": "Авто"}
_lock = threading.Lock()

DEFAULTS = {
    "planner_address": "", "planner_lat": None, "planner_lon": None, "planner_place": "",
    "planner_mode": "transit", "planner_travel_override": 0,
    "planner_morning_min": 60, "planner_buffer_min": 10, "planner_sleep_h": 8,
    "planner_work_from": "08:00", "planner_work_to": "21:00", "planner_min_block": 120,
    "planner_campus_gaps": False, "planner_weekends": True,
}


# ---------------------------------------------------------------- свята
def _easter(y: int) -> date:
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(y, month, day)


def holidays(y: int) -> dict[str, dict]:
    """Дні, вільні від праці в Польщі (ustawa o dniach wolnych od pracy)."""
    e = _easter(y)
    items = [
        (date(y, 1, 1), "Nowy Rok", "Новий рік"),
        (date(y, 1, 6), "Święto Trzech Króli", "Богоявлення (Три королі)"),
        (e, "Wielkanoc", "Великдень"),
        (e + timedelta(days=1), "Poniedziałek Wielkanocny", "Великодній понеділок"),
        (date(y, 5, 1), "Święto Pracy", "День праці"),
        (date(y, 5, 3), "Święto Konstytucji 3 Maja", "День Конституції 3 травня"),
        (e + timedelta(days=49), "Zielone Świątki", "Трійця (П'ятидесятниця)"),
        (e + timedelta(days=60), "Boże Ciało", "Боже Тіло"),
        (date(y, 8, 15), "Wniebowzięcie NMP", "Успіння Богородиці / День Війська Польського"),
        (date(y, 11, 1), "Wszystkich Świętych", "День усіх святих"),
        (date(y, 11, 11), "Narodowe Święto Niepodległości", "День незалежності"),
        (date(y, 12, 25), "Boże Narodzenie (1. dzień)", "Різдво"),
        (date(y, 12, 26), "Boże Narodzenie (2. dzień)", "Другий день Різдва"),
    ]
    if y >= 2025:
        items.append((date(y, 12, 24), "Wigilia", "Святвечір"))
    return {d.isoformat(): {"pl": pl, "uk": uk} for d, pl, uk in items}


# ---------------------------------------------------------------- кеш і мережа
def _cache() -> dict:
    c = storage.read_json(CACHE_FILE, {}) or {}
    c.setdefault("buildings", {})
    c.setdefault("routes", {})
    return c


def _save_cache(c: dict) -> None:
    storage.write_json(CACHE_FILE, c)


def _get_json(url: str, data: bytes | None = None, timeout: float = 12):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "application/json",
                                                          "Accept-Language": "pl,uk,en"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def geocode(address: str) -> dict:
    """Адреса → координати (Nominatim / OpenStreetMap). Пріоритет — Вроцлав."""
    address = (address or "").strip()
    if len(address) < 4:
        raise ValueError("Введіть адресу, напр. «ul. Grunwaldzka 10, Wrocław»")
    q = address if re.search(r"wroc", address, re.I) else address + ", Wrocław"
    for query in (q, address):
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
            {"format": "jsonv2", "q": query, "countrycodes": "pl", "limit": 1, "addressdetails": 0,
             "viewbox": "16.80,51.21,17.18,51.04"})
        res = _get_json(url)
        if res:
            r = res[0]
            return {"lat": float(r["lat"]), "lon": float(r["lon"]), "place": r.get("display_name", address)}
        time.sleep(1.1)  # правила Nominatim: не частіше 1 запиту/с
    raise ValueError("Адресу не знайдено. Спробуйте: вулиця + номер + місто")


def _building_code(room: str) -> str:
    m = re.search(r"bud\.?\s*([A-Z]{1,2})\s*-?\s*(\d{1,2}[a-z]?)", room or "", re.I)
    return f"{m.group(1).upper()}-{m.group(2)}" if m else ""


def _lookup_buildings(codes: list[str], cache: dict) -> None:
    """Шукає будинки PWr в OpenStreetMap (тег ref/name = «C-16» тощо) одним запитом Overpass."""
    todo = [c for c in codes if c and c not in cache["buildings"]]
    if not todo:
        return
    alt = "|".join(re.escape(c) for c in todo)
    s, w, n, e = BBOX
    q = (f'[out:json][timeout:25];(nwr["building"]["ref"~"^({alt})$"]({s},{w},{n},{e});'
         f'nwr["building"]["name"~"^(Budynek |budynek )?({alt})$"]({s},{w},{n},{e}););out center tags;')
    found = {}
    try:
        res = _get_json("https://overpass-api.de/api/interpreter", data=urllib.parse.urlencode({"data": q}).encode(), timeout=30)
        for el in res.get("elements", []):
            tags = el.get("tags", {})
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None:
                continue
            for c in todo:
                if tags.get("ref", "").upper() == c or re.fullmatch(rf"(budynek )?{re.escape(c)}", tags.get("name", ""), re.I):
                    found.setdefault(c, {"lat": lat, "lon": lon, "src": "osm"})
    except Exception as ex:
        applog.error("planner overpass", repr(ex))
        return  # спробуємо наступного разу; поки — центр кампусу
    for c in todo:
        cache["buildings"][c] = found.get(c) or {**{k: CAMPUS[k] for k in ("lat", "lon")}, "src": "campus"}


def _haversine(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _estimate(km: float, mode: str) -> int:
    road = km * 1.35
    if mode == "foot":
        return round(road / 4.8 * 60)
    if mode == "bike":
        return round(road / 15 * 60) + 3
    if mode == "car":
        return round(road / 24 * 60) + 7  # місто + паркування
    return round(road / 16 * 60) + 12      # трамвай/автобус: дійти до зупинки, почекати, дійти від зупинки


def travel(origin: tuple[float, float], dest: tuple[float, float], mode: str, cache: dict) -> dict:
    key = f"{origin[0]:.3f},{origin[1]:.3f}>{dest[0]:.4f},{dest[1]:.4f}:{mode}"
    if key in cache["routes"]:
        return cache["routes"][key]
    straight = _haversine(origin, dest)
    out = {"minutes": _estimate(straight, mode), "km": round(straight * 1.35, 1), "src": "estimate"}
    if straight < 0.25:
        out = {"minutes": 4, "km": round(straight, 2), "src": "near"}
    else:
        prof = {"foot": "routed-foot", "bike": "routed-bike", "car": "routed-car", "transit": "routed-foot"}[mode]
        url = (f"https://routing.openstreetmap.de/{prof}/route/v1/driving/"
               f"{origin[1]:.5f},{origin[0]:.5f};{dest[1]:.5f},{dest[0]:.5f}?overview=false")
        try:
            r = _get_json(url, timeout=10)["routes"][0]
            km = r["distance"] / 1000
            if mode == "transit":
                mins = round(km / 16 * 60) + 12
            elif mode == "car":
                mins = round(r["duration"] / 60 * 1.25) + 7
            else:
                mins = round(r["duration"] / 60)
            out = {"minutes": max(3, mins), "km": round(km, 1), "src": "osrm"}
        except Exception as ex:
            applog.error("planner osrm", repr(ex))
            return out  # не кешуємо оцінку — наступного разу спробуємо маршрут
    cache["routes"][key] = out
    return out


# ---------------------------------------------------------------- розрахунок
def settings() -> dict:
    s = schedule.load_settings()
    return {k: s.get(k, v) for k, v in DEFAULTS.items()}


def _m(t: str) -> int:
    h, m = str(t).split(":")
    return int(h) * 60 + int(m)


def _f(m: int) -> str:
    m = max(0, min(int(m), 24 * 60 - 1))
    return f"{m // 60:02d}:{m % 60:02d}"


def _int(v, default, lo, hi):
    try:
        return max(lo, min(hi, int(float(v))))
    except Exception:
        return default


def plan(start: date, days: int, lat: float | None = None, lon: float | None = None) -> dict:
    ps = settings()
    sched = schedule.load_schedule()
    sets = schedule.load_settings()
    mode = ps["planner_mode"] if ps["planner_mode"] in MODES else "transit"
    morning = _int(ps["planner_morning_min"], 60, 0, 240)
    buffer = _int(ps["planner_buffer_min"], 10, 0, 60)
    sleep_h = _int(ps["planner_sleep_h"], 8, 4, 12)
    min_block = _int(ps["planner_min_block"], 120, 30, 600)
    override = _int(ps["planner_travel_override"], 0, 0, 240)
    try:
        w0, w1 = _m(ps["planner_work_from"]), _m(ps["planner_work_to"])
    except Exception:
        w0, w1 = 8 * 60, 21 * 60
    if w1 <= w0:
        w1 = w0 + 8 * 60

    origin, origin_src = None, "none"
    if lat is not None and lon is not None:
        origin, origin_src = (float(lat), float(lon)), "device"
    elif ps["planner_lat"] is not None and ps["planner_lon"] is not None:
        origin, origin_src = (float(ps["planner_lat"]), float(ps["planner_lon"])), "home"

    hol = {}
    for y in {start.year, (start + timedelta(days=days)).year}:
        hol.update(holidays(y))

    # заняття по днях + потрібні будинки
    raw = []
    codes = set()
    for i in range(days):
        d = start + timedelta(days=i)
        cl = schedule.classes_on(d, sched, sets)
        for c in cl:
            c["building"] = _building_code(c.get("room", ""))
            codes.add(c["building"])
        raw.append((d, cl))

    with _lock:
        cache = _cache()
        if origin:
            _lookup_buildings(sorted(c for c in codes if c), cache)
        trav: dict[str, dict] = {}

        def trip(code: str) -> dict:
            if override:
                return {"minutes": override, "km": None, "src": "manual"}
            if not origin:
                return {"minutes": 30, "km": None, "src": "default"}
            if code not in trav:
                b = cache["buildings"].get(code) or {**{k: CAMPUS[k] for k in ("lat", "lon")}, "src": "campus"}
                t = travel(origin, (b["lat"], b["lon"]), mode, cache)
                trav[code] = {**t, "dest": {"lat": b["lat"], "lon": b["lon"], "src": b.get("src", "campus")}}
            return trav[code]

        out_days = []
        for d, cl in raw:
            ds = d.isoformat()
            h = hol.get(ds)
            weekend = d.weekday() >= 5
            note = ""
            source = cl[0].get("source", "template") if cl else ""
            if h and cl and source != "usos":
                note = "Свято — заняття за шаблоном розкладу, найімовірніше, не відбудуться"
                cancelled, cl = cl, []
            else:
                cancelled = []
            if not cl and not weekend and not h:
                tmpl = [c for c in sched["classes"] if c["day"] == d.weekday()]
                if tmpl and usos.events_on(d) is not None:
                    note = "За USOS цього дня занять немає (перенесення / день ректорський?)"
            classes = [{"subject": c["subject"]["short"], "subject_name": c["subject"]["name"], "color": c["subject"]["color"],
                        "start": c["start"], "end": c["end"], "type": c["type"], "room": c.get("room", ""),
                        "building": c["building"]} for c in cl]
            windows, day_plan = [], None
            if classes:
                first, last = classes[0], max(classes, key=lambda c: _m(c["end"]))
                t_in, t_out = trip(first["building"]), trip(last["building"])
                leave = _m(first["start"]) - t_in["minutes"] - buffer
                wake = leave - morning
                day_plan = {"wake": _f(wake), "leave": _f(leave), "travel_in": t_in, "travel_out": t_out,
                            "first": first["start"], "first_building": first["building"],
                            "home": _f(_m(last["end"]) + t_out["minutes"]), "last_end": last["end"],
                            "bed": _f((wake - sleep_h * 60) % (24 * 60)), "early": wake < 6 * 60 + 30}
                busy_from, busy_to = leave, _m(last["end"]) + t_out["minutes"]
                if busy_from - w0 >= 30:
                    windows.append({"from": _f(w0), "to": _f(min(busy_from, w1)), "where": "home"})
                # перерви між парами
                for a, b in zip(classes, classes[1:]):
                    g0, g1 = _m(a["end"]), _m(b["start"])
                    if g1 - g0 < 45:
                        continue
                    t_home = trip(a["building"])["minutes"] + trip(b["building"])["minutes"] + buffer
                    if g1 - g0 - t_home >= min_block and not ps["planner_campus_gaps"]:
                        windows.append({"from": _f(g0 + trip(a["building"])["minutes"]),
                                        "to": _f(g1 - trip(b["building"])["minutes"] - buffer), "where": "home"})
                    else:
                        windows.append({"from": _f(g0 + 5), "to": _f(g1 - 5), "where": "campus"})
                if w1 - busy_to >= 30:
                    windows.append({"from": _f(max(busy_to, w0)), "to": _f(w1), "where": "home"})
            elif not (weekend and not ps["planner_weekends"]):
                windows.append({"from": _f(w0), "to": _f(w1), "where": "home"})
            for w in windows:
                w["minutes"] = max(0, _m(w["to"]) - _m(w["from"]))
                w["work"] = w["minutes"] >= min_block and (w["where"] == "home" or ps["planner_campus_gaps"])
            windows = [w for w in windows if w["minutes"] >= 30]
            work_min = sum(w["minutes"] for w in windows if w["work"])
            kind = "holiday" if h else "weekend" if weekend else "classes" if classes else "free"
            out_days.append({"date": ds, "weekday": d.weekday(), "kind": kind, "holiday": h, "note": note,
                             "week": schedule.week_info(d, sets), "classes": classes,
                             "cancelled": [{"subject": c["subject"]["short"], "start": c["start"]} for c in cancelled],
                             "windows": windows, "work_minutes": work_min, "plan": day_plan})
        _save_cache(cache)

    # найкращі БУДНІ (вихідні й свята і так вільні цілком — їх видно в списку)
    best = sorted([d for d in out_days if d["work_minutes"] >= min_block and d["date"] >= date.today().isoformat()
                   and d["kind"] in ("free", "classes")],
                  key=lambda d: (-d["work_minutes"], d["date"]))[:6]
    return {
        "start": start.isoformat(), "days": out_days, "best": [d["date"] for d in best],
        "settings": ps, "modes": MODES,
        "origin": {"src": origin_src, "lat": origin[0] if origin else None, "lon": origin[1] if origin else None,
                   "place": ps["planner_place"] if origin_src == "home" else ""},
        "buildings": {k: v for k, v in cache["buildings"].items() if k in codes},
        "campus": CAMPUS,
    }
