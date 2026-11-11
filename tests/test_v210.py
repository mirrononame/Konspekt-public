"""2.10: мова інтерфейсу — словники en/ru, налаштування, мова відповіді Claude у чаті."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "app" / "static" / "i18n"


def test_dictionaries_are_consistent():
    for lang in ("en", "ru"):
        d = json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))
        assert len(d) > 1000, lang
        for k, v in d.items():
            assert sorted(re.findall(r"\{\d+\}", k)) == sorted(re.findall(r"\{\d+\}", v)), (lang, k, v)
        assert d["Налаштування"] in ("Settings", "Настройки")
    en = json.loads((I18N / "en.json").read_text(encoding="utf-8"))
    assert not [v for v in en.values() if re.search(r"[іїєґ]", v)], "в англійському словнику лишилась українська"


def test_ui_language_setting(client):
    assert client.get("/api/state").json()["settings"]["ui_language"] == "uk"
    assert client.put("/api/settings", json={"ui_language": "en"}).json()["ui_language"] == "en"
    assert client.put("/api/settings", json={"ui_language": "de"}).json()["ui_language"] == "uk"  # невідома мова → українська


def test_chat_reply_language_follows_ui(client, data_dir):
    from app import chat
    client.put("/api/settings", json={"ui_language": "en"})
    assert "англійською" in chat._reply_lang()
    client.put("/api/settings", json={"ui_language": "uk"})
    assert chat._reply_lang() == "українською"


def test_scripts_registered():
    idx = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "app" / "static" / "i18n.js").read_text(encoding="utf-8")
    assert idx.index("i18n.js") < idx.index("app.js")
    assert "#9ca3af" in js  # російська — сірий прямокутник, без прапора
