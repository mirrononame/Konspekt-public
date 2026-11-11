# Конспект — інструкції для Claude Code (розробка)

Застосунок для лекцій студента: запис → розшифровка (Whisper локально) → конспект PDF, інструкції до лаб, проєкти.
Локальний сервер FastAPI на Windows, інтерфейс у браузері (ПК і телефон). Версія — `app/server.py` (`VERSION`), історія — `CHANGELOG.md`.

## Два різні CLAUDE.md
- **Цей файл** — для розробки програми.
- **`app/CLAUDE.md`** + `app/protocol/*.md` — протокол обробки лекцій для Claude (черга `data/queue.json`, формати `notes.md`,
  `result.json`, інструкції до лаб, «Робота в чаті»). Сервер при старті копіює їх у `data/`. Протокол змінюй лише в `app/`.

## Де що
| Шлях | Що там |
|---|---|
| `app/server.py` | маршрути API, фоновий сканер (кожні 3 с), `VERSION`, `BETA` |
| `app/lectures.py` | заняття, статуси, `write_queue()` → `data/queue.json` |
| `app/course.py` | пам'ять предмета, карта курсу, «Допоможи», чекліст, інструкція до лаби |
| `app/chat.py` | «Робота в чаті»: `CHAT.md`, `journal.md`, пакет `.zip` |
| `app/share.py` | «Обмін конспектами»: експорт і імпорт пакета для однокурсника |
| `app/project.py` | «Проєкт» предмета: етапи, кроки, версії файлів |
| `app/semester.py`, `push.py` | семестр, залік, календар ICS, Web Push |
| `app/eportal.py`, `usos.py` | ePortal (Moodle) і розклад з USOS (PWr) |
| `app/storage.py`, `applog.py` | атомарний запис JSON, `data/` і `secrets/`, журнал подій |
| `app/static/` | `app.js` та модулі; у `index.html` і `sw.js` після змін JS/CSS збільшуй `?v=N` (тест у `test_v23`) |
| `tools/` | `mkpdf.py` (Markdown → PDF), `noteslint.py`, `logreport.py` |
| `tests/` | pytest на синтетичних даних (`KONSPEKT_DATA`), `test_ui` — Playwright |

## Правила
- Тести: `python -m pytest -q tests`. Перед комітом — усі зелені.
- Дані користувача в `data/`, ключі в `secrets/`: не читати й не комітити.
- `meta.json`, `queue.json`, `settings.json`, `schedule.json` пише лише застосунок.
- Нові помилки — через `applog.error`, а не `print`.
- `.bat`-файли — з кінцями рядків CRLF.
- Без платних сервісів і API: застосунок працює з підпискою Claude через Cowork або Claude Code.
