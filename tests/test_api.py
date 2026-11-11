"""API-тести релізу 2.0 (на синтетичних даних)."""
import json
import hashlib
from datetime import datetime, timedelta

W = "2026-10-19_1115_so_aaaa"
L = "2026-10-19_0730_so_bbbb"


def key(lid, q):
    return f"{lid}:{hashlib.sha1(q.strip().encode()).hexdigest()[:10]}"


def test_version_and_beta(client):
    st = client.get("/api/state").json()
    assert st["version"].startswith("2.") and st["beta"] is True
    assert {"help_waiting", "explain_waiting"} <= set(st)


def test_migration_v1_to_fsrs(client, data_dir):
    client.get("/api/study")
    d = json.loads((data_dir / "study.json").read_text("utf-8"))
    assert d["version"] == 2
    assert (data_dir / "study.v1.json").exists()
    p = d["cards"][key(W, "Stara karta v1")]
    assert p["state"] == "review" and p["s"] >= 3 and p["migrated"] == "leitner"


def test_card_types_normalized(client):
    cards = {c["q"]: c for c in client.get(f"/api/study?lecture={W}").json()["cards"]}
    assert cards["Który stan procesu oznacza, że czeka na procesor?"]["type"] == "mcq"
    mcq = cards["Który stan procesu oznacza, że czeka na procesor?"]
    assert mcq["correct"] == 0 and mcq["traps"]["1"] and mcq["important"] and mcq["source"]["sec"] == 754
    assert cards["Polecenie ___ nadaje prawo wykonania plikowi."]["source"]["sec"] == 310
    assert cards["Wątki jednego procesu mają wspólną przestrzeń adresową."]["answer"] is True
    assert cards["Ułóż kroki uruchomienia skryptu"]["steps"][0].startswith("Napisz")
    assert cards["Co wypisze program?"]["code"]
    assert cards["Zepsuta karta (zły correct)"]["type"] == "flip"  # невалідний mcq → flip
    assert cards["Stara karta v1"]["type"] == "flip"
    assert cards["Kontekst procesu"]["why"]


def test_progress_moves_with_prev(client, data_dir):
    cards = {c["q"]: c for c in client.get(f"/api/study?lecture={W}").json()["cards"]}
    c = cards["Nowa wersja starego pytania"]
    assert not c["is_new"] and c["s"] >= 14  # прогрес старої картки перенесено
    d = json.loads((data_dir / "study.json").read_text("utf-8"))
    assert d["cards"][c["key"]]["moved_from"] == key(W, "Stare pytanie przeniesione")


def test_today_session_and_new_limit(client):
    client.put("/api/settings", json={"study_new_per_day": 3})
    s = client.get("/api/study/session?mode=today").json()
    assert s["mode"] == "today" and s["new_left"] == 3
    assert sum(1 for c in s["cards"] if c["is_new"]) <= 3
    assert all(set(c["next"]) == {"1", "2", "3", "4"} for c in s["cards"])
    client.put("/api/settings", json={"study_new_per_day": 15})


def test_answer_fsrs_and_log(client):
    s = client.get(f"/api/study/session?mode=all&lecture={W}").json()
    c = next(x for x in s["cards"] if x["is_new"])
    r = client.post("/api/study/answer", json={"key": c["key"], "rating": 3, "ms": 4000}).json()
    assert r["state"] == "review" and r["ivl"] >= 1
    r1 = client.post("/api/study/answer", json={"key": c["key"], "rating": 1}).json()
    assert r1["state"] == "relearning" and r1["lapses"] == 1
    assert client.post("/api/study/answer", json={"key": c["key"], "rating": 7}).status_code == 400
    p = client.get("/api/study/progress").json()
    assert p["today"]["n"] >= 2 and p["streak"] >= 1 and len(p["heatmap"]) > 100


def test_old_known_api_still_works(client):
    c = client.get(f"/api/study?lecture={L}").json()["cards"][0]
    r = client.post("/api/study/answer", json={"key": c["key"], "known": True}).json()
    assert r["rating"] == 3


def test_modes(client):
    t = client.get("/api/study/session?mode=test&subject=so").json()
    assert 0 < len(t["cards"]) <= 20 and t["graded"] is False
    allc = client.get("/api/study?subject=so").json()["cards"]
    auto = [c for c in allc if c["type"] != "flip"]
    assert sum(c["type"] != "flip" for c in t["cards"]) == min(20, len(auto))  # спершу завдання з автоперевіркою
    b = client.get("/api/study/session?mode=blitz").json()
    assert b["seconds"] == 60 and all(isinstance(x["blitz_answer"], bool) for x in b["cards"])
    assert any(x["type"] == "mcq" for x in b["cards"])
    h = client.get("/api/study/session?mode=hard").json()
    assert h["mode"] == "hard"
    client.post("/api/study/activity", json={"mode": "test", "n": 10, "correct": 7, "subject_id": "so", "mistakes": ["x"]})
    assert client.get("/api/study/progress").json()["tests"][0]["score"] == 7


def test_tempo_to_colloquium(client):
    p = client.get("/api/study/progress").json()
    t = p["tempo"][0]
    assert t["title"] == "Kolokwium 1" and t["subject_id"] == "so" and t["days_left"] in (9, 10, 11)
    assert p["subjects"]["so"]["total"] >= 9


def test_manage_edit_hide_important_custom(client):
    c = next(x for x in client.get(f"/api/study?lecture={W}").json()["cards"] if x["type"] == "tf")
    client.patch("/api/study/card", json={"key": c["key"], "q": c["q"], "a": "Tak (poprawione)", "important": True})
    c2 = next(x for x in client.get(f"/api/study?lecture={W}").json()["cards"] if x["key"] == c["key"])
    assert c2["a"] == "Tak (poprawione)" and c2["important"] and c2["edited"]
    client.patch("/api/study/card", json={"key": c["key"], "hidden": True})
    assert c["key"] not in [x["key"] for x in client.get(f"/api/study?lecture={W}").json()["cards"]]
    assert c["key"] in [x["key"] for x in client.get(f"/api/study?lecture={W}&hidden=1").json()["cards"]]
    client.patch("/api/study/card", json={"key": c["key"], "hidden": False, "revert": True})
    c3 = next(x for x in client.get(f"/api/study?lecture={W}").json()["cards"] if x["key"] == c["key"])
    assert c3["a"] != "Tak (poprawione)" and not c3["edited"]
    cc = client.post("/api/study/custom", json={"q": "Moje pytanie", "a": "Moja odpowiedź", "lecture_id": W}).json()
    assert cc["subject_id"] == "so"
    keys = [x["key"] for x in client.get("/api/study?subject=so").json()["cards"]]
    assert "custom:" + cc["id"] in keys
    assert client.post("/api/study/custom", json={"q": "bez odpowiedzi"}).status_code == 400
    assert client.delete(f"/api/study/custom/{cc['id']}").json()["ok"]


def test_explain_queue_roundtrip(client, data_dir):
    c = client.get(f"/api/study?lecture={W}").json()["cards"][0]
    client.post("/api/study/explain", json={"key": c["key"], "note": "nie rozumiem"})
    q = json.loads((data_dir / "queue.json").read_text("utf-8"))
    assert q["explain"][0]["key"] == c["key"]
    assert client.get("/api/state").json()["explain_waiting"] == 1
    later = (datetime.now().astimezone() + timedelta(seconds=5)).isoformat(timespec="seconds")
    (data_dir / "explain_answers.json").write_text(json.dumps({"answers": {c["key"]: {"text": "Prościej: …", "at": later}}}), "utf-8")
    c2 = next(x for x in client.get(f"/api/study?lecture={W}").json()["cards"] if x["key"] == c["key"])
    assert c2["simpler"] == "Prościej: …" and c2["explain_pending"] is False
    assert client.get("/api/state").json()["explain_waiting"] == 0


def test_help_checklist_course(client, data_dir):
    m = client.get(f"/api/lectures/{L}").json()
    assert [i["text"] for i in m["checklist"]] == ["Sprawozdanie PDF", "Kod na ePortal", "Zrzuty ekranu"]
    cid = m["checklist"][0]["id"]
    m2 = client.post(f"/api/lectures/{L}/checklist/{cid}", json={"done": True}).json()
    assert m2["checklist"][0]["done"]
    home = client.get("/api/checklists").json()
    assert home[0]["lecture_id"] == L and home[0]["items"][0]["done"]
    hs = client.post(f"/api/lectures/{L}/help", json={"q": "Permission denied?"}).json()
    hid = hs[0]["id"]
    assert not hs[0]["answered"]
    q = json.loads((data_dir / "queue.json").read_text("utf-8"))
    assert q["help"][0]["lecture_id"] == L
    (data_dir / "lectures" / L / "output" / "help.md").write_text(f"# Pomoc\n\n<!-- help:{hid} -->\nZrób `chmod a+x`.\n", "utf-8")
    hs2 = client.get(f"/api/lectures/{L}/help").json()
    assert hs2[0]["answered"] and "chmod" in hs2[0]["answer"]
    assert client.get("/api/state").json()["help_waiting"] == 0
    crs = client.get("/api/subjects/so/course").json()
    assert "pamięć" in crs["memory"]["text"] and crs["map"]["items"][0]["labs"][0]["lecture_id"] == L
    assert client.post(f"/api/lectures/{L}/help", json={"q": " "}).status_code == 400


def test_task_and_code_upload(client, data_dir):
    r = client.post(f"/api/lectures/{L}/files", files={"file": ("zadanie.png", b"\x89PNG fake", "image/png")}, data={"kind": "task"})
    assert r.json()["file"]["kind"] == "task"
    r = client.post(f"/api/lectures/{L}/files", files={"file": ("main.c", b"int main(){return 0;}", "text/x-c")}, data={"kind": "code"})
    assert r.json()["file"]["kind"] == "code"
    assert (data_dir / "lectures" / L / "task" / "zadanie.png").exists()
    assert client.get(f"/api/lectures/{L}/files/code/main.c").text.startswith("int main")
    m = client.get(f"/api/lectures/{L}").json()
    assert {f["kind"] for f in m["files"]} >= {"task", "code"}


def test_queue_context_for_claude(client, data_dir):
    import time
    time.sleep(1.1)
    r = client.post(f"/api/lectures/{L}/claude", json={"instructions": ""})
    if r.status_code == 409:  # 2.6: один запит за раз — спершу завершити/скасувати незроблений (автоплан)
        assert "ще працює" in r.json()["detail"]
        client.delete(f"/api/lectures/{L}/plan")
        assert client.post(f"/api/lectures/{L}/claude", json={"instructions": ""}).status_code == 200
    q = json.loads((data_dir / "queue.json").read_text("utf-8"))
    e = next(x for x in q["lectures"] if x["id"] == L)
    assert "done" in e["progress"]  # 2.6: Claude бачить, що вже зроблено
    assert e["context"]["memory"] == "subjects/so/memory.md"
    assert e["context"]["lectures_w"][0]["folder"] == f"lectures/{W}"
    client.delete(f"/api/lectures/{L}/claude")


def test_beta_blocks_integrations(client):
    assert client.post("/api/remote/enable").status_code == 400
    assert client.post("/api/eportal/connect").status_code == 400
    assert client.post("/api/usos/connect", json={"url": "x"}).status_code == 400


def test_fsrs_unit():
    from app import fsrs
    now = datetime.now().astimezone()
    c = fsrs.review(None, 3, now)
    p = fsrs.preview(c, now + timedelta(days=c["ivl"]))
    ivls = [p[str(g)] for g in (1, 2, 3, 4)]
    assert ivls[0].endswith("хв")
    c4 = fsrs.review(c, 4, now + timedelta(days=c["ivl"]))
    c3 = fsrs.review(c, 3, now + timedelta(days=c["ivl"]))
    c2 = fsrs.review(c, 2, now + timedelta(days=c["ivl"]))
    assert c2["ivl"] < c3["ivl"] < c4["ivl"]
    m = fsrs.from_leitner({"box": 5, "seen": 6, "due": "2026-11-01", "last_known": True})
    assert m["s"] == 30 and m["state"] == "review"
