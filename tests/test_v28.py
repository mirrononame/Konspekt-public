"""2.8: карток після кожного заняття більше немає — Claude їх не пише, застосунок не нагадує."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_protocol_has_no_cards_step():
    core = (ROOT / "app" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Карток (`quiz.json`) не роби" in core
    assert "quizlint" not in core and "helper_W" not in core and "8 завдань" not in core
    assert (ROOT / "app" / "protocol" / "Q_quiz.md").exists()  # формат лишився для тесту перед колоквіумом


def test_no_card_reminders(client):
    from app import push, semester
    assert "cards" not in push.KINDS
    assert not any(t["kind"] == "cards" for t in semester.week_tasks([]))


def test_ui_has_no_cards_entry():
    js = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert "5 хвилин карток" not in js and '"#/study", ic' not in js and "Пройти ${L.cards_count}" not in js
