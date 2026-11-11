"""2.7: «Робота в чаті» (CHAT.md, журнал, пакет .zip), секрети поза data, автоінструкція за бажанням."""
import io
import json
import zipfile
from datetime import datetime

from fixture import _w

LAB = "2026-11-03_0730_so_chat1"


def _lab(data_dir, lid=LAB):
    d = data_dir / "lectures" / lid
    _w(d / "meta.json", {"id": lid, "subject_id": "so", "type": "L", "date": lid[:10], "time": "07:30", "title": "Lab 4",
                         "files": [{"kind": "task", "name": "zad4.txt", "size": 5, "added_at": datetime.now().astimezone().isoformat()}],
                         "claude": {"requested": False}, "created_at": datetime.now().astimezone().isoformat()})
    _w(d / "task" / "zad4.txt", "Napisz skrypt")
    _w(d / "output" / "plan.json", {"completed_at": "2026-11-01T10:00:00+01:00", "checklist": [{"text": "Skrypt działa"}, {"text": "Sprawozdanie"}]})
    _w(d / "output" / "plan.md", "# Lab 4")
    return d


def test_lecture_chat_md_and_journal(client, data_dir):
    d = _lab(data_dir)
    m = client.get(f"/api/lectures/{LAB}").json()
    cid = next(c["id"] for c in m["checklist"] if c["text"] == "Skrypt działa")
    client.post(f"/api/lectures/{LAB}/checklist/{cid}", json={"done": True})
    C = client.post(f"/api/chat/lecture/{LAB}", json={"note": "krok 3 nie działa"}).json()
    assert C["exists"] and C["prompt"].endswith("працюй за ним.") and C["chat_md"] == f"lectures/{LAB}/CHAT.md"
    md = (d / "CHAT.md").read_text(encoding="utf-8")
    assert "krok 3 nie działa" in md and f"lectures/{LAB}/task/zad4.txt" in md and "protocol/M_chat.md" in md
    assert "відмітив зробленим: Skrypt działa" in md and "Ще не зроблено: Sprawozdanie" in md
    assert "перший чат" in md
    # Claude дописав журнал → наступний CHAT.md його містить, а сторінка лаби показує
    (d / "journal.md").write_text("## 2026-11-03 — Pierwszy czat\n- Zrobione: krok 1\n- Dalej: krok 3\n\n## 2026-11-04 — Poprawki\n- Dalej: sprawozdanie\n", encoding="utf-8")
    L = client.get(f"/api/lectures/{LAB}").json()
    assert [e["title"] for e in L["chat"]["journal"]] == ["2026-11-04 — Poprawki", "2026-11-03 — Pierwszy czat"]
    client.post(f"/api/chat/lecture/{LAB}", json={})
    md = (d / "CHAT.md").read_text(encoding="utf-8")
    assert "Dalej: sprawozdanie" in md and "Студент нічого не дописав" in md


def test_lecture_chat_zip(client, data_dir):
    _lab(data_dir)
    r = client.get(f"/api/chat/lecture/{LAB}/zip")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert "CHAT.md" in names and "protocol/M_chat.md" in names
    assert f"lectures/{LAB}/task/zad4.txt" in names and f"lectures/{LAB}/output/plan.md" in names
    assert not any("meta.json" in n or "eportal" in n or "push" in n for n in names)


def test_chat_only_for_labs_and_bad_ids(client, data_dir):
    w = "2026-11-03_1115_so_chatw"
    _w(data_dir / "lectures" / w / "meta.json", {"id": w, "subject_id": "so", "type": "W", "date": "2026-11-03", "files": [],
                                                  "claude": {"requested": False}, "created_at": datetime.now().astimezone().isoformat()})
    assert client.post(f"/api/chat/lecture/{w}", json={}).status_code == 409
    assert "chat" not in client.get(f"/api/lectures/{w}").json()
    assert client.get("/api/chat/lecture/..%2F..%2Fsettings").status_code == 404
    assert client.get("/api/chat/other/x").status_code == 404
    assert client.get("/api/chat/project/..%2Fx").status_code == 404


def test_project_chat(client, data_dir):
    sid = "bd"
    if not client.get(f"/api/subjects/{sid}/project").json()["exists"]:
        client.post(f"/api/subjects/{sid}/project", json={"title": "Legendy"})
    P = data_dir / "subjects" / sid / "project"
    _w(P / "stages.json", {"stages": [{"id": "E1", "title": "Model", "due": "2026-11-10"}, {"id": "E2", "title": "SQL"}]})
    client.post(f"/api/subjects/{sid}/project/stage-done", json={"stage": "E1", "done": True})
    C = client.post(f"/api/chat/project/{sid}", json={"note": "zaczynamy E2"}).json()
    md = (P / "CHAT.md").read_text(encoding="utf-8")
    assert C["exists"] and "zaczynamy E2" in md and "✓ **E1**" in md and "**E2** SQL ← поточний" in md
    names = zipfile.ZipFile(io.BytesIO(client.get(f"/api/chat/project/{sid}/zip").content)).namelist()
    assert "CHAT.md" in names and f"subjects/{sid}/project/stages.json" in names
    assert not any("/versions/" in n or n.endswith("project.json") for n in names)


def test_secrets_moved_out_of_data(data_dir):
    from app import eportal, push, storage, usos
    assert eportal.EP_FILE.parent == storage.SECRETS_DIR == push.PUSH_FILE.parent
    assert storage.SECRETS_DIR != storage.DATA_DIR and storage.DATA_DIR not in storage.SECRETS_DIR.parents
    _w(data_dir / "push.json", {"vapid": "x"})
    _w(data_dir / "push.json.bak", {"vapid": "old"})
    (storage.SECRETS_DIR / "push.json").unlink(missing_ok=True)
    (storage.SECRETS_DIR / "push.json.bak").unlink(missing_ok=True)
    moved = storage.migrate_secrets()
    assert "push.json" in moved and "push.json.bak" in moved
    assert not (data_dir / "push.json").exists() and json.loads((storage.SECRETS_DIR / "push.json").read_text())["vapid"] == "x"
    # USOS: розклад лишається в data (його читає Claude), посилання з токеном — у secrets
    _w(usos.USOS_FILE, {"url": "https://web.usos.pwr.edu.pl/x?token=SECRET", "events": [{"date": "2026-11-03"}], "weeks": []})
    d = usos.load()
    assert d["url"].endswith("SECRET") and d["events"]
    assert "SECRET" not in usos.USOS_FILE.read_text(encoding="utf-8")
    assert "SECRET" not in (usos.USOS_FILE.parent / "usos.json.bak").read_text(encoding="utf-8")
    assert usos.public_status()["connected"]


def test_auto_plan_is_opt_in():
    from app import schedule
    assert schedule.default_settings()["auto_plan"] is False


def test_protocol_has_chat_section():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "app"
    core = (root / "CLAUDE.md").read_text(encoding="utf-8")
    m = (root / "protocol" / "M_chat.md").read_text(encoding="utf-8")
    assert "protocol/M_chat.md" in core
    assert "journal.md" in m and "## <РРРР-ММ-ДД>" in m and "CHAT.md" in m
