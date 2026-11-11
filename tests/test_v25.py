"""2.5: якість конспектів — петлі Whisper, оцінка розшифровки, noteslint, таблиці в PDF, протокол частинами."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))


def test_whisper_loops_collapsed_and_quality():
    from app.transcriber import collapse_loops, quality
    segs = [{"text": t} for t in ["Dzień dobry.", "Chodzisz.", "Chodzisz.", "chodzisz", "Kontekst procesu to rejestry.", "Tak."]]
    out, dropped = collapse_loops(segs)
    assert [s["text"] for s in out] == ["Dzień dobry.", "Chodzisz.", "Kontekst procesu to rejestry.", "Tak."] and dropped == 2
    good = quality([{"text": "słowo " * 110}], 0, 1)
    assert good["level"] == "good"
    assert quality([{"text": "Tak."}] * 30, 280, 69)["level"] == "bad"  # як TS 28.10: петлі й майже без мови


def _good_w(points=9):
    body = "\n\n".join(f"## {i}. Temat {i}\n\n**Po ludzku:** opis.\n\n**Zapamiętaj:** krótko." for i in range(1, points + 1))
    return ("# Przedmiot — temat (wersja „na szybko”)\n\n**Przedmiot:** X · **Data:** 01.11.2026\n\n## Za 1 minutę\n\n"
            + "\n".join(f"- myśl {i}" for i in range(6)) + "\n\n" + body + ("\n\nTekst. " * 400)
            + "\n\n## Typowe pułapki\n\n" + "\n".join(f"- pułapka {i}" for i in range(4))
            + "\n\n## Sprawdź się\n\n" + "\n".join(f"{i}. pytanie *(odp.)*" for i in range(1, 8)))


def test_noteslint_good_and_bad():
    from noteslint import lint
    assert not [m for lvl, m in lint(_good_w()) if lvl == "ERR"]
    bad = "# A\n# B\n\n## Najważniejsze\n\n| a | b |\n|---|---|\n| x | y | z |\n\n<mark>x</mark> **open\n"
    errs = [m for lvl, m in lint(bad) if lvl == "ERR"]
    assert any("один" in e for e in errs) and any("Za 1 minut" in e for e in errs)
    assert any("таблиця розпадеться" in e for e in errs) and any("HTML" in e for e in errs) and any("**" in e for e in errs)
    ok_table = "| wzór | uwaga |\n|---|---|\n| \\|a\\| < 1 | `x || y` |\n"
    assert not [m for lvl, m in lint(_good_w() + "\n\n" + ok_table) if "таблиця" in m]
    assert any(lvl == "ERR" for lvl, _ in lint("# T\n\n**Przedmiot:** X\n\n## Cel w 1 zdaniu\n\nx", "L"))


def test_mkpdf_escaped_pipes_and_emoji(tmp_path):
    md = tmp_path / "n.md"
    md.write_text("# T\n\n| wzór | uwaga |\n|---|---|\n| gdy \\|a\\| < 1 | 🔧 przyda się |\n", encoding="utf-8")
    pdf = tmp_path / "n.pdf"
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "mkpdf.py"), str(md), str(pdf), "f", "t"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    from pypdf import PdfReader
    text = " ".join(p.extract_text() or "" for p in PdfReader(str(pdf)).pages)
    assert "|a|" in text and "\\|" not in text and "►" in text


def test_protocol_split_and_copied(client, data_dir):
    core = (ROOT / "app" / "CLAUDE.md").read_text(encoding="utf-8")
    assert len(core.encode("utf-8")) < 32000  # ядро коротке, решта — частинами
    for name in re.findall(r"`protocol/([A-Z]_\w+\.md)`", core):
        assert (ROOT / "app" / "protocol" / name).exists(), name
        assert (data_dir / "protocol" / name).exists(), name  # сервер копіює їх у data/ при старті
    for must in ("noteslint.py", "## K. Код для студента", "_jak_dziala.md", "quality.level"):
        assert must in core, must
    assert "Конспект пишеш ти сам" in core and "Карток (`quiz.json`) не роби" in core  # 2.8: карток немає
