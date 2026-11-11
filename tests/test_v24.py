"""2.4: «Проєкт» — етапи, по одному кроку, один канал до Claude, одна актуальна версія файлу."""
import io
import json
from datetime import datetime, timedelta

from fixture import _w

SID = "bd"


def _now(sec=0):
    return (datetime.now().astimezone() + timedelta(seconds=sec)).isoformat(timespec="seconds")


def _meeting(data_dir, lid="2026-10-17_0938_bd_pm01"):
    _w(data_dir / "lectures" / lid / "meta.json", {"id": lid, "subject_id": SID, "type": "P", "date": lid[:10], "time": "09:38", "title": "",
                                                    "files": [], "claude": {"requested": False}, "created_at": _now()})
    return lid


def _upload(client, area, name, data=b"x"):
    return client.post(f"/api/subjects/{SID}/project/files", files={"file": (name, io.BytesIO(data))}, data={"area": area})


def test_project_flow_one_step_at_a_time(client, data_dir):
    P = client.get(f"/api/subjects/{SID}/project").json()
    assert P["exists"] and P["title"].startswith("Projekt") and P["next_n"] == 1  # 2.6: створено само — у розкладі BD є P
    assert client.post(f"/api/subjects/{SID}/project", json={"title": "x"}).status_code == 409

    lid = _meeting(data_dir)
    P = client.post(f"/api/subjects/{SID}/project/step", json={"note": "zaczynamy"}).json()
    assert P["pending"] and P["req"]["n"] == 1
    # поки крок готується — другий запит, «Допоможи» і звіт на зустрічі проєкту не приймаються
    assert client.post(f"/api/subjects/{SID}/project/step", json={}).status_code == 409
    assert client.post(f"/api/lectures/{lid}/help", json={"q": "Dorób projekt"}).status_code == 400
    assert client.post(f"/api/lectures/{lid}/report", json={"kind": "draft"}).status_code == 400
    q = json.loads((data_dir / "queue.json").read_text(encoding="utf-8"))
    item = next(x for x in q["project_steps"] if x["subject_id"] == SID)
    assert item["n"] == 1 and item["output"]["md"].endswith("steps/step_01.md") and item["meetings"]
    assert client.get(f"/api/lectures/{lid}").json()["project_meeting"] is True

    # Claude пише крок: спершу .md, ОСТАННІМ — .json
    sd = data_dir / "subjects" / SID / "project" / "steps"
    _w(sd / "step_01.md", "## Мета кроку\nZaimportuj XMI.")
    _w(sd / "step_01.json", {"completed_at": _now(5), "title": "Import XMI", "stage": "E2", "minutes": 20,
                             "check": "9 aktorów", "send_back": ["BD_Legendy.vpp"]})
    P = client.get(f"/api/subjects/{SID}/project").json()
    assert not P["pending"] and P["open_step"]["n"] == 1 and P["open_step"]["send_back"] == ["BD_Legendy.vpp"]
    assert P["current_stage"] == "E2"
    P = client.post(f"/api/subjects/{SID}/project/step/1/done", json={"done": True}).json()
    assert P["open_step"] is None and P["steps"][0]["done"] and P["next_n"] == 2
    P = client.post(f"/api/subjects/{SID}/project/step", json={"kind": "next"}).json()
    assert P["req"]["n"] == 2
    client.delete(f"/api/subjects/{SID}/project/step")
    assert not client.get(f"/api/subjects/{SID}/project").json()["pending"]


def test_project_files_versioning_and_promote(client, data_dir):
    if not client.get(f"/api/subjects/{SID}/project").json()["exists"]:
        client.post(f"/api/subjects/{SID}/project", json={"title": "Legendy"})
    assert _upload(client, "current", "Projekt_Etap1.docx", b"v1").status_code == 200
    P = _upload(client, "current", "Projekt_Etap1.docx", b"v2").json()
    assert [f["name"] for f in P["files"]["current"]].count("Projekt_Etap1.docx") == 1
    assert any(f["name"].startswith("Projekt_Etap1__") for f in P["files"]["versions"])  # стара версія не загубилась
    cur = client.get(f"/api/subjects/{SID}/project/file/current/Projekt_Etap1.docx").content
    assert cur == b"v2"
    assert _upload(client, "work", ".~lock.Projekt.docx#").status_code == 409  # тимчасові файли LibreOffice не приймаємо
    _upload(client, "work", "Projekt_Etap1.docx", b"v3 moje poprawki")
    P = client.post(f"/api/subjects/{SID}/project/promote", json={"name": "Projekt_Etap1.docx"}).json()
    assert client.get(f"/api/subjects/{SID}/project/file/current/Projekt_Etap1.docx").content == b"v3 moje poprawki"
    assert sum(f["name"].startswith("Projekt_Etap1__") for f in P["files"]["versions"]) == 2
    assert client.get(f"/api/subjects/{SID}/project/file/current/..%2F..%2Fmemory.md").status_code == 404
    assert any("Актуальне" in c["text"] for c in P["changelog"])


def test_temp_files_hidden_in_lecture_output(client, data_dir):
    lid = _meeting(data_dir, "2026-10-18_0938_bd_pm02")
    out = data_dir / "lectures" / lid / "output"
    _w(out / "notes.md", "# x")
    (out / ".~lock.Raport.pdf#").write_text("x")
    (out / "lu123.tmp").write_text("x")
    (out / "zdacha").mkdir(parents=True, exist_ok=True)
    (out / "zdacha" / "~$Raport.docx").write_text("x")
    L = client.get(f"/api/lectures/{lid}").json()
    names = [f["name"] for f in L["output"]["files"]] + [d["name"] for d in L["output"]["deliverables"]]
    assert not any("lock" in n or n.endswith(".tmp") or "~$" in n for n in names), names


def test_no_auto_plan_for_project_meeting(client, data_dir):
    from app import course
    lid = _meeting(data_dir, "2026-10-19_0938_bd_pm03")
    if not client.get(f"/api/subjects/{SID}/project").json()["exists"]:
        client.post(f"/api/subjects/{SID}/project", json={"title": "Legendy"})
    assert course.on_task_added(lid) is False


def test_migration_tool_dry_run_and_apply(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    data = tmp_path / "data"
    L = data / "lectures" / "2026-10-17_0938_bd_mig1"
    _w(L / "meta.json", {"id": L.name, "subject_id": "bd", "type": "P", "date": "2026-10-17", "files": [],
                         "claude": {"requested": False}, "plan_req": {"requested_at": _now()}, "created_at": _now()})
    _w(L / "output" / "Projekt R.5.docx", "doc5")
    _w(L / "output" / "projekt_R4.md", "r4")
    _w(L / "output" / "result.json.bak", {"status": "done", "title": "Stary", "summary": "17.10"})
    _w(L / "output" / "result.json", {"status": "done", "title": "v5", "todos": [{"title": "Aktorzy", "due": "2026-10-30"}]})
    _w(data / "schedule.json", {"version": 1, "subjects": [{"id": "bd", "name": "Bazy danych 2", "short": "BD2", "color": "#10b981"}], "classes": []})
    plan = tmp_path / "plan.json"
    _w(plan, {"vars": {"L": f"lectures/{L.name}", "P": "subjects/bd/project"}, "actions": [
        ["project_create", "bd", "Legendy"],
        ["move", "{L}/output/Projekt R.5.docx", "{P}/current/Projekt_Etap1.docx"],
        ["move", "{L}/output/projekt_R4.md", "{P}/versions/Projekt_Etap1__R4.md"],
        ["move", "{L}/output/nie_ma.md", "{P}/versions/x.md"],
        ["result_meeting", "{L}", "Konsultacja 17.10", "Pliki — w Projekcie."],
        ["meta_pop", L.name, ["plan_req"]]]})
    cmd = [sys.executable, str(root / "tools" / "migrate_project.py"), str(data), str(plan)]
    dry = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert "Буде виконано" in dry.stdout and (L / "output" / "Projekt R.5.docx").exists()  # без --apply нічого не змінилось
    run = subprocess.run(cmd + ["--apply"], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    P = data / "subjects" / "bd" / "project"
    assert (P / "current" / "Projekt_Etap1.docx").read_text() == "doc5" and (P / "versions" / "Projekt_Etap1__R4.md").exists()
    assert "пропущено: 1" in run.stdout
    res = json.loads((L / "output" / "result.json").read_text(encoding="utf-8"))
    assert res["title"] == "Konsultacja 17.10" and res["checklist"] == [] and res["todos"][0]["title"] == "Aktorzy"
    assert "plan_req" not in json.loads((L / "meta.json").read_text(encoding="utf-8"))
    rerun = subprocess.run(cmd + ["--apply"], capture_output=True, text=True, encoding="utf-8")
    assert "ціль уже є" in rerun.stdout or "немає" in rerun.stdout  # повторний запуск нічого не ламає
