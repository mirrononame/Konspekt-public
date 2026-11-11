"""2.9: «Поділитися конспектами» — пакет для однокурсника і його імпорт; порожній розклад для нового користувача."""
import io
import json
import zipfile


def _pack(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data if isinstance(data, (bytes, str)) else json.dumps(data, ensure_ascii=False))
    return buf.getvalue()


def test_export_has_notes_but_no_private_data(client, data_dir):
    subs = client.get("/api/share/subjects").json()
    so = next(s for s in subs if s["id"] == "so")
    assert so["notes"] >= 1
    r = client.post("/api/share/export", json={"subjects": ["so"], "author": "Dima"})
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    info = json.loads(z.read("share.json"))
    assert info["author"] == "Dima" and info["subjects"][0]["id"] == "so" and info["lectures"] >= 1
    assert any(n.endswith("/output/notes.pdf") for n in names)
    bad = ("audio/", "images/", "transcript.txt", "help.md", "quiz.json", "eportal", "push", "study", "grades", "CHAT.md", "journal.md")
    assert not [n for n in names if any(b in n for b in bad)], names
    meta = json.loads(z.read(next(n for n in names if n.endswith("meta.json"))))
    assert "user_notes" not in meta and "claude" not in meta
    assert client.post("/api/share/export", json={"subjects": []}).status_code == 400


def test_import_new_subject_and_lectures(client, data_dir):
    pack = _pack({
        "share.json": {"format": 1, "app": "Konspekt", "author": "Ola", "subjects": [{"id": "am", "name": "Analiza matematyczna", "short": "AM"}]},
        "subjects/am/memory.md": "# AM — pamięć",
        "lectures/2026-10-05_0915_am_aaaa/meta.json": {"id": "x", "subject_id": "am", "type": "W", "date": "2026-10-05", "time": "09:15",
                                                       "title": "Granice", "files": [{"kind": "task", "name": "z.txt"}]},
        "lectures/2026-10-05_0915_am_aaaa/output/notes.pdf": b"%PDF-1.4 x",
        "lectures/2026-10-05_0915_am_aaaa/output/notes.md": "# Granice",
        "lectures/2026-10-05_0915_am_aaaa/output/result.json": {"status": "done", "completed_at": "2026-10-05T20:00:00+02:00", "title": "Granice"},
        "lectures/2026-10-05_0915_am_aaaa/task/z.txt": "Zadanie",
    })
    p = client.post("/api/share/preview", files={"file": ("p.zip", pack)}).json()
    assert p["author"] == "Ola" and p["subjects"][0]["match"] is None and p["subjects"][0]["new"] == 1
    r = client.post("/api/share/import", json={"token": p["token"]}).json()
    assert r["subjects_added"] == ["Analiza matematyczna"] and r["lectures_new"] == 1
    sid = next(s["id"] for s in client.get("/api/schedule").json()["subjects"] if s["name"] == "Analiza matematyczna")
    L = next(m for m in client.get("/api/lectures").json() if m["subject_id"] == sid)
    assert L["status"] == "done" and L["shared"]["from"] == "Ola" and any(f["kind"] == "task" for f in L["files"])
    assert (data_dir / "subjects" / sid / "memory.md").read_text(encoding="utf-8") == "# AM — pamięć"
    # той самий пакет удруге — нічого не дублюється
    p2 = client.post("/api/share/preview", files={"file": ("p.zip", pack)}).json()
    assert p2["subjects"][0]["match"] == "Analiza matematyczna" and p2["subjects"][0]["skip"] == 1
    r2 = client.post("/api/share/import", json={"token": p2["token"]}).json()
    assert r2["lectures_new"] == 0 and r2["lectures_skipped"] == 1 and r2["subjects_added"] == []


def test_import_never_overwrites_own_notes(client, data_dir):
    own = (data_dir / "lectures" / "2026-10-19_1115_so_aaaa" / "output" / "notes.md")
    before = own.read_bytes()
    pack = _pack({
        "share.json": {"format": 1, "app": "Konspekt", "subjects": [{"id": "so", "name": "Systemy operacyjne", "short": "SO"}]},
        "lectures/q/meta.json": {"subject_id": "so", "type": "W", "date": "2026-10-19", "time": "11:15"},
        "lectures/q/output/notes.md": "CUDZE", "lectures/q/output/notes.pdf": b"%PDF",
    })
    tok = client.post("/api/share/preview", files={"file": ("p.zip", pack)}).json()["token"]
    assert client.post("/api/share/import", json={"token": tok}).json()["lectures_skipped"] == 1
    assert own.read_bytes() == before


def test_bad_packs_rejected(client):
    evil = _pack({"share.json": {"format": 1, "app": "Konspekt", "subjects": []}, "../../evil.txt": "x"})
    assert client.post("/api/share/preview", files={"file": ("e.zip", evil)}).status_code == 400
    assert client.post("/api/share/preview", files={"file": ("e.zip", b"not a zip")}).status_code == 400
    assert client.post("/api/share/preview", files={"file": ("e.zip", _pack({"a.txt": "x"}))}).status_code == 400
    assert client.post("/api/share/import", json={"token": "../../x"}).status_code == 404


def test_new_user_starts_with_empty_schedule():
    from app import schedule
    assert schedule.default_schedule()["subjects"] == []


def test_public_copy_has_no_private_files(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    import pytest
    root = Path(__file__).resolve().parent.parent
    if not (root / "tools" / "make_public.py").exists():
        pytest.skip("це вже публічна копія — збирати нічого")
    out = tmp_path / "pub"
    r = subprocess.run([sys.executable, str(root / "tools" / "make_public.py"), f"--src={root}", f"--out={out}"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    names = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert {"README.md", "LICENSE", ".gitignore", "CLAUDE.md", "app/server.py", "app/share.py"} <= names
    assert not any(n.startswith(("data/", "secrets/", "beta/", "releases/")) or "make_public" in n or "migrations/" in n for n in names)
    assert "/data/" in (out / ".gitignore").read_text(encoding="utf-8")
    other = tmp_path / "other"
    other.mkdir()
    (other / "keep.txt").write_text("x")
    r = subprocess.run([sys.executable, str(root / "tools" / "make_public.py"), f"--src={root}", f"--out={other}"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 2 and (other / "keep.txt").exists()  # чужу папку не чистить


def test_duplicate_files_stored_once(client, data_dir):
    pack = _pack({
        "share.json": {"format": 1, "app": "Konspekt", "subjects": [{"id": "fz", "name": "Fizyka", "short": "FZ"}],
                       "aliases": {"lectures/b/task/opis.pdf": "lectures/a/task/opis.pdf"}},
        "lectures/a/meta.json": {"subject_id": "fz", "type": "L", "date": "2026-10-06", "files": [{"kind": "task", "name": "opis.pdf"}]},
        "lectures/a/output/notes.pdf": b"%PDF a", "lectures/a/task/opis.pdf": b"%PDF opis",
        "lectures/b/meta.json": {"subject_id": "fz", "type": "L", "date": "2026-10-13", "files": [{"kind": "task", "name": "opis.pdf"}]},
        "lectures/b/output/notes.pdf": b"%PDF b",
    })
    tok = client.post("/api/share/preview", files={"file": ("p.zip", pack)}).json()["token"]
    assert client.post("/api/share/import", json={"token": tok}).json()["lectures_new"] == 2
    got = [p for p in data_dir.glob("lectures/2026-10-13_*/task/opis.pdf")]
    assert got and got[0].read_bytes() == b"%PDF opis"
    bad = _pack({"share.json": {"format": 1, "app": "Konspekt", "subjects": [], "aliases": {"../x": "share.json"}}})
    assert client.post("/api/share/preview", files={"file": ("e.zip", bad)}).status_code == 400
