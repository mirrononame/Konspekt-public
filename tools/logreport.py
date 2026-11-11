"""Звіт з журналу подій «Конспекту» (data/logs/events.jsonl) — для оглядів «що покращити».

  python tools/logreport.py [папка data] [днів=30]

Читає лише журнал подій (без токенів і тексту лекцій).
"""
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # консоль Windows (cp1251) інакше ламає кирилицю
    except (AttributeError, ValueError):
        pass
    data = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    since = datetime.now().astimezone() - timedelta(days=days)
    ev = []
    for p in (data / "logs" / "events.1.jsonl", data / "logs" / "events.jsonl"):
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    e = json.loads(line)
                    if datetime.fromisoformat(e["t"]) >= since:
                        ev.append(e)
                except (ValueError, KeyError):
                    pass
    if not ev:
        print(f"Подій за {days} дн. немає ({data / 'logs'}).")
        return
    print(f"Журнал за {days} дн.: подій — {len(ev)}, {ev[0]['t'][:10]} … {ev[-1]['t'][:10]}\n")
    print("Події:", ", ".join(f"{k} {n}" for k, n in Counter(e["kind"] for e in ev).most_common()))
    for kind in ("eportal_sync", "eportal_deadlines", "usos_sync"):
        xs = [e for e in ev if e["kind"] == kind]
        if xs:
            ok = sum(1 for e in xs if e.get("ok"))
            last_bad = next((e for e in reversed(xs) if not e.get("ok")), None)
            print(f"{kind}: вдалих {ok}/{len(xs)}" + (f"; остання помилка {last_bad['t'][:16]}: {last_bad.get('msg', '')}" if last_bad else ""))
    err = Counter()
    for e in ev:
        if e["kind"] == "error":
            err[e.get("src", "?")] += 1 + int(e.get("repeats") or 0)
    if err:
        print("Помилки за джерелом:", ", ".join(f"{k} {n}" for k, n in err.most_common()))
    tr = [e for e in ev if e["kind"] == "transcribe"]
    good = [e for e in tr if e.get("ok") and e.get("elapsed_s")]
    if tr:
        speed = sum(e.get("audio_s", 0) for e in good) / max(1, sum(e["elapsed_s"] for e in good))
        print(f"Розшифровка: {len(good)} вдало, {len(tr) - len(good)} з помилкою, швидкість {speed:.1f}× від тривалості запису")
    cl = [e for e in ev if e["kind"] == "claude_done" and e.get("wait_h") is not None]
    if cl:
        w = sorted(e["wait_h"] for e in cl)
        print(f"Claude: {len(cl)} занять, очікування медіана {w[len(w) // 2]} год, макс {w[-1]} год")
    st = [e for e in ev if e["kind"] == "study"]
    if st:
        print(f"Навчання: {len({e['t'][:10] for e in st})} днів, відповідей ≈ {sum(e.get('answers', 0) for e in st)}, "
              f"режими: {dict(Counter(e.get('mode') for e in st))}")
    la = Counter(e.get("subject") or "?" for e in ev if e["kind"] == "lecture_added")
    if la:
        print("Нові заняття:", ", ".join(f"{k} {n}" for k, n in la.most_common()))


if __name__ == "__main__":
    main()
