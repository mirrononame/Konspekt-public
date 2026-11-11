"""2.3: «Семестр» (E1), план тижня (E2), звіт (E3), календар (E4), сповіщення (E5), «Готуюсь до тесту» (E6), service worker (E7)."""
import json
from datetime import date, datetime, timedelta

from fixture import _w


def _now(sec=0):
    return (datetime.now().astimezone() + timedelta(seconds=sec)).isoformat(timespec="seconds")


def test_semester_grades_and_risk(client, data_dir):
    _w(data_dir / "subjects" / "so" / "zaliczenie.json", {
        "updated_at": _now(), "formula": "0,3·L + 0,3·P + 0,4·E",
        "components": [{"id": "L", "name": "Laboratorium", "weight": 0.3, "min": 3.0},
                       {"id": "P", "name": "Projekt", "weight": 0.3, "min": 3.0},
                       {"id": "E", "name": "Egzamin", "weight": 0.4, "min": 3.0}],
        "milestones": [{"date": (date.today() + timedelta(days=5)).isoformat(), "title": "Kolokwium 1", "component": "E"}]})
    r = client.post("/api/semester/grade", json={"subject_id": "so", "component": "L", "value": "2,5", "title": "Lab 1"})
    assert r.status_code == 200
    s = r.json()
    assert s["status"] == "risk" and s["risks"] and s["current"] == 2.5 and not s["complete"]
    client.post("/api/semester/grade", json={"subject_id": "so", "component": "L", "value": 5})
    so = next(x for x in client.get("/api/semester").json() if x["subject_id"] == "so")
    assert so["components"][0]["avg"] == 3.75 and so["status"] == "ok" and so["next"][0]["title"] == "Kolokwium 1"
    assert client.post("/api/semester/grade", json={"subject_id": "so", "component": "L", "value": "abc"}).status_code == 400
    gid = so["grades"][0]["id"]
    so = client.delete(f"/api/semester/grade/so/{gid}").json()
    assert len(so["grades"]) == 1


def test_zaliczenie_setup_queued(client, data_dir):
    from app import lectures
    _w(data_dir / "subjects" / "bd" / "memory.md", "# BD2\n## Terminy i zaliczenie\n- Projekt: 3 etapy")
    lectures.write_queue()
    q = json.loads((data_dir / "queue.json").read_text(encoding="utf-8"))
    assert any(x["subject_id"] == "bd" for x in q["zaliczenie"])
    assert not any(x["subject_id"] == "so" for x in q["zaliczenie"])  # для SO умови вже є


def test_exam_prep_flow(client, data_dir):
    from app import lectures
    day = (date.today() + timedelta(days=10)).isoformat()
    assert client.post("/api/subjects/so/exam-prep", json={"date": "", "title": "x"}).status_code == 400
    s = client.post("/api/subjects/so/exam-prep", json={"date": day, "title": "Kolokwium 1"}).json()
    assert s["prep"]["pending"] and s["prep"]["days_left"] == 10
    q = json.loads((data_dir / "queue.json").read_text(encoding="utf-8"))
    assert any(x["subject_id"] == "so" and x["date"] == day for x in q["exam_prep"])
    assert any(d["id"] == "exam:so" for d in client.get("/api/deadlines").json())
    assert any(t["subject_id"] == "so" for t in client.get("/api/study/progress").json()["tempo"])  # темп карток до тесту
    sd = data_dir / "subjects" / "so"
    (sd / "szpargalka.pdf").write_bytes(b"%PDF-1.4\n")
    _w(sd / "szpargalka.json", {"completed_at": _now(5)})
    lectures.write_queue()
    so = next(x for x in client.get("/api/semester").json() if x["subject_id"] == "so")
    assert so["prep"]["ready"]
    assert client.get("/api/subjects/so/szpargalka.pdf").content.startswith(b"%PDF")
    client.delete("/api/subjects/so/exam-prep")
    assert not any(d["id"] == "exam:so" for d in client.get("/api/deadlines").json())


def test_report_request_and_result(client, data_dir):
    lid = "2026-10-24_0730_so_rep1"
    _w(data_dir / "lectures" / lid / "meta.json", {"id": lid, "subject_id": "so", "type": "L", "date": "2026-10-24", "time": "07:30", "title": "",
                                                    "files": [], "claude": {"requested": False}, "created_at": _now()})
    assert client.post(f"/api/lectures/{lid}/report", json={"kind": "zzz"}).status_code == 400
    L = client.post(f"/api/lectures/{lid}/report", json={"kind": "check", "note": "sprawdź wnioski"}).json()
    assert L["report"]["pending"]
    q = json.loads((data_dir / "queue.json").read_text(encoding="utf-8"))
    rq = next(x for x in q["reports"] if x["lecture_id"] == lid)
    assert rq["kind"] == "check" and rq["output"]["json"].endswith("zdacha/report.json")
    _w(data_dir / "lectures" / lid / "output" / "zdacha" / "report.json",
       {"completed_at": _now(5), "kind": "check", "summary": "Prawie gotowe", "missing": ["Brak rys. 2"]})
    L = client.get(f"/api/lectures/{lid}").json()
    assert not L["report"]["pending"] and L["report"]["result"]["missing"] == ["Brak rys. 2"]


def test_calendar_ics(client, data_dir):
    assert client.get("/api/calendar.ics").status_code == 403
    assert client.get("/api/calendar.ics?k=wrong").status_code == 403
    info = client.get("/api/calendar-info").json()
    k = info["local"].split("k=")[1]
    _w(data_dir / "deadlines.json", {"manual": [{"id": "mcal", "title": "Sprawozdanie, wersja końcowa", "source": "manual",
                                                  "due": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")}], "done": []})
    r = client.get(f"/api/calendar.ics?k={k}")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    body = r.text
    assert body.startswith("BEGIN:VCALENDAR") and "Sprawozdanie\\, wersja ko" in body.replace("\r\n ", "")
    assert "TRIGGER:-P1D" in body and "TRIGGER:-PT2H" in body
    assert all(len(ln.encode("utf-8")) <= 75 for ln in body.split("\r\n"))
    (data_dir / "deadlines.json").unlink()


def test_planner_places_tasks(client, data_dir):
    _w(data_dir / "deadlines.json", {"manual": [{"id": "mplan", "title": "Raport TS", "source": "manual",
                                                  "due": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%dT23:59")}], "done": []})
    p = client.get("/api/planner?days=14").json()
    assert "tasks" in p
    placed = [t for d in p["days"] for w in d["windows"] for t in w.get("tasks", []) if t["id"] == "mplan"]
    assert placed and sum(t["minutes"] for t in placed) == 120
    assert all(d["date"] <= (date.today() + timedelta(days=3)).isoformat() for d in p["days"]
               for w in d["windows"] for t in w.get("tasks", []) if t["id"] == "mplan")
    (data_dir / "deadlines.json").unlink()


def test_push_api_and_beta_silence(client):
    from app import push
    info = client.get("/api/push").json()
    assert len(info["public_key"]) > 80 and info["beta"] is True
    assert client.post("/api/push/subscribe", json={"subscription": {"endpoint": "http://x"}}).status_code == 400
    assert client.post("/api/push/test").status_code == 400  # нікого не підписано
    client.post("/api/push/subscribe", json={"subscription": {"endpoint": "https://push.example/abc", "keys": {"p256dh": "x", "auth": "y"}}})
    assert client.get("/api/push").json()["subscriptions"] == 1
    assert push.notify("done", "x") == 0  # у беті (і в тестах) нічого не надсилається
    client.post("/api/push/unsubscribe", json={"endpoint": "https://push.example/abc"})
    assert client.get("/api/push").json()["subscriptions"] == 0


def test_answers_notify_on_help_answered(client, data_dir, monkeypatch):
    from app import lectures, push
    sent = []
    monkeypatch.setattr(push, "notify", lambda kind, title, *a, **k: sent.append((kind, title)) or 1)
    lid = "2026-10-24_0730_so_hlp1"
    _w(data_dir / "lectures" / lid / "meta.json", {"id": lid, "subject_id": "so", "type": "L", "date": "2026-10-24", "time": "07:30", "title": "",
                                                    "files": [], "claude": {"requested": False}, "created_at": _now(),
                                                    "help": [{"id": "h1", "q": "Nie działa", "asked_at": _now()}]})
    lectures.write_queue()
    _w(data_dir / "lectures" / lid / "output" / "help.md", "<!-- help:h1 -->\n### Nie działa\nUżyj chmod.")
    lectures.write_queue()
    assert ("answers", "Claude відповів у «Допоможи»") in sent


def test_service_worker_served(client):
    r = client.get("/sw.js")
    assert r.status_code == 200 and r.headers.get("service-worker-allowed") == "/" and "networkFirst" in r.text
    import re
    idx = client.get("/").text
    used = re.findall(r'/static/[\w.-]+\?v=\d+', idx)
    assert len(used) >= 6
    for u in used:
        assert u in r.text, u  # оболонка в кеші збігається з тим, що підключає index.html
