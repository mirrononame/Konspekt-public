"""2.3 (E5): сповіщення Web Push — безкоштовний стандарт браузера, без платних сервісів.

secrets/push.json (2.7: поза data) — ключі VAPID (секрет, як токен), підписки пристроїв і що вже надіслано сьогодні. Пише лише застосунок.
На iPhone працює, коли «Конспект» додано на головний екран (iOS 16.4+) і відкрито через https-адресу Tailscale.
У беті нічого не надсилається: копія даних містить ті самі підписки, телефон отримав би дублікати.
"""
from __future__ import annotations

import base64
import json
import os
import threading
from datetime import date, datetime, timedelta

from . import applog, storage

PUSH_FILE = storage.SECRETS_DIR / "push.json"
_lock = threading.Lock()
BETA = os.environ.get("KONSPEKT_BETA") == "1"
KINDS = {"done": "Готовий конспект", "answers": "Claude відповів (Допоможи, план, звіт, шпаргалка)",
         "lab": "Завтра лаба чи проєкт", "deadline": "Дедлайн протягом доби"}


def _load() -> dict:
    d = storage.read_json(PUSH_FILE, {}) or {}
    return d if isinstance(d, dict) else {}


def _keys() -> dict:
    with _lock:
        d = _load()
        if not d.get("private_pem"):
            from cryptography.hazmat.primitives import serialization
            from py_vapid import Vapid01
            v = Vapid01()
            v.generate_keys()
            pub = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
            d["private_pem"] = v.private_pem().decode()
            d["public_key"] = base64.urlsafe_b64encode(pub).rstrip(b"=").decode()
            storage.write_json(PUSH_FILE, d)
        return d


def public_key() -> str:
    return _keys()["public_key"]


def status() -> dict:
    d = _load()
    return {"subscriptions": len(d.get("subs") or []), "beta": BETA, "kinds": KINDS}


def subscribe(sub: dict, device: str = "") -> dict:
    if not isinstance(sub, dict) or not str(sub.get("endpoint", "")).startswith("https://") or not sub.get("keys"):
        raise ValueError("Неправильна підписка")
    with _lock:
        d = _load()
        subs = [s for s in d.get("subs") or [] if s["sub"]["endpoint"] != sub["endpoint"]]
        subs.append({"sub": {"endpoint": sub["endpoint"], "keys": sub["keys"]}, "device": device[:80], "at": storage.now_iso()})
        d["subs"] = subs[-10:]
        storage.write_json(PUSH_FILE, d)
    applog.event("push_subscribed", device=device[:80])
    return status()


def unsubscribe(endpoint: str) -> dict:
    with _lock:
        d = _load()
        d["subs"] = [s for s in d.get("subs") or [] if s["sub"]["endpoint"] != endpoint]
        storage.write_json(PUSH_FILE, d)
    return status()


def _enabled(kind: str) -> bool:
    from .schedule import load_settings
    return bool((load_settings().get("push_kinds") or {}).get(kind, True))


def notify(kind: str, title: str, body: str = "", url: str = "#/", tag: str = "", force: bool = False) -> int:
    """Надсилає у фоні на всі підписані пристрої. Повертає кількість підписок (0 — нікому)."""
    if BETA and not force:
        return 0
    if not force and kind != "test" and not _enabled(kind):
        return 0
    subs = list(_load().get("subs") or [])
    if not subs:
        return 0
    payload = json.dumps({"title": title[:120], "body": body[:240], "url": url, "tag": tag or kind}, ensure_ascii=False)

    def run():
        from py_vapid import Vapid01
        from pywebpush import WebPushException, webpush
        vapid = Vapid01.from_pem(_keys()["private_pem"].encode())
        dead = []
        for s in subs:
            try:
                webpush(s["sub"], payload, vapid_private_key=vapid, vapid_claims={"sub": "mailto:konspekt@example.com"}, ttl=86400)
            except WebPushException as e:
                code = getattr(getattr(e, "response", None), "status_code", None)
                if code in (404, 410):
                    dead.append(s["sub"]["endpoint"])
                else:
                    applog.error("push", code or "", str(e)[:200])
            except Exception as e:
                applog.error("push", repr(e)[:200])
        for ep in dead:
            unsubscribe(ep)
        applog.event("push_sent", what=kind, devices=len(subs) - len(dead))  # не «kind»: це вже назва події
    threading.Thread(target=run, daemon=True, name="push").start()
    return len(subs)


def _once(key: str) -> bool:
    """True, якщо сьогодні таке ще не надсилали (і позначає як надіслане)."""
    today = date.today().isoformat()
    with _lock:
        d = _load()
        sent = {k: v for k, v in (d.get("sent") or {}).items() if v >= (date.today() - timedelta(days=3)).isoformat()}
        if key in sent:
            return False
        sent[key] = today
        d["sent"] = sent
        storage.write_json(PUSH_FILE, d)
    return True


def daily() -> None:
    """Раз на хвилину зі сканера: о 19:00 — завтрашні лаби й дедлайни на добу, о 18:00 — картки."""
    if BETA or not _load().get("subs"):
        return
    now = datetime.now()
    today = now.date()
    if now.hour >= 19 and _once(f"lab:{today}"):
        from . import course, lectures, schedule
        tom = today + timedelta(days=1)
        for c in schedule.classes_on(tom):
            if c["type"] not in ("L", "P", "C"):
                continue
            last = [m for m in lectures.list_all() if m.get("subject_id") == c["subject_id"] and m.get("type") == c["type"]
                    and (m.get("date") or "") <= today.isoformat()]
            plan = course.plan_info(last[0]["id"], last[0]) if last else {}
            extra = " · план готовий" if plan.get("has_plan") else " · плану ще немає — додай умову в «Завдання»"
            notify("lab", f"Завтра {c['subject']['short']} {c['type']} о {c['start']}", f"{c.get('room', '')}{extra}",
                   f"#/lecture/{last[0]['id']}" if last else "#/planner", tag=f"lab-{tom}-{c['start']}")
    if now.hour >= 9:
        from . import eportal
        for x in eportal.list_deadlines():
            if x.get("done") or not x.get("due"):
                continue
            try:
                due = datetime.fromisoformat(x["due"][:16])
            except ValueError:
                continue
            if now < due <= now + timedelta(hours=24) and _once(f"dl:{x['id']}"):
                notify("deadline", f"До {due:%H:%M} {'сьогодні' if due.date() == today else 'завтра'}: {x['title']}",
                       x.get("what", ""), x.get("url") or "#/", tag=f"dl-{x['id']}")
    # 2.8: нагадування про картки прибрано — карток більше немає
