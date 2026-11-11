"""Надійне файлове сховище.

Усі дані зберігаються як звичайні файли в папці data/:
  data/settings.json        — налаштування
  data/schedule.json        — предмети та розклад
  data/lectures/<id>/       — одна папка на лекцію
      meta.json             — метадані (пише тільки застосунок)
      audio/ slides/ images/ — завантажені файли
      transcript.txt        — розшифровка (локальна або від Claude)
      output/               — результат Claude (notes.pdf, notes.md, result.json)
  data/trash/               — видалені лекції (можна відновити)
  data/backups/             — щоденні архіви метаданих

JSON записується атомарно (тимчасовий файл + fsync + os.replace), а попередня
версія зберігається як *.bak — тому вимкнення ПК чи падіння сервера під час
запису не пошкоджує дані.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
DATA_DIR = Path(os.environ.get("KONSPEKT_DATA", ROOT_DIR / "data")).resolve()
LECTURES_DIR = DATA_DIR / "lectures"
TRASH_DIR = DATA_DIR / "trash"
BACKUPS_DIR = DATA_DIR / "backups"
TMP_DIR = DATA_DIR / ".tmp"
# 2.7: токени й ключі — поза data, щоб Claude у Cowork (доступ до data) їх не бачив
SECRETS_DIR = Path(os.environ.get("KONSPEKT_SECRETS", DATA_DIR.parent / "secrets")).resolve()
SECRET_FILES = ("eportal.json", "push.json")  # usos.json лишається: посилання з нього виносить usos.load()

_lock = threading.RLock()


def ensure_dirs() -> None:
    for d in (DATA_DIR, LECTURES_DIR, TRASH_DIR, BACKUPS_DIR, TMP_DIR):
        d.mkdir(parents=True, exist_ok=True)


def migrate_secrets() -> list[str]:
    """Переносить секрети (і їхні .bak) з data/ у secrets/. Уже перенесене не чіпає."""
    moved = []
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    for name in SECRET_FILES:
        for n in (name, name + ".bak"):
            src, dst = DATA_DIR / n, SECRETS_DIR / n
            if src.exists() and not dst.exists():
                os.replace(src, dst)
                moved.append(n)
    return moved


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------- JSON I/O
def write_json(path: Path, data: Any) -> None:
    """Атомарний запис JSON з резервною копією попередньої версії."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    with _lock:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            try:
                shutil.copy2(path, path.with_name(path.name + ".bak"))
            except OSError:
                pass
        # На Windows os.replace іноді падає, якщо файл тримає антивірус — повторюємо
        for attempt in range(10):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.1 * (attempt + 1))


def read_json(path: Path, default: Any = None) -> Any:
    """Читає JSON; якщо файл пошкоджено — бере *.bak; інакше default."""
    path = Path(path)
    for candidate in (path, path.with_name(path.name + ".bak")):
        if not candidate.exists():
            continue
        try:
            with open(candidate, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        if candidate != path:  # основний файл пошкоджено — відновлюємо з копії
            try:
                with _lock:
                    shutil.copy2(candidate, path)
            except OSError:
                pass
        return data
    return default


def cleanup_tmp() -> None:
    """Прибирає недокачані файли після аварійного завершення."""
    if TMP_DIR.exists():
        for p in TMP_DIR.iterdir():
            try:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink()
            except OSError:
                pass
    for p in DATA_DIR.rglob(".*.tmp"):
        try:
            p.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------- backups
def make_backup(reason: str = "auto") -> Path | None:
    """Архів усіх JSON/тексту (без важких аудіо) — щоб нічого не втратити."""
    ensure_dirs()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    target = BACKUPS_DIR / f"backup_{stamp}_{reason}.zip"
    try:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            for p in DATA_DIR.rglob("*"):
                if not p.is_file():
                    continue
                rel = p.relative_to(DATA_DIR)
                if rel.parts[0] in ("backups", "trash", ".tmp"):
                    continue
                if p.suffix.lower() in (".json", ".txt", ".md") and p.stat().st_size < 20_000_000:
                    z.write(p, rel.as_posix())
    except OSError:
        return None
    # залишаємо 20 останніх
    backups = sorted(BACKUPS_DIR.glob("backup_*.zip"))
    for old in backups[:-20]:
        try:
            old.unlink()
        except OSError:
            pass
    return target


def backup_if_needed() -> None:
    backups = sorted(BACKUPS_DIR.glob("backup_*_auto.zip"))
    if backups:
        age = time.time() - backups[-1].stat().st_mtime
        if age < 24 * 3600:
            return
    make_backup("auto")


def list_backups() -> list[dict]:
    out = []
    for p in sorted(BACKUPS_DIR.glob("backup_*.zip"), reverse=True):
        st = p.stat()
        out.append({
            "name": p.name,
            "size": st.st_size,
            "created": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds"),
        })
    return out


def touch(path: Path) -> None:
    """Ставить файлу «зараз» як час зміни (щоб кошик рахував дні від видалення)."""
    try:
        os.utime(path, None)
    except OSError:
        pass


def disk_usage() -> dict:
    total, seen = 0, set()
    for p in DATA_DIR.rglob("*"):
        try:
            if p.is_file():
                st = p.stat()
                if st.st_ino and (st.st_dev, st.st_ino) in seen:
                    continue  # hard link на той самий файл
                seen.add((st.st_dev, st.st_ino))
                total += st.st_size
        except OSError:
            pass
    free = shutil.disk_usage(DATA_DIR).free
    return {"data_bytes": total, "free_bytes": free}


def safe_filename(name: str) -> str:
    name = os.path.basename(name or "file").strip().replace("\x00", "")
    bad = '<>:"/\\|?*'
    name = "".join("_" if c in bad or ord(c) < 32 else c for c in name)
    name = name.strip(". ") or "file"
    stem, dot, ext = name.rpartition(".")
    if dot and len(stem) > 120:
        name = stem[:120] + "." + ext[:12]
    elif len(name) > 130:
        name = name[:130]
    return name


def unique_path(folder: Path, name: str) -> Path:
    p = folder / name
    if not p.exists():
        return p
    stem, suffix = p.stem, p.suffix
    i = 2
    while (folder / f"{stem} ({i}){suffix}").exists():
        i += 1
    return folder / f"{stem} ({i}){suffix}"


def trash_dir_name(lecture_id: str) -> str:
    return f"{lecture_id}__{datetime.now().strftime('%Y%m%d%H%M%S')}"


__all__ = [n for n in dir() if not n.startswith("_")] + ["timedelta"]
