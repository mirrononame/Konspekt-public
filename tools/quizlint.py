"""Перевірка quiz.json перед записом: python3 quizlint.py quiz.json
Показує картки, які застосунок сховає як організаційні (study.is_org), невалідні та дублікати."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("KONSPEKT_DATA", str(Path(os.environ.get("TMPDIR", "/tmp")) / "konspekt_lint"))
from app import study  # noqa: E402


def main(path: str) -> int:
    cards = (json.load(open(path, encoding="utf-8")) or {}).get("cards", [])
    bad, seen = 0, set()
    for i, c in enumerate(cards, 1):
        q = str(c.get("q") or "")[:90]
        if study.is_org(c):
            print(f"ORG   #{i}: {q}  → у todos/пам'ять/конспект, не в картку"); bad += 1
        n = study.normalize(c)
        if not n or n["type"] != c.get("type"):
            print(f"BAD   #{i}: {q}  → тип {c.get('type')} не пройшов перевірку"); bad += 1
        if q in seen:
            print(f"DUP   #{i}: {q}"); bad += 1
        seen.add(q)
    print(f"{len(cards)} карток, проблем: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "quiz.json"))
