"""Компактне зберігання даних.

Що робиться (у фоні, раз на годину, або кнопкою «Стиснути зараз» у Налаштуваннях → Сховище):
1. Аудіо, яке вже розшифровано, перекодовується в AAC 48 кбіт/с моно (24 кГц) → .m4a.
   Для мовлення якість майже та сама, а місця в 3–6 разів менше (90 хв ≈ 32 МБ замість 80–250 МБ).
   Оригінал замінюється лише після перевірки, що нова тривалість збігається.
2. Великі фото (дошка, скріншоти) зменшуються до 2200 px за довшою стороною (JPEG 85 %): 3–4 МБ → 0,4–0,8 МБ.
   Ключові кадри з відео (kadr_*) не чіпаються — вони вже маленькі.
3. Однакові файли (слайди ePortalu, що лежать і в предметі, і в лекції) зберігаються один раз:
   друга копія стає жорстким посиланням (hard link) на той самий файл — займає 0 байт, виглядає як звичайний файл.
4. Кошик чиститься за налаштуванням «trash_days».
"""
from __future__ import annotations

import hashlib
import os
import shutil
import threading
import time
from collections import defaultdict
from pathlib import Path

from . import applog, lectures, storage
from .schedule import load_settings

AUDIO_KBPS = 48
AUDIO_RATE = 24000
AUDIO_MIN_KBPS = 80          # нижче — уже компактно, не чіпаємо
IMG_MAX_SIDE = 2200
IMG_MIN_BYTES = 1_200_000
MIN_AGE = 20 * 60            # файл не чіпаємо, поки він «свіжий» (може ще дописуватись/оброблятись)
LINK_MIN_BYTES = 200_000

_job = {"state": "idle", "message": "", "started": 0.0, "finished": 0.0, "saved": 0, "last": None}
_lock = threading.Lock()


# ---------------------------------------------------------------- helpers
def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def _old(p: Path) -> bool:
    try:
        return time.time() - p.stat().st_mtime > MIN_AGE
    except OSError:
        return False


def _probe_seconds(p: Path) -> float:
    import av
    try:
        with av.open(str(p)) as c:
            if c.duration:
                return c.duration / 1_000_000
            a = next((s for s in c.streams if s.type == "audio"), None)
            if a is not None and a.duration and a.time_base:
                return float(a.duration * a.time_base)
    except Exception:
        pass
    return 0.0


def _busy(meta: dict) -> bool:
    if meta.get("recording", {}).get("state") == "recording":
        return True
    if meta.get("transcribe", {}).get("state") in ("queued", "running"):
        return True
    return any(v.get("state") in ("queued", "processing") for v in (meta.get("video") or {}).values())


# ---------------------------------------------------------------- audio
def _encode_audio(src: Path, dst: Path) -> float:
    """Перекодовує в AAC моно; пошкоджені пакети пропускає. Повертає тривалість результату (с)."""
    import av
    samples = 0
    with av.open(str(src)) as c:
        a = next(s for s in c.streams if s.type == "audio")
        with av.open(str(dst), "w", format="ipod") as out:
            o = out.add_stream("aac", rate=AUDIO_RATE)
            try:
                o.layout = "mono"
            except Exception:
                pass
            o.bit_rate = AUDIO_KBPS * 1000
            rs = av.AudioResampler(format="fltp", layout="mono", rate=AUDIO_RATE)

            def push(frames):
                nonlocal samples
                for rf in frames or []:
                    samples += rf.samples
                    for p in o.encode(rf):
                        out.mux(p)

            for pkt in c.demux(a):
                try:
                    frames = pkt.decode()
                except Exception:  # noqa: BLE001 — битий пакет (обірваний запис) пропускаємо
                    continue
                for fr in frames:
                    fr.pts = None
                    push(rs.resample(fr))
            push(rs.resample(None))
            for p in o.encode(None):
                out.mux(p)
    return samples / AUDIO_RATE


def compact_audio(lid: str) -> int:
    d = storage.LECTURES_DIR / lid
    tr = d / "transcript.txt"
    if not tr.exists() or tr.stat().st_size == 0:
        return 0  # ще не розшифровано — оригінал може знадобитись
    meta = lectures.read_meta(lid)
    if _busy(meta):
        return 0
    saved = 0
    for f in [x for x in meta["files"] if x["kind"] == "audio"]:
        if f.get("compact"):
            continue
        src = d / "audio" / f["name"]
        if not src.exists() or not _old(src):
            continue
        size = src.stat().st_size
        dur = f.get("duration") or _probe_seconds(src)
        if not dur or dur < 5:
            continue
        if size * 8 / dur / 1000 < AUDIO_MIN_KBPS and src.suffix.lower() in (".m4a", ".ogg", ".opus", ".mp3", ".webm"):
            lectures.mutate(lid, lambda m, n=f["name"]: _flag(m, n, {"compact": "skip"}))
            continue
        storage.TMP_DIR.mkdir(parents=True, exist_ok=True)
        tmp = storage.TMP_DIR / f"cmp_{os.getpid()}_{int(time.time())}.m4a"
        try:
            got = _encode_audio(src, tmp)
            new_size = tmp.stat().st_size
            if got < dur * 0.97 - 2 or new_size > size * 0.8:
                # тривалість не збіглась (щось не так) або виграшу немає — лишаємо оригінал
                tmp.unlink(missing_ok=True)
                lectures.mutate(lid, lambda m, n=f["name"]: _flag(m, n, {"compact": "skip"}))
                continue
            target = (d / "audio" / (src.stem + ".m4a"))
            if target != src and target.exists():
                target = storage.unique_path(d / "audio", src.stem + ".m4a")
            if not _swap(lid, "audio", src, tmp, target, dict(size=new_size, sha256=_sha(tmp), duration=round(got, 1),
                                                              compact={"from": f["name"], "from_size": size, "at": storage.now_iso()})):
                continue
            saved += size - new_size
        except Exception as e:  # noqa: BLE001
            applog.error("compact audio", lid, f["name"], repr(e))
            tmp.unlink(missing_ok=True)
    return saved


def _swap(lid: str, kind: str, src: Path, tmp: Path, target: Path, upd: dict) -> bool:
    """Атомарно: новий файл на місце старого + запис у meta.json. Якщо старий зайнятий (відкритий у плеєрі) — відкат."""
    with storage._lock:
        meta_p = storage.LECTURES_DIR / lid / "meta.json"
        raw = storage.read_json(meta_p)
        entry = next((x for x in (raw or {}).get("files", []) if x.get("name") == src.name and x.get("kind") == kind), None)
        if entry is None:
            tmp.unlink(missing_ok=True)
            return False
        try:
            if target != src:
                os.replace(tmp, target)
                try:
                    src.unlink()
                except OSError:
                    target.unlink(missing_ok=True)
                    return False
            else:
                os.replace(tmp, target)
        except OSError as e:
            applog.error("compact swap", src.name, e)
            tmp.unlink(missing_ok=True)
            return False
        entry.update(name=target.name, **upd)
        lectures.write_meta(raw)
    return True


def _flag(m: dict, name: str, kv: dict) -> None:
    for x in m["files"]:
        if x["name"] == name:
            x.update(kv)


# ---------------------------------------------------------------- images
def _shrink_image(p: Path) -> Path | None:
    from PIL import Image, ImageOps
    with Image.open(p) as im:
        im = ImageOps.exif_transpose(im)
        w, h = im.size
        is_png = p.suffix.lower() == ".png"
        if im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info):
            a = im.convert("RGBA").getchannel("A")
            if a.getextrema()[0] < 250:
                return None  # справжня прозорість — не чіпаємо
        if max(w, h) > IMG_MAX_SIDE:
            k = IMG_MAX_SIDE / max(w, h)
            im = im.resize((round(w * k), round(h * k)), Image.LANCZOS)
        elif is_png and p.stat().st_size < 3_000_000:
            return None
        out = storage.TMP_DIR / f"img_{os.getpid()}_{int(time.time() * 1000)}.jpg"
        storage.TMP_DIR.mkdir(parents=True, exist_ok=True)
        im.convert("RGB").save(out, "JPEG", quality=85, optimize=True, progressive=True)
    return out


def compact_images(lid: str) -> int:
    d = storage.LECTURES_DIR / lid
    meta = lectures.read_meta(lid)
    saved = 0
    for f in [x for x in meta["files"] if x["kind"] == "image"]:
        if f.get("compact") or f["name"].startswith("kadr_"):
            continue
        src = d / "images" / f["name"]
        if src.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"):
            continue
        if not src.exists() or not _old(src) or src.stat().st_size < IMG_MIN_BYTES:
            continue
        size = src.stat().st_size
        try:
            tmp = _shrink_image(src)
        except Exception as e:  # noqa: BLE001
            applog.error("compact image", src.name, repr(e))
            tmp = None
        if tmp is None or tmp.stat().st_size > size * 0.8:
            if tmp:
                tmp.unlink(missing_ok=True)
            lectures.mutate(lid, lambda m, n=f["name"]: _flag(m, n, {"compact": "skip"}))
            continue
        target = src.with_suffix(".jpg")
        if target != src and target.exists():
            target = storage.unique_path(src.parent, src.stem + ".jpg")
        new_size = tmp.stat().st_size
        if not _swap(lid, "image", src, tmp, target, dict(size=new_size, sha256=_sha(tmp),
                                                         compact={"from": f["name"], "from_size": size, "at": storage.now_iso()})):
            continue
        saved += size - new_size
    return saved


# ---------------------------------------------------------------- однакові файли → hard link
def _dedupe_candidates() -> list[Path]:
    out = []
    subj = storage.DATA_DIR / "subjects"
    if subj.exists():
        out += [p for p in subj.glob("*/files/*") if p.is_file()]
    if storage.LECTURES_DIR.exists():
        for sub in ("slides", "other", "images"):
            out += [p for p in storage.LECTURES_DIR.glob(f"*/{sub}/*") if p.is_file()]
    return [p for p in out if p.stat().st_size >= LINK_MIN_BYTES]


def dedupe() -> int:
    by_size: dict[int, list[Path]] = defaultdict(list)
    for p in _dedupe_candidates():
        by_size[p.stat().st_size].append(p)
    saved = 0
    for size, group in by_size.items():
        if len(group) < 2:
            continue
        by_hash: dict[str, list[Path]] = defaultdict(list)
        for p in group:
            try:
                by_hash[_sha(p)].append(p)
            except OSError:
                pass
        for same in by_hash.values():
            if len(same) < 2:
                continue
            master = same[0]
            mst = master.stat()
            for p in same[1:]:
                st = p.stat()
                if (st.st_dev, st.st_ino) == (mst.st_dev, mst.st_ino):
                    continue  # уже одне й те саме
                tmp = p.with_name(f".{p.name}.lnk.tmp")
                try:
                    os.link(master, tmp)
                    os.replace(tmp, p)
                    saved += size
                except OSError as e:
                    tmp.unlink(missing_ok=True)
                    applog.error("dedupe", p.name, e)
                    return saved  # файлова система не вміє hard link — не мучимось
    return saved


def link_or_copy(src: Path, dst: Path) -> None:
    """Для прикріплення файлу, який уже є в даних: спершу hard link (0 байт), інакше звичайна копія."""
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


# ---------------------------------------------------------------- кошик
def _trashed_at(p: Path) -> float:
    """Коли лекцію видалено: з назви «<id>__РРРРММДДггххсс» (mtime папки — це час останньої зміни лекції)."""
    from datetime import datetime
    try:
        return datetime.strptime(p.name.rsplit("__", 1)[1], "%Y%m%d%H%M%S").timestamp()
    except (IndexError, ValueError):
        return p.stat().st_mtime


def purge_trash(days: int | None = None) -> int:
    """Видаляє з кошика все, що старше `days` днів (0 — усе). Повертає звільнені байти."""
    if days is None:
        days = int(load_settings().get("trash_days", 14))
    limit = time.time() - days * 86400
    freed = 0
    t = storage.TRASH_DIR
    if not t.exists():
        return 0

    def gone(p: Path) -> int:
        n = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size
        shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink()
        return n

    for p in list(t.iterdir()):
        try:
            if p.name == "_files":
                for f in list(p.rglob("*")):
                    if f.is_file() and (days == 0 or f.stat().st_mtime < limit):
                        freed += gone(f)
                for sub in sorted(p.rglob("*"), reverse=True):
                    if sub.is_dir() and not any(sub.iterdir()):
                        sub.rmdir()
            elif days == 0 or _trashed_at(p) < limit:
                freed += gone(p)
        except OSError:
            pass
    return freed


# ---------------------------------------------------------------- звіт і запуск
CATS = [("audio", "Аудіо"), ("video", "Відео"), ("images", "Фото й кадри"), ("slides", "Слайди й файли лекцій"),
        ("subjects", "Матеріали предметів"), ("notes", "Конспекти, розшифровки"), ("trash", "Кошик"),
        ("backups", "Резервні копії"), ("other", "Інше")]


def report() -> dict:
    seen, sizes = set(), defaultdict(int)
    root = storage.DATA_DIR
    for p in root.rglob("*"):
        try:
            if not p.is_file():
                continue
            st = p.stat()
        except OSError:
            continue
        key = (st.st_dev, st.st_ino)
        if st.st_ino and key in seen:
            continue  # hard link — рахуємо один раз
        seen.add(key)
        parts = p.relative_to(root).parts
        top = parts[0]
        if top == "trash":
            c = "trash"
        elif top == "backups":
            c = "backups"
        elif top == "subjects":
            c = "subjects"
        elif top == "lectures" and len(parts) > 2:
            c = {"audio": "audio", "video": "video", "images": "images", "slides": "slides", "other": "slides"}.get(parts[2], "notes")
        else:
            c = "other"
        sizes[c] += st.st_size
    total = sum(sizes.values())
    return {"total": total, "free": shutil.disk_usage(root).free,
            "cats": [{"key": k, "label": lbl, "bytes": sizes.get(k, 0)} for k, lbl in CATS],
            "job": dict(_job), "settings": {k: load_settings().get(k) for k in ("compact_audio", "compact_images", "trash_days")}}


def run(force: bool = False) -> int:
    """Повний прохід. force — ігнорувати «свіжість» файлів (кнопка в налаштуваннях)."""
    global MIN_AGE
    if not _lock.acquire(blocking=False):
        return 0
    old_age = MIN_AGE
    try:
        if force:
            MIN_AGE = 60
        s = load_settings()
        _job.update(state="running", started=time.time(), message="Шукаю, що можна стиснути…", saved=0)
        saved = 0
        ids = [d.name for d in storage.LECTURES_DIR.iterdir() if d.is_dir()] if storage.LECTURES_DIR.exists() else []
        for i, lid in enumerate(ids):
            try:
                if s.get("compact_images", True):
                    saved += compact_images(lid)
                if s.get("compact_audio", True):
                    _job["message"] = f"Лекція {i + 1}/{len(ids)}: стискаю аудіо…"
                    saved += compact_audio(lid)
            except KeyError:
                continue
            except Exception as e:  # noqa: BLE001
                applog.error("compact", lid, repr(e))
            _job["saved"] = saved
        _job["message"] = "Шукаю однакові файли…"
        saved += dedupe()
        saved += purge_trash()
        _job.update(state="idle", finished=time.time(), saved=saved, message="",
                    last={"at": storage.now_iso(), "saved": saved})
        storage.write_json(storage.DATA_DIR / ".compact.json", _job["last"])
        return saved
    except Exception as e:  # noqa: BLE001
        _job.update(state="idle", message=f"Помилка: {e}")
        applog.error("compact run", repr(e))
        return 0
    finally:
        MIN_AGE = old_age
        _lock.release()


def run_async(force: bool = False) -> bool:
    if _lock.locked():
        return False
    _job.update(state="running", message="Починаю…")
    threading.Thread(target=run, args=(force,), daemon=True, name="compact").start()
    return True


def load_last() -> None:
    last = storage.read_json(storage.DATA_DIR / ".compact.json")
    if isinstance(last, dict):
        _job["last"] = last
