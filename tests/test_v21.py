"""2.1: план до лаби з умови завдання; підбір файлів з ePortalu за змістом; «нові матеріали» на обробленому занятті."""
import json
import time
from datetime import datetime, timedelta

from fixture import _w

L_ID = "2026-10-19_0730_so_bbbb"


def _now(sec=0):
    return (datetime.now().astimezone() + timedelta(seconds=sec)).isoformat(timespec="seconds")


def test_task_upload_queues_plan(client, data_dir):
    r = client.post(f"/api/lectures/{L_ID}/files", files={"file": ("zadanie.txt", b"Napisz skrypt bash liczacy pliki", "text/plain")},
                    data={"kind": "task"})
    assert r.status_code == 200
    p = client.get(f"/api/lectures/{L_ID}/plan").json()
    assert p["pending"] and p["auto"]
    q = json.loads((data_dir / "queue.json").read_text(encoding="utf-8"))
    pl = [x for x in q["plans"] if x["lecture_id"] == L_ID]
    assert pl and "task/zadanie.txt" in pl[0]["task_files"] and pl[0]["output"]["json"].endswith("plan.json")
    assert "context" in pl[0] and pl[0]["type"] == "L"
    assert client.get("/api/state").json()["plans_waiting"] >= 1
    assert "у черзі" in client.get("/api/claude-prompt").text


def test_plan_done_merges_checklist_and_todos(client, data_dir):
    out = data_dir / "lectures" / L_ID / "output"
    due = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    _w(out / "plan.md", "# Plan\n\n1. Krok")
    time.sleep(1.1)
    _w(out / "plan.json", {"completed_at": _now(), "checklist": [{"text": "Przygotować skrypt"}, {"text": "Sprawozdanie PDF"}],
                           "todos": [{"title": "Lab 1: oddać skrypt", "due": due}]})
    p = client.get(f"/api/lectures/{L_ID}/plan").json()
    assert not p["pending"] and p["has_plan"] and "Krok" in p["md"]
    L = client.get(f"/api/lectures/{L_ID}").json()
    texts = [i["text"] for i in L["checklist"]]
    assert "Przygotować skrypt" in texts and texts.count("Sprawozdanie PDF") == 1  # без дублікатів з result.json
    dl = client.get("/api/deadlines").json()
    assert any(d["title"] == "Lab 1: oddać skrypt" and d["id"].startswith("lecp:") for d in dl)
    time.sleep(1.1)
    client.post(f"/api/lectures/{L_ID}/plan", json={"note": "jeszcze raz"})
    q = json.loads((data_dir / "queue.json").read_text(encoding="utf-8"))
    assert any(x["lecture_id"] == L_ID and x["note"] == "jeszcze raz" for x in q["plans"])
    client.delete(f"/api/lectures/{L_ID}/plan")


def test_plan_only_for_practice(client):
    assert client.post("/api/lectures/2026-10-19_1115_so_aaaa/plan", json={}).status_code == 400


def _ep_setup(data_dir):
    from app import eportal
    files = data_dir / "subjects" / "so" / "files"
    _w(files / "wyklad_A.txt", "Semafory i muteksy. Sekcja krytyczna, zakleszczenie, warunki Coffmana, problem producenta i konsumenta. "
                               "Semafor binarny, semafor zliczający, operacje wait i signal, zakleszczenie i zagłodzenie. " * 3)
    _w(files / "wyklad_B.txt", "Pamięć wirtualna, stronicowanie, ramki, tablica stron, segmentacja, algorytmy wymiany stron LRU FIFO. " * 3)
    _w(files / "wyklad_C.txt", "System plików, i-węzły, katalogi, dowiązania twarde i symboliczne, uprawnienia plików. " * 3)
    _w(files / "Lab3_instrukcja.txt", "Laboratorium 3: skrypty powłoki, pętle for, warunki if, zmienne środowiskowe. " * 3)
    ep = {"courses": [], "course_map": {}, "files": {
        "1:10:/wyklad_A.txt": {"subject_id": "so", "course_type": "W", "section": "Wykłady", "module": "Materiały", "filename": "wyklad_A.txt", "saved": "wyklad_A.txt", "uploaded": 1},
        "1:11:/wyklad_B.txt": {"subject_id": "so", "course_type": "W", "section": "Wykłady", "module": "Materiały", "filename": "wyklad_B.txt", "saved": "wyklad_B.txt", "uploaded": 1},
        "1:12:/wyklad_C.txt": {"subject_id": "so", "course_type": "W", "section": "Wykłady", "module": "Materiały", "filename": "wyklad_C.txt", "saved": "wyklad_C.txt", "uploaded": 1},
        "2:20:/Lab3_instrukcja.txt": {"subject_id": "so", "course_type": "L", "section": "Laboratorium", "module": "Instrukcje", "filename": "Lab3_instrukcja.txt", "saved": "Lab3_instrukcja.txt", "uploaded": 1},
    }}
    _w(eportal.EP_FILE, ep)


def test_eportal_content_match_and_new_flag(client, data_dir):
    from app import eportal, lectures
    _ep_setup(data_dir)
    lid = "2026-10-12_1115_so_dddd"
    _w(data_dir / "lectures" / lid / "meta.json", {"id": lid, "subject_id": "so", "type": "W", "date": "2026-10-12", "time": "11:15", "title": "",
                                                    "files": [], "claude": {"requested": False}, "created_at": _now()})
    _w(data_dir / "lectures" / lid / "transcript.txt", "[00:01:00] Dzisiaj semafory. Sekcja krytyczna i zakleszczenie, warunki Coffmana. "
                                                       "Producent i konsument, semafor binarny, operacja wait i signal, muteksy.")
    out = data_dir / "lectures" / lid / "output"
    _w(out / "notes.md", "# x"); (out / "notes.pdf").write_bytes(b"%PDF-1.4\n")
    _w(out / "result.json", {"status": "done", "completed_at": _now(-60), "title": "Synchronizacja"})
    c = eportal.candidates(lid)
    assert c[0]["file"] == "wyklad_A.txt" and any(w.startswith("зміст") for w in c[0]["why"]), c[:2]
    assert eportal.auto_attach(lid) == 1
    m = lectures.read_meta(lid)
    assert "1:10:/wyklad_A.txt" in m["eportal_attached"] and m["eportal_new"][0]["name"] == "wyklad_A.txt"
    assert eportal.auto_attach(lid) == 0  # уже переглянуто — не повторюємо
    L = client.post(f"/api/lectures/{lid}/eportal-new", json={"action": "update"}).json()
    assert L["status"] == "waiting_claude" and "wyklad_A.txt" in L["claude"]["instructions"] and not L["eportal_new"]


def test_eportal_lab_file_goes_to_task_and_plan(client, data_dir):
    from app import eportal, lectures
    _ep_setup(data_dir)
    lid = "2026-10-26_0730_so_eeee"
    _w(data_dir / "lectures" / lid / "meta.json", {"id": lid, "subject_id": "so", "type": "L", "date": "2026-10-26", "time": "07:30", "title": "",
                                                    "user_notes": "Lab 3: skrypty powłoki, pętle i warunki", "files": [],
                                                    "claude": {"requested": False}, "created_at": _now()})
    cands = eportal.candidates(lid)
    lab = next(x for x in cands if x["file"] == "Lab3_instrukcja.txt")
    assert lab["as_task"] and lab["score"] >= 3
    eportal.attach(lid, lab["key"])
    m = lectures.read_meta(lid)
    assert any(f["kind"] == "task" and f["source"] == "eportal" for f in m["files"])
    assert m.get("plan_req", {}).get("auto")
    (eportal.EP_FILE).unlink()


def test_eportal_content_beats_wrong_ordinal(client, data_dir):
    """USOS рахує організаційне заняття як Lab 1 → порядковий номер зсунутий; зміст «[1] …» має переважити «№2»."""
    from app import eportal, lectures
    files = data_dir / "subjects" / "so" / "files"
    lid = "2026-10-27_0730_so_ffff"
    _w(data_dir / "lectures" / lid / "meta.json", {"id": lid, "subject_id": "so", "type": "L", "date": "2026-10-27", "time": "07:30", "title": "",
                                                    "files": [], "claude": {"requested": False}, "created_at": _now()})
    _w(data_dir / "lectures" / lid / "transcript.txt", "[00:01:00] Szacowanie pasma łącza. Przepustowość, opóźnienie, Wireshark, "
                                                       "pomiar transferu, przepustowość łącza internetowego, pasmo i opóźnienie.")
    n = eportal._lecture_ordinal(lectures.read_meta(lid))
    assert n >= 2
    _w(files / "[1] Szacowanie pasma.txt", "Szacowanie pasma: przepustowość łącza, opóźnienie, pomiar transferu w Wireshark. " * 3)
    _w(files / f"[{n}] Konfiguracja sieci.txt", "Konfiguracja routera, adresacja, maska podsieci, serwer DHCP, brama domyślna. " * 3)
    _w(files / "Regulamin.txt", "Zasady zaliczenia, obecność, oceny, kontakt z prowadzącym, konsultacje. " * 3)
    ep = {"courses": [], "course_map": {}, "files": {
        f"3:1:/{nm}": {"subject_id": "so", "course_type": "L", "section": sec, "module": "Opis ćwiczenia", "filename": nm, "saved": nm, "uploaded": 1}
        for nm, sec in (("[1] Szacowanie pasma.txt", "Temat 1: Szacowanie pasma"), (f"[{n}] Konfiguracja sieci.txt", f"Temat {n}: Konfiguracja sieci"),
                        ("Regulamin.txt", "General"))}}
    _w(eportal.EP_FILE, ep)
    c = eportal.candidates(lid)
    assert c[0]["file"] == "[1] Szacowanie pasma.txt", c
    wrong = next(x for x in c if x["file"].startswith(f"[{n}]"))
    assert wrong["score"] < 3 and f"№{n}" not in wrong["why"], wrong
    assert eportal.auto_attach(lid) == 1
    assert lectures.read_meta(lid)["eportal_attached"] == ["3:1:/[1] Szacowanie pasma.txt"]
    (eportal.EP_FILE).unlink()
