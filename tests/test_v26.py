"""2.6: одна жива інструкція до лаби, один запит за раз, «Проєкт» у кожному предметі з проєктом, «Етап здано»."""
import json
from datetime import datetime, timedelta

from fixture import _w


def _now(sec=0):
    return (datetime.now().astimezone() + timedelta(seconds=sec)).isoformat(timespec="seconds")


def _lab(data_dir, lid):
    _w(data_dir / "lectures" / lid / "meta.json", {"id": lid, "subject_id": "so", "type": "L", "date": lid[:10], "time": "07:30", "title": "",
                                                    "files": [], "claude": {"requested": False}, "created_at": _now()})


def test_one_request_at_a_time_and_progress(client, data_dir):
    lid = "2026-11-02_0730_so_one1"
    _lab(data_dir, lid)
    out = data_dir / "lectures" / lid / "output"
    _w(out / "plan.md", "# Lab\n\n## Cel w 1 zdaniu\nx\n\n## Krok po kroku\n1. a\n\n## Do oddania\nx")
    _w(out / "plan.json", {"completed_at": _now(-60), "checklist": [{"text": "Skrypt działa"}, {"text": "Sprawozdanie PDF"}]})
    L = client.get(f"/api/lectures/{lid}").json()
    cid = next(i["id"] for i in L["checklist"] if i["text"] == "Skrypt działa")
    client.post(f"/api/lectures/{lid}/checklist/{cid}", json={"done": True})
    assert client.post(f"/api/lectures/{lid}/plan", json={"note": "krok 3 nie działa"}).status_code == 200
    # поки інструкція оновлюється — інші запити по цьому заняттю чекають
    for path, body in (("help", {"q": "a teraz?"}), ("report", {"kind": "draft"}), ("plan", {"note": "jeszcze"})):
        r = client.post(f"/api/lectures/{lid}/{path}", json=body)
        assert r.status_code in (400, 409) and "ще працює" in r.json()["detail"], (path, r.text)
    assert client.post(f"/api/lectures/{lid}/claude", json={}).status_code == 409
    q = json.loads((data_dir / "queue.json").read_text(encoding="utf-8"))
    item = next(x for x in q["plans"] if x["lecture_id"] == lid)
    assert item["instruction_exists"] and item["progress"]["done"] == ["Skrypt działa"] and "Sprawozdanie PDF" in item["progress"]["open"]
    _w(out / "plan.json", {"completed_at": _now(5), "checklist": [{"text": "Skrypt działa"}, {"text": "Sprawozdanie PDF"}]})
    assert client.post(f"/api/lectures/{lid}/help", json={"q": "a teraz?"}).status_code == 200  # після відповіді — можна


def test_lecture_course_is_not_blocked(client, data_dir):
    from app import course, lectures
    assert course.busy_reason(lectures.read_meta("2026-10-19_1115_so_aaaa")) is None  # лекції (W) не обмежуємо


def test_projects_everywhere_and_stage_done(client, data_dir):
    from app import project
    _w(data_dir / "lectures" / "2026-11-02_1315_so_pp01" / "meta.json",
       {"id": "2026-11-02_1315_so_pp01", "subject_id": "so", "type": "P", "date": "2026-11-02", "time": "13:15", "title": "",
        "files": [], "claude": {"requested": False}, "created_at": _now()})
    made = project.ensure_projects()
    assert project.exists("so") and project.exists("bd") and ("so" in made or project.exists("so"))
    assert project.ensure_projects() == []  # повторно нічого не створює
    _w(data_dir / "subjects" / "so" / "project" / "stages.json", {"stages": [
        {"id": "E1", "title": "Filozofowie", "due": "2026-11-03", "status": "current"},
        {"id": "E2", "title": "Projekt właściwy", "due": "2026-12-01", "status": "next"}]})
    P = client.get("/api/subjects/so/project").json()
    assert P["current_stage"] == "E1"
    P = client.post("/api/subjects/so/project/stage-done", json={"stage": "E1"}).json()
    assert P["current_stage"] == "E2" and P["stages"][0]["status"] == "done"
    client.post("/api/subjects/so/project/step", json={})
    q = json.loads((data_dir / "queue.json").read_text(encoding="utf-8"))
    item = next(x for x in q["project_steps"] if x["subject_id"] == "so")
    assert item["current_stage"] == "E2" and item["stages_done"] == ["E1"]
    client.delete("/api/subjects/so/project/step")
    P = client.post("/api/subjects/so/project/stage-done", json={"stage": "E1", "done": False}).json()
    assert P["current_stage"] == "E1"


def test_protocol_rules_present():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    core = (root / "app" / "CLAUDE.md").read_text(encoding="utf-8")
    f = (root / "app" / "protocol" / "F_plan.md").read_text(encoding="utf-8")
    d = (root / "app" / "protocol" / "D_help.md").read_text(encoding="utf-8")
    assert "оновлюй, а не пиши заново" in core and "progress.done" in core
    assert "з коментарем до кожного рядка" not in core  # не суперечить правилу K
    assert "Zmiany" in f and "instruction_exists" in f and "не створюй" in d.lower()


def test_auto_instruction_deferred_until_free(client, data_dir):
    from app import course, lectures
    lid = "2026-11-02_0730_so_def1"
    _lab(data_dir, lid)
    client.post(f"/api/lectures/{lid}/help", json={"q": "jak zacząć?"})
    course.on_task_added(lid)  # умова прийшла, поки «Допоможи» без відповіді
    m = lectures.read_meta(lid)
    assert m.get("plan_wanted") and not m.get("plan_req")
    hid = m["help"][0]["id"]
    _w(data_dir / "lectures" / lid / "output" / "help.md", f"<!-- help:{hid} -->" + chr(10) + "### x" + chr(10) + "Odpowiedź.")
    lectures.write_queue()
    m = lectures.read_meta(lid)
    assert m.get("plan_req", {}).get("auto") and not m.get("plan_wanted")  # тепер — у черзі сама
