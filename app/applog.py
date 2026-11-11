"""Логи й журнал подій (2.2). Усе лишається на ПК, у data/logs/, і нікуди не надсилається.

  app.log       — читабельний лог з часом і рівнем; однакова помилка пишеться раз на годину з лічильником повторів
  events.jsonl  — журнал подій (по рядку JSON): синхронізації, розшифровки, обробка Claude, навчання, помилки.
                  Без токенів і без тексту лекцій — лише назви, числа й тривалість.
Обидва файли ротуються: app.log — 3 × 1 МБ, events.jsonl — 2 × 5 МБ.
"""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timedelta

from . import storage

LOG_DIR = storage.DATA_DIR / "logs"
APP_LOG = LOG_DIR / "app.log"
EVENTS = LOG_DIR / "events.jsonl"
REPEAT_WINDOW = 3600  # та сама помилка — не частіше разу на годину

_lock = threading.Lock()
_seen: dict[str, list] = {}  # ключ → [скільки разів пропущено, коли записано востаннє]
_SECRET_RX = re.compile(r"(?i)(wstoken|token|passport|privatetoken)([\"'=: ]+)[A-Za-z0-9:_\-]{8,}")


def _scrub(s: str) -> str:
    return _SECRET_RX.sub(r"\1\2***", s)


def _rotate(p, limit: int, keep: int) -> None:
    try:
        if p.exists() and p.stat().st_size > limit:
            for i in range(keep - 1, 0, -1):
                src = p.with_name(f"{p.stem}.{i}{p.suffix}")
                if src.exists():
                    src.replace(p.with_name(f"{p.stem}.{i + 1}{p.suffix}"))
            p.replace(p.with_name(f"{p.stem}.1{p.suffix}"))
    except OSError:
        pass


def _write_line(line: str) -> None:
    print(line)  # консоль / server.log, як і раніше
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with _lock:
            _rotate(APP_LOG, 1_000_000, 3)
            with open(APP_LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError:
        pass


def _msg(parts) -> str:
    return _scrub(" ".join(str(p) for p in parts))[:1000]


def info(src: str, *parts) -> None:
    _write_line(f"{datetime.now():%Y-%m-%d %H:%M:%S} INFO  {src}: {_msg(parts)}")


def error(src: str, *parts) -> None:
    """Помилка: у лог (без спаму повторів) і в журнал подій."""
    msg = _msg(parts)
    key = f"{src}|{re.sub(r'[0-9]+', '#', msg)[:200]}"
    now = time.time()
    with _lock:
        rec = _seen.get(key)
        if rec and now - rec[1] < REPEAT_WINDOW:
            rec[0] += 1
            return
        skipped = rec[0] if rec else 0
        _seen[key] = [0, now]
    extra = f" (ще {skipped} таких самих за останню годину)" if skipped else ""
    _write_line(f"{datetime.now():%Y-%m-%d %H:%M:%S} ERROR {src}: {msg}{extra}")
    event("error", src=src, msg=msg[:300], repeats=skipped)


def event(kind: str, **fields) -> None:
    rec = {"t": storage.now_iso(), "kind": kind}
    for k, v in fields.items():
        rec[k] = _scrub(v)[:300] if isinstance(v, str) else v
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with _lock:
            _rotate(EVENTS, 5_000_000, 2)
            with open(EVENTS, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_events(days: float = 30) -> list[dict]:
    since = datetime.now().astimezone() - timedelta(days=days)
    out = []
    for p in (EVENTS.with_name(f"{EVENTS.stem}.1{EVENTS.suffix}"), EVENTS):
        if not p.exists():
            continue
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    e = json.loads(line)
                    if datetime.fromisoformat(e["t"]) >= since:
                        out.append(e)
                except (ValueError, KeyError):
                    continue
        except OSError:
            continue
    return out


def summary() -> dict:
    """Для «Стан застосунку»: остання вдала й невдала синхронізація, помилки за добу, розшифровка, Claude."""
    ev = read_events(30)
    day_ago = (datetime.now().astimezone() - timedelta(hours=24)).isoformat()
    syncs = {}
    for kind in ("eportal_sync", "eportal_deadlines", "usos_sync"):
        xs = [e for e in ev if e["kind"] == kind]
        ok = [e for e in xs if e.get("ok")]
        bad = [e for e in xs if not e.get("ok")]
        syncs[kind] = {"last_ok": ok[-1]["t"] if ok else None, "last_error": bad[-1]["t"] if bad else None,
                       "error_msg": bad[-1].get("msg", "") if bad else "", "ok": bool(xs) and bool(xs[-1].get("ok"))}
    errs = [e for e in ev if e["kind"] == "error" and e["t"] >= day_ago]
    by_src: dict[str, int] = {}
    for e in errs:
        by_src[e["src"]] = by_src.get(e["src"], 0) + 1 + int(e.get("repeats") or 0)
    tr = [e for e in ev if e["kind"] == "transcribe" and e.get("ok") and e.get("audio_s") and e.get("elapsed_s")]
    speed = round(sum(e["audio_s"] for e in tr) / max(1, sum(e["elapsed_s"] for e in tr)), 1) if tr else None
    cl = [e for e in ev if e["kind"] == "claude_done" and e.get("wait_h") is not None]
    study_days = sorted({e["t"][:10] for e in ev if e["kind"] == "study"})
    return {"syncs": syncs, "errors_24h": sum(by_src.values()), "errors_by_src": by_src,
            "last_errors": [{"t": e["t"], "src": e["src"], "msg": e.get("msg", "")} for e in errs[-5:]][::-1],
            "transcribe": {"count": len(tr), "speed_x": speed},
            "claude": {"count": len(cl), "avg_wait_h": round(sum(e["wait_h"] for e in cl) / len(cl), 1) if cl else None},
            "study_days_30d": len(study_days), "events_30d": len(ev)}
