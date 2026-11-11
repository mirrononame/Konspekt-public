"""2.2: логи й журнал подій, «Так і є» для розкладу, «Здано», лічильник «Здати», вкладка «Здача», дедлайни ePortalu."""
import json
from datetime import datetime, timedelta

from fixture import _w


def _now(sec=0):
    return (datetime.now().astimezone() + timedelta(seconds=sec)).isoformat(timespec="seconds")


def _lab(data_dir, lid, checklist, extra_out=None):
    _w(data_dir / "lectures" / lid / "meta.json", {"id": lid, "subject_id": "so", "type": "L", "date": lid[:10], "time": "07:30", "title": "",
                                                    "files": [], "claude": {"requested": False}, "created_at": _now()})
    out = data_dir / "lectures" / lid / "output"
    _w(out / "notes.md", "# x")
    (out / "notes.pdf").write_bytes(b"%PDF-1.4\n")
    _w(out / "result.json", {"status": "done", "completed_at": _now(), "title": "Lab", "checklist": checklist,
                             "todos": [{"title": "Oddać sprawozdanie", "due": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")}]})
    for name, body in (extra_out or {}).items():
        p = out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)


def test_applog_dedup_and_scrub(data_dir):
    from app import applog
    for _ in range(5):
        applog.error("test src", "boom 42 wstoken=abcdef1234567890")
    log = (data_dir / "logs" / "app.log").read_text(encoding="utf-8")
    assert log.count("test src: boom") == 1 and "abcdef1234567890" not in log and "wstoken=***" in log
    ev = [json.loads(x) for x in (data_dir / "logs" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    errs = [e for e in ev if e["kind"] == "error" and e["src"] == "test src"]
    assert len(errs) == 1 and "abcdef" not in errs[0]["msg"]


def test_health_endpoint(client):
    from app import applog
    applog.event("eportal_deadlines", ok=False, msg="Limit must be between 1 and 50")
    applog.event("transcribe", ok=True, lecture="x", audio_s=600, elapsed_s=120)
    h = client.get("/api/health").json()
    assert h["syncs"]["eportal_deadlines"]["last_error"] and not h["syncs"]["eportal_deadlines"]["ok"]
    assert h["transcribe"]["speed_x"] == 5.0 and h["errors_24h"] >= 1


def test_deadline_error_is_not_retried_every_tick(monkeypatch, data_dir):
    from app import eportal
    _w(eportal.EP_FILE, {"token": "x", "courses": [], "course_map": {}, "files": {}})

    def bad(*a, **k):
        raise eportal.MoodleError("limit", "Limit must be between 1 and 50 (inclusive)")
    monkeypatch.setattr(eportal, "_call", bad)
    assert eportal.deadlines_due()
    eportal.refresh_deadlines()
    import time
    for _ in range(50):
        if not eportal.deadlines_due():
            break
        time.sleep(0.05)
    assert not eportal.deadlines_due()  # спроба записана — наступна через годину
    (eportal.EP_FILE).unlink()


def test_deadline_paging(monkeypatch, data_dir):
    from app import eportal
    calls = []

    def fake(fn, token=None, **p):
        calls.append(p)
        start = p.get("aftereventid", 0)
        n = 20 if start < 20 else 5
        return {"events": [{"id": start + i + 1, "name": f"Zadanie {start + i + 1}", "timesort": 2_000_000_000} for i in range(n)]}
    monkeypatch.setattr(eportal, "_call", fake)
    d = {"course_map": {}}
    monkeypatch.setattr(eportal, "_save", lambda d: None)
    eportal._sync_deadlines(d, [])
    assert len(d["deadlines"]) == 25 and all(c["limitnum"] == 20 for c in calls) and calls[1]["aftereventid"] == 20


def test_schedule_ok_hides_banner(client, data_dir):
    lid = "2026-10-21_1600_so_s1"  # середа 16:00 — за розкладом SO немає
    _w(data_dir / "lectures" / lid / "meta.json", {"id": lid, "subject_id": "so", "type": "W", "date": "2026-10-21", "time": "16:00",
                                                    "title": "", "files": [], "claude": {"requested": False}, "created_at": _now()})
    assert client.get(f"/api/lectures/{lid}").json()["schedule_check"]["status"] == "mismatch"
    client.patch(f"/api/lectures/{lid}", json={"schedule_ok": True})
    assert client.get(f"/api/lectures/{lid}").json()["schedule_check"]["status"] == "ok"
    client.patch(f"/api/lectures/{lid}", json={"time": "17:00"})  # змінили час — підтвердження вже не діє
    assert client.get(f"/api/lectures/{lid}").json()["schedule_check"]["status"] == "mismatch"


def test_submitted_closes_checklist_and_deadlines(client, data_dir):
    lid = "2026-10-22_0730_so_sub1"
    soon = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    _lab(data_dir, lid, [{"text": "Sprawozdanie PDF", "due": soon}, {"text": "Kod z komentarzami"}])
    before = client.get("/api/state").json()["todo_open"]
    L = client.post(f"/api/lectures/{lid}/submitted", json={"done": True}).json()
    assert all(i["done"] for i in L["checklist"]) and L["submitted_at"]
    assert client.get("/api/state").json()["todo_open"] == before - 1  # без терміну пункт у лічильник не входить
    dl = [d for d in client.get("/api/deadlines").json() if d["id"].startswith(f"lec:{lid}:")]
    assert dl and all(d["done"] for d in dl)
    L = client.post(f"/api/lectures/{lid}/submitted", json={"done": False}).json()
    assert not any(i["done"] for i in L["checklist"]) and not L.get("submitted_at")


def test_todo_counter_only_next_7_days(client, data_dir):
    lid = "2026-10-23_0730_so_cnt1"
    far = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    old = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    before = client.get("/api/state").json()["todo_open"]
    _lab(data_dir, lid, [{"text": "Za miesiąc", "due": far}, {"text": "Dawno minęło", "due": old}, {"text": "Bez daty"}])
    assert client.get("/api/state").json()["todo_open"] == before


def test_deliverables_listed_and_served(client, data_dir):
    lid = "2026-10-24_0730_so_zd1"
    _lab(data_dir, lid, [], {"zdacha/Sprawozdanie.pdf": b"%PDF-1.4\n", "kod.py": b"print(1)\n", "quiz.json": b"{}"})
    L = client.get(f"/api/lectures/{lid}").json()
    names = [d["name"] for d in L["output"]["deliverables"]]
    assert "zdacha/Sprawozdanie.pdf" in names and "kod.py" in names
    assert not any(n.startswith(("notes", "quiz", "result")) for n in names)
    r = client.get(f"/api/lectures/{lid}/output/zdacha/Sprawozdanie.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert client.get(f"/api/lectures/{lid}/output/..%2F..%2Fmeta.json").status_code == 404


def test_claude_done_event(client, data_dir):
    from app import applog, lectures
    lid = "2026-10-25_1115_so_cd1"
    _w(data_dir / "lectures" / lid / "meta.json", {"id": lid, "subject_id": "so", "type": "W", "date": "2026-10-25", "time": "11:15", "title": "",
                                                    "files": [], "claude": {"requested": True, "requested_at": _now(-7200)},
                                                    "created_at": _now(-7300)})
    lectures.write_queue()
    out = data_dir / "lectures" / lid / "output"
    _w(out / "notes.md", "# x")
    (out / "notes.pdf").write_bytes(b"%PDF-1.4\n")
    _w(out / "result.json", {"status": "done", "completed_at": _now(), "title": "T"})
    lectures.write_queue()
    ev = [e for e in applog.read_events(1) if e["kind"] == "claude_done" and e["lecture"] == lid]
    assert ev and 1.9 <= ev[0]["wait_h"] <= 2.1
