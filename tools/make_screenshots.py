"""Скріншоти для інструкції (docs/) — на вигаданих демо-даних, трьома мовами інтерфейсу.

  python tools/make_screenshots.py [--out=tools/public/docs/img]

Реальні дані студента не використовуються: скрипт збирає демо-папку у тимчасовій теці (основа — tests/fixture.py,
плюс справжні PDF, інструкція до лаби, журнал чату, проєкт з етапами), запускає бету на вільному порту й знімає
однакові екрани українською, англійською й російською. Шлях до папки й позначку бети на знімках замінює на нейтральні.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))
import fixture  # noqa: E402

W, L, P = "2026-10-19_1115_so_aaaa", "2026-10-19_0730_so_bbbb", "2026-10-17_0915_bd_cccc"
NOTES = """# Systemy operacyjne — Procesy i wątki (wersja „na szybko”)
**Przedmiot:** Systemy operacyjne · **Data:** 19.10.2026 · Czas nauki: ok. 1 godz.

## Za 1 minutę
- Proces to uruchomiony program z własną pamięcią.
- Wątek to „lżejszy” proces: dzieli pamięć z innymi wątkami.
- fork() tworzy kopię procesu, exec() podmienia program.
- Planista decyduje, który proces dostaje procesor.
- Zombie to proces, na który rodzic nie zrobił wait().

## 1. Proces
**Po ludzku:** proces to program, który właśnie działa — ma swój PID, pamięć i otwarte pliki.

**Zapamiętaj:** każdy proces ma unikalny PID, a jego rodzica pokazuje PPID.

## 2. fork() i exec()
**Po ludzku:** fork() robi bliźniaka procesu, exec() zamienia bliźniaka w inny program.

```bash
ps -ef | grep bash
```

**Zapamiętaj:** fork() zwraca 0 w dziecku i PID dziecka w rodzicu.

## Typowe pułapki
- Brak wait() w rodzicu zostawia procesy zombie.
- kill -9 nie daje procesowi szansy na posprzątanie.

## Sprawdź się
1. Co zwraca fork() w procesie potomnym? *(0)*
2. Czym różni się wątek od procesu? *(wątki dzielą pamięć)*
"""
PLAN = """# Systemy operacyjne — Lab 1: skrypty bash (instrukcja)
**Przedmiot:** Systemy operacyjne · **Data:** 19.10.2026

## Cel w 1 zdaniu
Napisać skrypt, który policzy pliki w katalogu i wypisze największy.

## Krok po kroku
**1.** Utwórz plik `licz.sh` i dodaj na początku `#!/bin/bash` (≈ 5 min).

**2.** Nadaj prawo wykonania: `chmod a+x licz.sh` (≈ 2 min).

**3.** Policz pliki pętlą `for` i wypisz wynik (≈ 15 min).

## Do oddania
- Sprawozdanie PDF i kod na ePortal — do terminu z ePortalu.
"""


def _w(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _pdf(md: Path, pdf: Path, title: str) -> None:
    subprocess.run([sys.executable, str(ROOT / "tools" / "mkpdf.py"), str(md), str(pdf), "Konspekt · demo", title],
                   check=True, capture_output=True)


def build_demo() -> Path:
    d = fixture.make(Path(tempfile.mkdtemp(prefix="konspekt-demo-")))
    today = date.today()
    wd = today.weekday()
    sched = json.loads((d / "schedule.json").read_text(encoding="utf-8"))
    sched["subjects"] += [{"id": "ts", "name": "Technologie sieciowe", "short": "TS", "color": "#0ea5e9"},
                          {"id": "io", "name": "Inżynieria oprogramowania", "short": "IO", "color": "#f59e0b"}]
    sched["classes"] += [
        {"id": "d1", "subject_id": "ts", "day": wd, "start": "09:15", "end": "11:00", "type": "W", "room": "C-13", "parity": "all"},
        {"id": "d2", "subject_id": "io", "day": wd, "start": "13:15", "end": "15:00", "type": "L", "room": "C-16", "parity": "all"}]
    _w(d / "schedule.json", sched)
    s = json.loads((d / "settings.json").read_text(encoding="utf-8"))
    s.update(theme="light", auto_plan=False)
    _w(d / "settings.json", s)
    # справжні PDF замість заглушок
    out = d / "lectures" / W / "output"
    _w(out / "notes.md", NOTES)
    _pdf(out / "notes.md", out / "notes.pdf", "Procesy i wątki")
    _w(out / "result.json", {"status": "done", "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                             "title": "Procesy i wątki", "summary": "Procesy, wątki, fork() i exec(), planista i procesy zombie.",
                             "topics": ["procesy", "wątki", "fork/exec", "planowanie"]})
    lab = d / "lectures" / L
    _w(lab / "output" / "plan.md", PLAN)
    _pdf(lab / "output" / "plan.md", lab / "output" / "plan.pdf", "Lab 1: skrypty bash")
    _w(lab / "output" / "plan.json", {"completed_at": datetime.now().astimezone().isoformat(timespec="seconds"), "title": "Lab 1",
                                      "checklist": [{"text": "Skrypt licz.sh działa"}, {"text": "Sprawozdanie PDF"}]})
    _w(lab / "task" / "Lab1_zadanie.pdf", "")
    (lab / "task" / "Lab1_zadanie.pdf").write_bytes((lab / "output" / "plan.pdf").read_bytes())
    meta = json.loads((lab / "meta.json").read_text(encoding="utf-8"))
    meta["files"] = [{"kind": "task", "name": "Lab1_zadanie.pdf", "size": 20000, "added_at": meta["created_at"]}]
    _w(lab / "meta.json", meta)
    _w(lab / "journal.md", "## 2026-10-20 — Pierwszy skrypt\n- Zrobione: krok 1–2, skrypt się uruchamia.\n- Dalej: pętla for (krok 3).\n")
    # проєкт з етапами — через сам застосунок
    os.environ["KONSPEKT_DATA"] = str(d)
    os.environ["KONSPEKT_SECRETS"] = str(d.parent / "secrets")
    from app import project
    if not project.exists("bd"):
        project.create("bd", "System biblioteki")
    _w(project.pdir("bd") / "stages.json", {"stages": [
        {"id": "E1", "title": "Opis świata i wymagania", "due": (today - timedelta(days=7)).isoformat()},
        {"id": "E2", "title": "Przypadki użycia", "due": (today + timedelta(days=9)).isoformat()},
        {"id": "E3", "title": "Projekt bazy danych", "due": (today + timedelta(days=30)).isoformat()}]})
    project.stage_done("bd", "E1", True)
    _w(project.pdir("bd") / "journal.md", "## 2026-10-29 — Etap II\n- Zrobione: lista aktorów i 12 przypadków użycia.\n- Dalej: diagramy w VP.\n")
    return d


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


MASK = r"""() => {
  document.body.classList.remove('is-beta');
  document.querySelectorAll('.beta-badge').forEach(e => e.remove());
  document.querySelectorAll('iframe.pdf-frame').forEach(f => {  // браузер без вікна не малює PDF — показуємо текстову версію
    const d = f.parentElement.querySelector('details'); if (d) d.open = true; f.remove(); });
  document.querySelectorAll('#sidebar-foot span').forEach(e => { e.textContent = e.textContent.replace('-beta', ''); });
  document.querySelectorAll('.mono').forEach(e => { if (/konspekt-demo/.test(e.textContent)) e.textContent = 'C:\\Users\\you\\Documents\\Konspekt\\data'; });
  document.querySelectorAll('#remote-card, #ios-card, .tip').forEach(e => e.style.display = 'none');
  document.querySelectorAll('.toast').forEach(e => e.remove());
}"""


def main() -> int:
    args = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    out = Path(args.get("out", ROOT / "tools" / "public" / "docs" / "img")).resolve()
    app_root = Path(args.get("app", ROOT)).resolve()  # --app=beta — знімати з коду бети
    data = build_demo()
    port = _free_port()
    env = {**os.environ, "KONSPEKT_DATA": str(data), "KONSPEKT_SECRETS": str(data.parent / "secrets"), "KONSPEKT_BETA": "1", "PYTHONUTF8": "1"}
    srv = subprocess.Popen([sys.executable, "-m", "app.server", "--port", str(port), "--no-browser"], cwd=app_root, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(150):
        try:
            urllib.request.urlopen(url + "/api/ping", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    from playwright.sync_api import sync_playwright

    def put_lang(lang):
        req = urllib.request.Request(url + "/api/settings", data=json.dumps({"ui_language": lang}).encode(), method="PUT",
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req).read()

    shots = [("home", "#/", None), ("add", "#/upload", None), ("lecture", f"#/lecture/{W}", None),
             ("lab", f"#/lecture/{L}", None), ("subject", "#/subject/so", None), ("project", "#/subject/bd?tab=project", None),
             ("settings", "#/settings", None), ("claude-share", "#/settings", "#claude-card")]
    n = 0
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            for lang in ("uk", "en", "ru"):
                put_lang(lang)
                (out / lang).mkdir(parents=True, exist_ok=True)
                page = b.new_page(viewport={"width": 1280, "height": 800})
                for name, hash_, el in shots:
                    page.goto(f"{url}/{hash_}")
                    page.wait_for_timeout(1800)
                    page.evaluate(MASK)
                    if el:
                        page.locator(el).locator("xpath=..").screenshot(path=str(out / lang / f"{name}.png"))
                    else:
                        page.screenshot(path=str(out / lang / f"{name}.png"))
                    n += 1
                page.close()
                m = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
                m.goto(f"{url}/#/")
                m.wait_for_timeout(1800)
                m.evaluate(MASK)
                m.screenshot(path=str(out / lang / "phone.png"))
                n += 1
                m.close()
            b.close()
    finally:
        srv.terminate()
    print(f"Знімків: {n} → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
