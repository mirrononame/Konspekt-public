"""FSRS (Free Spaced Repetition Scheduler, версія 4.5 — як в Anki) з денною гранулярністю.

Стан картки: {"s": стабільність (дні), "d": складність 1..10, "state": "new|learning|review|relearning",
              "due": ISO-дата/час, "last": ISO, "reps": n, "lapses": n}
Оцінки: 1 — Знову, 2 — Важко, 3 — Добре, 4 — Легко.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

W = [0.4872, 1.4003, 3.7145, 13.8206, 5.1618, 1.2298, 0.8975, 0.031, 1.6474, 0.1367,
     1.0461, 2.1072, 0.0793, 0.3246, 1.587, 0.2272, 2.8755]
DECAY = -0.5
FACTOR = 0.9 ** (1 / DECAY) - 1  # = 19/81
RETENTION = 0.9
MAX_IVL = 365
AGAIN_MIN = 10   # «Знову» → повтор через 10 хв (у тій самій сесії)
HARD_NEW_MIN = 30  # «Важко» для нової картки → через 30 хв (сьогодні ж)


def _clamp(x, a, b):
    return max(a, min(b, x))


def retrievability(t_days: float, s: float) -> float:
    if s <= 0:
        return 0.0
    return (1 + FACTOR * max(0.0, t_days) / s) ** DECAY


def interval(s: float, retention: float = RETENTION) -> int:
    ivl = s / FACTOR * (retention ** (1 / DECAY) - 1)
    return int(_clamp(round(ivl), 1, MAX_IVL))


def init_d(g: int) -> float:
    return _clamp(W[4] - (g - 3) * W[5], 1, 10)


def next_d(d: float, g: int) -> float:
    nd = d - W[6] * (g - 3)
    return _clamp(W[7] * init_d(3) + (1 - W[7]) * nd, 1, 10)


def s_success(d: float, s: float, r: float, g: int) -> float:
    hard = W[15] if g == 2 else 1
    easy = W[16] if g == 4 else 1
    return s * (math.exp(W[8]) * (11 - d) * s ** (-W[9]) * (math.exp(W[10] * (1 - r)) - 1) * hard * easy + 1)


def s_fail(d: float, s: float, r: float) -> float:
    return min(s, W[11] * d ** (-W[12]) * ((s + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r)))


def _parse(v) -> datetime | None:
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.astimezone()
    except ValueError:
        return None


def _iso(dt: datetime) -> str:
    return dt.astimezone().isoformat(timespec="seconds")


def _day_due(now: datetime, days: int) -> datetime:
    """Початок дня через `days` днів (картка доступна з ранку)."""
    d = (now + timedelta(days=days)).replace(hour=4, minute=0, second=0, microsecond=0)
    return d


def review(card: dict | None, g: int, now: datetime | None = None) -> dict:
    """Повертає новий стан картки після оцінки g (1..4)."""
    now = now or datetime.now().astimezone()
    g = int(_clamp(int(g), 1, 4))
    c = dict(card or {})
    state = c.get("state") or "new"
    s, d = c.get("s"), c.get("d")
    last = _parse(c.get("last"))
    c["reps"] = int(c.get("reps", 0)) + 1
    c["last"] = _iso(now)
    c["rating"] = g
    if state == "new" or s is None or d is None:
        s, d = W[g - 1], init_d(g)
        if g == 1:
            c.update(state="learning", due=_iso(now + timedelta(minutes=AGAIN_MIN)))
        elif g == 2:
            c.update(state="learning", due=_iso(now + timedelta(minutes=HARD_NEW_MIN)))
        else:
            ivl = interval(s)
            if g == 4:
                ivl = max(ivl, 4)
            c.update(state="review", due=_iso(_day_due(now, ivl)), ivl=ivl)
        c.update(s=round(s, 4), d=round(d, 4))
        return c
    elapsed = ((now - last).total_seconds() / 86400) if last else 0.0
    r = retrievability(elapsed, s)
    if state in ("learning", "relearning") and elapsed < 1:
        # короткострокове повторення в той самий день: стабільність майже не росте
        if g == 1:
            c.update(state=state, due=_iso(now + timedelta(minutes=AGAIN_MIN)))
            d = next_d(d, g)
        else:
            d = next_d(d, g)
            if g >= 3:
                s = max(s, W[2] if g == 3 else W[3]) if state == "learning" else s * (1.2 if g == 3 else 1.6)
                ivl = interval(s)
                if g == 4:
                    ivl = max(ivl, 2)
                c.update(state="review", due=_iso(_day_due(now, ivl)), ivl=ivl)
            else:
                c.update(due=_iso(now + timedelta(minutes=HARD_NEW_MIN)))
        c.update(s=round(s, 4), d=round(d, 4))
        return c
    nd = next_d(d, g)
    if g == 1:
        ns = s_fail(d, s, r)
        c["lapses"] = int(c.get("lapses", 0)) + 1
        c.update(state="relearning", due=_iso(now + timedelta(minutes=AGAIN_MIN)), ivl=0)
    else:
        ns = s_success(d, s, r, g)
        ivl = interval(ns)
        prev_ivl = int(c.get("ivl") or 0)
        hard_ivl = max(1, min(interval(s_success(d, s, r, 2)), max(prev_ivl, 1)))
        if g == 2:
            ivl = hard_ivl  # «Важко» — не довше за попередній інтервал
        if g == 3:
            ivl = max(ivl, hard_ivl + 1)
        if g == 4:
            ivl = max(ivl, max(interval(s_success(d, s, r, 3)), hard_ivl + 1) + 1)
        c.update(state="review", due=_iso(_day_due(now, ivl)), ivl=ivl)
    c.update(s=round(ns, 4), d=round(nd, 4))
    return c


def preview(card: dict | None, now: datetime | None = None) -> dict:
    """Інтервали для 4 кнопок: {"1": "10 хв", "2": "1 д", ...}."""
    now = now or datetime.now().astimezone()
    out = {}
    for g in (1, 2, 3, 4):
        c = review(card, g, now)
        due = _parse(c["due"])
        mins = (due - now).total_seconds() / 60
        out[str(g)] = fmt_ivl(mins)
    return out


def fmt_ivl(mins: float) -> str:
    if mins < 60:
        return f"{max(1, round(mins))} хв"
    if mins < 60 * 6:
        return f"{round(mins / 60)} год"
    days = round(mins / 1440)
    if days < 1:
        days = 1
    if days < 31:
        return f"{days} д"
    if days < 365:
        return f"{round(days / 30)} міс"
    return f"{days / 365:.1f} р"


def from_leitner(p: dict, intervals=(0, 1, 3, 7, 14, 30)) -> dict:
    """Міграція прогресу Лейтнера (study.json v1) у стан FSRS без втрати інтервалів."""
    box = int(p.get("box", 0) or 0)
    seen = int(p.get("seen", 0) or 0)
    known = p.get("last_known")
    s = float(max(0.5, intervals[min(box, len(intervals) - 1)] or 0.5))
    d = 4.5 if known else 7.0
    due = p.get("due")
    due_iso = f"{due}T04:00:00" if due and len(due) == 10 else due
    dt = _parse(due_iso) if due_iso else None
    out = {"s": s, "d": d, "state": "review" if box >= 2 else ("relearning" if seen and not known else "review"),
           "reps": seen, "lapses": 0 if known else (1 if seen else 0), "last": p.get("last"),
           "due": _iso(dt) if dt else _iso(datetime.now().astimezone()), "ivl": int(intervals[min(box, 5)]),
           "migrated": "leitner"}
    return out
