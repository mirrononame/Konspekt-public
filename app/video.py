"""Відео лекції (запис онлайн-зустрічі Teams / Meet / Zoom тощо) → аудіо для розшифровки + ключові кадри.

1. Аудіодоріжка копіюється з відео без перекодування (секунди) → audio/<назва>.m4a|.ogg|.mp3.
   Якщо формат незвичний — перекодовується в AAC 64 кбіт/с моно.
2. Ключові кадри: беремо кадр приблизно кожні 2 с (спершу лише опорні кадри — це дуже швидко),
   зменшуємо до 320×180 і порівнюємо сіткою 32×18 клітинок. Новий слайд = змінилось ≥ 6 % «спокійних»
   клітинок і картинка вже «встояла» (не середина анімації/перегортання). Клітинки, що змінюються
   постійно (віконце з камерою, анімація), автоматично виключаються з порівняння.
   Повтори слайдів (повернулись назад) не дублюються. Кадри → images/kadr_ГГ-ХХ-СС.jpg.
Після обробки (якщо треба) автоматично запускається розшифровка.
"""
from __future__ import annotations

import hashlib
import queue
import threading
import time
from pathlib import Path

from . import applog, lectures, storage

MAX_FRAMES = 90
SAMPLE_SEC = 2.0
_q: "queue.Queue[tuple[str, str]]" = queue.Queue()
_worker = {"thread": None, "current": None}


def have_av() -> bool:
    try:
        import av  # noqa: F401
        import numpy  # noqa: F401
        return True
    except Exception:
        return False


def has_video_stream(path: Path) -> bool:
    """Справжнє відео (а не аудіо з обкладинкою альбому)."""
    import av
    try:
        with av.open(str(path)) as c:
            for st in c.streams.video:
                try:
                    if st.disposition & av.stream.Disposition.attached_pic:
                        continue
                except Exception:
                    pass
                if st.codec_context.name in ("mjpeg", "png", "bmp") and (st.frames or 0) <= 1:
                    continue
                return True
    except Exception:
        return False
    return False


# ---------------------------------------------------------------- queue
def enqueue(lid: str, name: str) -> None:
    def fn(m):
        m.setdefault("video", {})[name] = {"state": "queued", "progress": 0, "queued_at": storage.now_iso()}
    lectures.mutate(lid, fn)
    _q.put((lid, name))
    _ensure()


def _ensure() -> None:
    t = _worker["thread"]
    if t and t.is_alive():
        return
    t = threading.Thread(target=_loop, daemon=True, name="video")
    _worker["thread"] = t
    t.start()


def resume_pending() -> int:
    """Після перезапуску сервера доробляємо відео, які не встигли обробитись."""
    n = 0
    if not storage.LECTURES_DIR.exists():
        return 0
    for d in storage.LECTURES_DIR.iterdir():
        meta = storage.read_json(d / "meta.json")
        if not isinstance(meta, dict):
            continue
        for name, v in (meta.get("video") or {}).items():
            if v.get("state") in ("queued", "processing") and (d / "video" / name).exists():
                _q.put((d.name, name))
                n += 1
    if n:
        _ensure()
    return n


def busy(meta: dict) -> bool:
    return any(v.get("state") in ("queued", "processing") for v in (meta.get("video") or {}).values())


def _set(lid: str, name: str, **kw) -> None:
    def fn(m):
        m.setdefault("video", {}).setdefault(name, {}).update(kw)
    try:
        lectures.mutate(lid, fn)
    except KeyError:
        pass


def _loop() -> None:
    while True:
        lid, name = _q.get()
        _worker["current"] = lid
        try:
            process(lid, name)
        except Exception as e:  # noqa: BLE001
            applog.error("video", lid, name, repr(e))
            _set(lid, name, state="error", message=str(e)[:300])
        finally:
            _worker["current"] = None


# ---------------------------------------------------------------- processing
def process(lid: str, name: str) -> None:
    from .schedule import load_settings
    d = storage.LECTURES_DIR / lid
    src = d / "video" / name
    if not src.exists():
        _set(lid, name, state="error", message="Файл відео не знайдено")
        return
    if not have_av():
        _set(lid, name, state="error", message="Бракує бібліотеки для відео (av). Перезапустіть «Конспект» — вона встановиться сама.")
        return
    _set(lid, name, state="processing", progress=1, started_at=storage.now_iso(), step="аудіо")
    stem = Path(name).stem[:60]
    t0 = time.time()

    audio = extract_audio(src, d / "audio", stem)
    if audio:
        p, dur = audio
        h = _sha(p)

        def add_audio(m):
            if not any(f.get("sha256") == h for f in m["files"]):
                m["files"].append({"name": p.name, "kind": "audio", "size": p.stat().st_size, "sha256": h,
                                   "added_at": storage.now_iso(), "source": "video", "from_video": name,
                                   **({"duration": round(dur, 1)} if dur else {})})
        lectures.mutate(lid, add_audio)
    _set(lid, name, progress=10, step="кадри", audio=audio[0].name if audio else "")

    def prog(frac: float) -> None:
        _set(lid, name, progress=10 + int(frac * 88))

    frames = extract_frames(src, d / "images", progress=prog)

    def add_frames(m):
        have = {f["name"] for f in m["files"]}
        for fp, t in frames:
            if fp.name not in have:
                m["files"].append({"name": fp.name, "kind": "image", "size": fp.stat().st_size, "sha256": _sha(fp),
                                   "added_at": storage.now_iso(), "source": "video", "from_video": name, "t": round(t, 1)})
    lectures.mutate(lid, add_frames)
    msg = (f"Аудіо: {'так' if audio else 'немає звукової доріжки'} · ключових кадрів: {len(frames)}"
           f" · {int(time.time() - t0)} с")
    if not frames and STATS.get("samples") and STATS["black"] / STATS["samples"] > 0.95:
        msg = (f"Аудіо: {'так' if audio else 'немає'}. Картинка у відео повністю чорна — програма запису не захопила екран "
               "(в OBS: джерело «Захоплення вікна», метод «Windows 10 (1903+)», або запуск OBS на вбудованій відеокарті). "
               "Конспект буде за звуком.")
    _set(lid, name, state="done", progress=100, step="", frames=len(frames), finished_at=storage.now_iso(), message=msg)
    if audio and not load_settings().get("video_keep"):
        drop_video(lid, name)

    # розшифровка: якщо її просили під час обробки або ввімкнено автоматичну
    meta = lectures.read_meta(lid)
    want = meta.pop("transcribe_after_video", None)
    if want is not None:
        lectures.mutate(lid, lambda m: m.pop("transcribe_after_video", None))
    if audio and (want or (want is None and load_settings().get("auto_transcribe"))):
        from . import transcriber
        if transcriber.available() and meta.get("transcribe", {}).get("state") not in ("queued", "running"):
            transcriber.enqueue(lid)


def drop_video(lid: str, name: str) -> bool:
    """Видаляє сам відеофайл (аудіо й кадри вже витягнуто). Без кошика — інакше місце не звільниться."""
    p = storage.LECTURES_DIR / lid / "video" / name
    if not p.exists():
        return False
    size = p.stat().st_size
    try:
        p.unlink()
    except OSError as e:
        applog.error("drop_video", e)
        return False

    def fn(m):
        v = m.setdefault("video", {}).setdefault(name, {})
        v["deleted_at"] = storage.now_iso()
        v["freed"] = size
        v["message"] = (v.get("message") or "") + f" · відео видалено (звільнено {size // 1048576} МБ)"
    lectures.mutate(lid, fn)
    return True


def cleanup_processed() -> int:
    """Під час запуску: видаляє відео, які вже оброблено (якщо в налаштуваннях не просили зберігати)."""
    from .schedule import load_settings
    if load_settings().get("video_keep") or not storage.LECTURES_DIR.exists():
        return 0
    n = 0
    for d in storage.LECTURES_DIR.iterdir():
        meta = storage.read_json(d / "meta.json")
        if not isinstance(meta, dict):
            continue
        for name, v in (meta.get("video") or {}).items():
            has_audio = any(f.get("from_video") == name and f["kind"] == "audio" for f in meta.get("files", []))
            if v.get("state") == "done" and has_audio and drop_video(d.name, name):
                n += 1
    return n


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def extract_audio(src: Path, out_dir: Path, stem: str) -> tuple[Path, float] | None:
    """Копіює звукову доріжку без перекодування; якщо не вийшло — перекодовує в AAC."""
    import av
    out_dir.mkdir(parents=True, exist_ok=True)
    with av.open(str(src)) as c:
        a = next((s for s in c.streams if s.type == "audio"), None)
        if a is None:
            return None
        dur = float(c.duration / 1_000_000) if c.duration else 0.0
        codec = a.codec_context.name
    ext = {"aac": ".m4a", "mp3": ".mp3", "opus": ".ogg", "vorbis": ".ogg", "flac": ".flac", "alac": ".m4a"}.get(codec)
    if ext:
        target = storage.unique_path(out_dir, f"{stem}{ext}")
        try:
            _remux(src, target)
            if target.stat().st_size > 1024:
                return target, dur
        except Exception as e:  # noqa: BLE001
            applog.info("video", "remux failed, transcoding:", repr(e))
        target.unlink(missing_ok=True)
    target = storage.unique_path(out_dir, f"{stem}.m4a")
    _transcode(src, target)
    return target, dur


def _remux(src: Path, target: Path) -> None:
    import av
    tmp = target.with_name("." + target.name + ".part" + target.suffix)
    with av.open(str(src)) as c:
        a = next(s for s in c.streams if s.type == "audio")
        fmt = {".m4a": "ipod", ".mp3": "mp3", ".ogg": "ogg", ".flac": "flac"}[target.suffix]
        with av.open(str(tmp), "w", format=fmt) as out:
            if hasattr(out, "add_stream_from_template"):
                o = out.add_stream_from_template(a)
            else:
                o = out.add_stream(template=a)
            for pkt in c.demux(a):
                if pkt.dts is None:
                    continue
                pkt.stream = o
                out.mux(pkt)
    tmp.replace(target)


def _transcode(src: Path, target: Path) -> None:
    import av
    tmp = target.with_name("." + target.name + ".part.m4a")
    with av.open(str(src)) as c:
        a = next(s for s in c.streams if s.type == "audio")
        a.thread_type = "AUTO"
        with av.open(str(tmp), "w", format="ipod") as out:
            o = out.add_stream("aac", rate=48000)
            try:
                o.layout = "mono"
            except Exception:
                pass
            o.bit_rate = 64000
            rs = av.AudioResampler(format="fltp", layout="mono", rate=48000)
            for frame in c.decode(a):
                for rf in rs.resample(frame) or []:
                    for p in o.encode(rf):
                        out.mux(p)
            for rf in rs.resample(None) or []:
                for p in o.encode(rf):
                    out.mux(p)
            for p in o.encode(None):
                out.mux(p)
    tmp.replace(target)


# ---------------------------------------------------------------- key frames
def _samples(src: Path, keyframes_only: bool, progress=None):
    """Генерує (t, кадр) приблизно кожні SAMPLE_SEC секунд."""
    import av
    with av.open(str(src)) as c:
        vs = c.streams.video[0]
        vs.thread_type = "AUTO"
        if keyframes_only:
            vs.codec_context.skip_frame = "NONKEY"
        dur = float(c.duration / 1_000_000) if c.duration else 0.0
        last_t, last_p = -1e9, 0.0
        n = 0
        fps = float(vs.average_rate or vs.guessed_rate or 30)
        try:
            for frame in c.decode(vs):
                n += 1
                if frame.pts is not None:
                    t = float(frame.pts * vs.time_base)
                elif frame.time is not None:
                    t = float(frame.time)
                else:
                    t = n / fps  # приблизно (лише якщо в файлі немає міток часу)
                if t - last_t < SAMPLE_SEC * 0.9:
                    continue
                last_t = t
                if progress and dur and t - last_p > dur / 50:
                    last_p = t
                    progress(min(1.0, t / dur))
                yield t, frame
        except av.error.InvalidDataError:
            return  # обірваний кінець файлу (напр. OBS закрили під час запису)


def _grid(small) -> "object":
    """320×180 → сітка 32×18 клітинок (середня яскравість)."""
    import numpy as np
    return small.reshape(18, 10, 32, 10).mean(axis=(1, 3)).astype(np.float32)


def _save(frame, out_dir: Path, t: float) -> Path:
    hh, mm, ss = int(t // 3600), int(t % 3600 // 60), int(t % 60)
    p = storage.unique_path(out_dir, f"kadr_{hh:02d}-{mm:02d}-{ss:02d}.jpg")
    w = frame.width
    if w > 1600:
        frame = frame.reformat(width=1600, height=round(frame.height * 1600 / w / 2) * 2)
    frame.to_image().convert("RGB").save(p, "JPEG", quality=85, optimize=True)
    return p


STATS: dict = {}


def extract_frames(src: Path, out_dir: Path, progress=None) -> list[tuple[Path, float]]:
    import numpy as np
    out_dir.mkdir(parents=True, exist_ok=True)

    def run(keyframes_only: bool):
        kept: list[list] = []          # [t, cells, path] — кадр зберігаємо одразу (пам'ять не росте)
        last_cells = prev_cells = None
        dyn = None                     # як часто клітинка змінюється (камера, анімація) — їх ігноруємо
        times: list[float] = []
        black = 0

        def frac(a, b, thr, mask):
            m = np.abs(a - b) > thr
            return float(m[mask].mean()) if mask.any() else float(m.mean())

        for t, frame in _samples(src, keyframes_only, progress):
            times.append(t)
            small = frame.reformat(width=320, height=180, format="gray").to_ndarray()
            if small.std() < 4:          # чорний / порожній екран
                black += 1
                prev_cells = None
                continue
            cells = _grid(small)
            if prev_cells is not None:
                ch = (np.abs(cells - prev_cells) > 6).astype(np.float32)
                dyn = ch if dyn is None else dyn * 0.85 + ch * 0.15
            mask = (dyn < 0.35) if dyn is not None else np.ones_like(cells, dtype=bool)
            stable = prev_cells is not None and frac(cells, prev_cells, 6, mask) < 0.02
            prev_cells = cells
            if not stable:
                continue
            if last_cells is not None and frac(cells, last_cells, 6, mask) < 0.06:
                continue                 # той самий слайд
            last_cells = cells
            if any(frac(cells, k[1], 6, mask) < 0.03 for k in kept):
                continue                 # повернулись до вже збереженого слайда
            if kept and t - kept[-1][0] < 6:
                kept[-1][2].unlink(missing_ok=True)   # швидка зміна — беремо пізніший стан
                kept[-1] = [t, cells, _save(frame, out_dir, t)]
                continue
            kept.append([t, cells, _save(frame, out_dir, t)])
            if len(kept) > 400:
                break
        gaps = np.diff(times) if len(times) > 2 else np.array([0.0])
        STATS.update(samples=len(times), black=black)
        return kept, float(np.median(gaps))

    kept, gap = run(True)
    if STATS.get("samples") and STATS["black"] / STATS["samples"] > 0.95:
        return []                      # відео повністю чорне — повний прохід нічого не дасть
    if gap > 3.5 or not kept:
        # опорних кадрів замало (рідкі keyframes) — повний прохід, повільніше
        for k in kept:
            k[2].unlink(missing_ok=True)
        kept, _ = run(False)
    if len(kept) > MAX_FRAMES:
        # забагато змін (напр. камера на весь екран) — рівномірна вибірка
        idx = set(np.linspace(0, len(kept) - 1, MAX_FRAMES).round().astype(int).tolist())
        for i, k in enumerate(kept):
            if i not in idx:
                k[2].unlink(missing_ok=True)
        kept = [k for i, k in enumerate(kept) if i in idx]
    if progress:
        progress(1.0)
    return [(k[2], k[0]) for k in kept]
