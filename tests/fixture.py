"""Тестові дані для автотестів 2.0 (синтетичні, без реальних даних користувача)."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path


def _w(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) if not isinstance(data, str) else data, encoding="utf-8")


QUIZ_V2 = {"version": 2, "cards": [
    {"type": "mcq", "q": "Który stan procesu oznacza, że czeka na procesor?", "options": ["Gotowy", "Zablokowany", "Wykonywany", "Zakończony"],
     "correct": 0, "traps": {"1": "Zablokowany czeka na zdarzenie (np. I/O), nie na CPU."}, "explain": "Gotowy = ma wszystko oprócz procesora.",
     "hint": ["Pomyśl o kolejce do CPU", "Nie czeka na I/O"], "source": {"t": "00:12:34"}, "tags": ["procesy"], "important": True},
    {"type": "cloze", "q": "Polecenie ___ nadaje prawo wykonania plikowi.", "answer": "chmod", "accept": ["chmod +x"], "explain": "chmod a+x plik.sh",
     "source": "00:05:10"},
    {"type": "tf", "q": "Wątki jednego procesu mają wspólną przestrzeń adresową.", "answer": True, "explain": "Tak — dzielą pamięć, mają własne stosy."},
    {"type": "order", "q": "Ułóż kroki uruchomienia skryptu", "steps": ["Napisz #!/bin/bash", "chmod a+x skrypt.sh", "./skrypt.sh"]},
    {"type": "code", "q": "Co wypisze program?", "code": "x=3\necho $((x*2))", "answer": "6", "mode": "output", "lang": "bash"},
    {"type": "flip", "q": "Kontekst procesu", "a": "Wszystko, co potrzebne do wznowienia procesu: rejestry, pamięć, stan jądra.", "why": "Bez tego nie da się przełączyć procesów.",
     "source": {"section": "2. Procesy"}},
    {"type": "mcq", "q": "Zepsuta karta (zły correct)", "options": ["a", "b"], "correct": 5, "a": "fallback"},
    {"q": "Stara karta v1", "a": "odpowiedź v1", "kind": "qa"},
    {"type": "flip", "q": "Nowa wersja starego pytania", "a": "nowa odpowiedź", "prev": "Stare pytanie przeniesione"},
]}


def make(root: Path) -> Path:
    d = root / "data"
    today = date.today()
    _w(d / "schedule.json", {"version": 1, "subjects": [
        {"id": "so", "name": "Systemy operacyjne", "short": "SO", "color": "#6366f1"},
        {"id": "bd", "name": "Bazy danych 2", "short": "BD2", "color": "#10b981"}],
        "classes": [
            {"id": "c1", "subject_id": "so", "day": 0, "start": "11:15", "end": "13:00", "type": "W", "room": "A-1", "parity": "all"},
            {"id": "c2", "subject_id": "so", "day": 0, "start": "07:30", "end": "09:00", "type": "L", "room": "C-3", "parity": "all"},
            {"id": "c3", "subject_id": "bd", "day": 4, "start": "09:15", "end": "11:00", "type": "P", "room": "D-1", "parity": "all"}]})
    _w(d / "settings.json", {"semester_start": "2026-10-01", "theme": "light", "auto_transcribe": False, "auto_request_claude": False,
                                 "auto_plan": True})  # тести 2.1–2.6 перевіряють автоінструкцію
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    w_id, l_id, p_id = "2026-10-19_1115_so_aaaa", "2026-10-19_0730_so_bbbb", "2026-10-17_0915_bd_cccc"
    for lid, typ, sid, dt in ((w_id, "W", "so", "2026-10-19"), (l_id, "L", "so", "2026-10-19"), (p_id, "P", "bd", "2026-10-17")):
        _w(d / "lectures" / lid / "meta.json", {"id": lid, "subject_id": sid, "type": typ, "date": dt, "time": "11:15", "title": "",
                                                "files": [], "claude": {"requested": False}, "transcribe": {"state": "done"}, "created_at": now})
        out = d / "lectures" / lid / "output"
        _w(out / "notes.md", f"# {sid} {typ}\n\n**Za 1 minutę**\n- punkt\n")
        (out / "notes.pdf").write_bytes(b"%PDF-1.4\n%test\n")
    _w(d / "lectures" / w_id / "transcript.txt", "\n".join(f"[00:{m:02d}:00] zdanie {m}" for m in range(0, 20)))
    _w(d / "lectures" / w_id / "output" / "quiz.json", QUIZ_V2)
    _w(d / "lectures" / w_id / "output" / "result.json", {"status": "done", "completed_at": now, "title": "Procesy i wątki", "summary": "Test."})
    due = (today + timedelta(days=5)).isoformat()
    _w(d / "lectures" / l_id / "output" / "result.json", {"status": "done", "completed_at": now, "title": "Lab 1: skrypty bash",
        "checklist": [{"text": "Sprawozdanie PDF", "due": due}, {"text": "Kod na ePortal", "due": due + "T20:00"}, "Zrzuty ekranu"],
        "todos": [{"title": "Sprawozdanie lab 1", "due": due, "what": "PDF"}]})
    _w(d / "lectures" / l_id / "output" / "quiz.json", {"cards": [{"q": "Jak nadać prawo wykonania?", "a": "chmod a+x plik", "kind": "qa"}]})
    _w(d / "lectures" / p_id / "output" / "result.json", {"status": "done", "completed_at": now, "title": "Projekt: spotkanie 2"})
    # пам'ять предмета і карта курсу
    _w(d / "subjects" / "so" / "memory.md", "# SO — pamięć przedmiotu\n\n## Co przerobiono\n- W1: procesy\n\n## Jak chce prowadzący\n- skrypty z `#!/bin/bash`\n")
    _w(d / "subjects" / "so" / "course_map.json", {"updated_at": now, "items": [
        {"topic": "Procesy i wątki", "lecture_id": w_id, "date": "2026-10-19", "labs": [{"title": "Lab 1: skrypty", "type": "L", "lecture_id": l_id, "how": "ps, kill"}]}]})
    # старий прогрес (Лейтнер v1) для міграції
    import hashlib
    k_old = f"{w_id}:{hashlib.sha1('Stare pytanie przeniesione'.encode()).hexdigest()[:10]}"
    k_v1 = f"{w_id}:{hashlib.sha1('Stara karta v1'.encode()).hexdigest()[:10]}"
    _w(d / "study.json", {"cards": {
        k_v1: {"box": 3, "seen": 3, "due": (today - timedelta(days=1)).isoformat(), "last": now, "last_known": True},
        k_old: {"box": 4, "seen": 4, "due": (today + timedelta(days=10)).isoformat(), "last": now, "last_known": True}}})
    _w(d / "deadlines.json", {"manual": [{"id": "m1", "title": "Kolokwium 1", "due": (today + timedelta(days=10)).isoformat() + "T10:00",
                                          "subject_id": "so", "what": "", "source": "manual"}]})
    return d


if __name__ == "__main__":
    import sys
    print(make(Path(sys.argv[1])))
