"""Локальна безкоштовна розшифровка аудіо через faster-whisper (необов'язково).

Черга зберігається в meta.json кожної лекції (transcribe.state = queued/running),
тому після перезапуску сервера незавершені завдання автоматично продовжуються.
"""
from __future__ import annotations

import importlib
import os
import re
import queue
import subprocess
import sys
import threading
import time
import traceback

from . import applog, storage, lectures
from .schedule import load_settings

_q: "queue.Queue[str]" = queue.Queue()
_cancel: set[str] = set()
_current: dict = {"id": None}
_model = {"obj": None, "key": None}
_install = {"state": "idle", "log": ""}
_force_cpu = {"on": False}
_worker_started = False


# ---------------------------------------------------------------- NVIDIA libraries (cuBLAS / cuDNN)
_gpu_install = {"state": "idle", "log": ""}
_dll_dirs_done = {"ok": False}


def _nvidia_bin_dirs() -> list[str]:
    """Папки з DLL/SO бібліотек NVIDIA, встановлених через pip (nvidia-cublas-cu12, nvidia-cudnn-cu12)."""
    import site
    roots = set(site.getsitepackages() if hasattr(site, "getsitepackages") else [])
    try:
        roots.add(site.getusersitepackages())
    except Exception:
        pass
    roots.add(os.path.join(sys.prefix, "Lib", "site-packages"))
    out = []
    for r in roots:
        nv = os.path.join(r, "nvidia")
        if not os.path.isdir(nv):
            continue
        for pkg in os.listdir(nv):
            for sub in ("bin", "lib"):
                d = os.path.join(nv, pkg, sub)
                if os.path.isdir(d):
                    out.append(d)
    return out


def register_cuda_dlls() -> None:
    """Робить DLL cuBLAS/cuDNN видимими для CTranslate2 (без цього GPU на Windows не працює)."""
    if _dll_dirs_done["ok"]:
        return
    dirs = _nvidia_bin_dirs()
    for d in dirs:
        try:
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(d)
        except OSError:
            pass
    if dirs:
        os.environ["PATH"] = os.pathsep.join(dirs + [os.environ.get("PATH", "")])
    _dll_dirs_done["ok"] = True


def gpu_libs_installed() -> bool:
    found = {"cublas": False, "cudnn": False}
    for d in _nvidia_bin_dirs():
        for f in os.listdir(d):
            fl = f.lower()
            if fl.startswith(("cublas64_12", "libcublas.so.12")):
                found["cublas"] = True
            if fl.startswith(("cudnn_ops64_9", "cudnn64_9", "libcudnn_ops.so.9", "libcudnn.so.9")):
                found["cudnn"] = True
    return all(found.values())


_gpu_name_cache: dict = {}


def gpu_name() -> str | None:
    if "v" in _gpu_name_cache:
        return _gpu_name_cache["v"]
    _gpu_name_cache["v"] = _gpu_name_query()
    return _gpu_name_cache["v"]


def _gpu_name_query() -> str | None:
    try:
        p = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=5,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        line = (p.stdout or "").strip().splitlines()
        return line[0].strip() if line else None
    except Exception:
        return None


def install_gpu() -> None:
    if _gpu_install["state"] == "running":
        return

    def run():
        _gpu_install.update(state="running", log="Встановлення бібліотек NVIDIA cuBLAS і cuDNN (~1 ГБ, кілька хвилин)…\n")
        try:
            p = subprocess.Popen([sys.executable, "-m", "pip", "install", "--upgrade",
                                  "nvidia-cublas-cu12", "nvidia-cudnn-cu12>=9,<10"],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for line in p.stdout:
                _gpu_install["log"] = (_gpu_install["log"] + line)[-6000:]
            p.wait()
            ok = p.returncode == 0 and gpu_libs_installed()
            _gpu_install["state"] = "done" if ok else "error"
            _gpu_install["log"] += ("\nГотово ✔ Перезапустіть «Конспект», щоб увімкнути відеокарту." if ok
                                    else f"\nПомилка (код {p.returncode})")
        except Exception as e:
            _gpu_install.update(state="error", log=_gpu_install["log"] + f"\n{e}")

    threading.Thread(target=run, daemon=True).start()


def available() -> bool:
    try:
        importlib.invalidate_caches()
        importlib.import_module("faster_whisper")
        return True
    except Exception:
        return False


def cuda_available() -> bool:
    register_cuda_dlls()
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def status() -> dict:
    av = available()
    return {
        "available": av,
        "cuda": cuda_available() if av else False,
        "gpu_name": gpu_name(),
        "gpu_libs": gpu_libs_installed(),
        "gpu_install": _gpu_install,
        "current": _current.get("id"),
        "queue_size": _q.qsize(),
        "install": _install,
    }


# ---------------------------------------------------------------- install
def install() -> None:
    if _install["state"] == "running":
        return

    def run():
        _install.update(state="running", log="Встановлення faster-whisper…\n")
        try:
            p = subprocess.Popen([sys.executable, "-m", "pip", "install", "--upgrade", "faster-whisper"],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for line in p.stdout:
                _install["log"] = (_install["log"] + line)[-6000:]
            p.wait()
            ok = p.returncode == 0 and available()
            _install["state"] = "done" if ok else "error"
            _install["log"] += "\nГотово ✔" if ok else f"\nПомилка (код {p.returncode})"
        except Exception as e:
            _install.update(state="error", log=_install["log"] + f"\n{e}")

    threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------- queue
def enqueue(lid: str) -> dict:
    def fn(m):
        m["transcribe"] = {"state": "queued", "progress": 0, "message": "У черзі", "updated_at": storage.now_iso()}
    meta = lectures.mutate(lid, fn)
    _cancel.discard(lid)
    _q.put(lid)
    ensure_worker()
    return meta


def cancel(lid: str) -> dict:
    _cancel.add(lid)

    def fn(m):
        if m.get("transcribe", {}).get("state") in ("queued", "running"):
            m["transcribe"] = {"state": "cancelled", "message": "Скасовано", "updated_at": storage.now_iso()}
    return lectures.mutate(lid, fn)


def resume_pending() -> int:
    """Після перезапуску повертає в чергу незавершені розшифровки."""
    n = 0
    for d in storage.LECTURES_DIR.iterdir() if storage.LECTURES_DIR.exists() else []:
        meta = storage.read_json(d / "meta.json")
        if isinstance(meta, dict) and meta.get("transcribe", {}).get("state") in ("queued", "running"):
            try:
                enqueue(d.name)
                n += 1
            except KeyError:
                pass
    return n


def ensure_worker() -> None:
    global _worker_started
    if not _worker_started:
        _worker_started = True
        threading.Thread(target=_worker, daemon=True, name="whisper").start()


def _set(lid: str, **kw) -> None:
    def fn(m):
        t = m.get("transcribe") or {}
        t.update(kw)
        t["updated_at"] = storage.now_iso()
        m["transcribe"] = t
    try:
        lectures.mutate(lid, fn)
    except KeyError:
        pass


_fallback = {"level": 0}  # 0 — найкращий режим, 1 — GPU float32, 2 — процесор


class _GarbageOutput(Exception):
    """Модель повернула лише «...» / розділові знаки — ознака збою обчислень (часто fp16 на старих GPU)."""


def _cuda_compute_type() -> str:
    try:
        import ctranslate2
        types = set(ctranslate2.get_supported_compute_types("cuda"))
    except Exception:
        types = set()
    if _fallback["level"] >= 1:
        return "float32"
    for t in ("float16", "int8_float16", "int8_float32", "float32"):
        if t in types:
            return t
    return "float32"


def _load_model():
    register_cuda_dlls()
    from faster_whisper import WhisperModel
    s = load_settings()
    name = s.get("whisper_model") or "large-v3-turbo"
    dev = s.get("whisper_device") or "auto"
    if dev == "auto":
        dev = "cuda" if cuda_available() and not _force_cpu["on"] else "cpu"
    if dev == "cuda" and (_fallback["level"] >= 2 or _force_cpu["on"]):
        dev = "cpu"
    ctype = _cuda_compute_type() if dev == "cuda" else "int8"
    key = (name, dev, ctype)
    if _model["key"] == key and _model["obj"] is not None:
        return _model["obj"], dev
    _model["obj"] = None
    try:
        model = WhisperModel(name, device=dev, compute_type=ctype,
                             cpu_threads=max(1, (os.cpu_count() or 4)) if dev == "cpu" else 0)
    except Exception:
        if dev != "cuda":
            raise
        dev, ctype = "cpu", "int8"  # наприклад, немає cuDNN — працюємо на процесорі
        model = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=max(1, (os.cpu_count() or 4)))
    _model.update(obj=model, key=(name, dev, ctype))
    return model, f"{dev}/{ctype}"


def _decode_audio(path, sr: int = 16000):
    """Власне декодування аудіо в 16 кГц моно (сумісне з будь-якою версією PyAV).

    Вбудоване в faster-whisper декодування ламається на нових PyAV
    ("open() got an unexpected keyword argument 'metadata_errors'").
    """
    import av
    import numpy as np
    chunks = []
    with av.open(str(path), mode="r") as c:
        stream = next((st for st in c.streams if st.type == "audio"), None)
        if stream is None:
            raise ValueError("У файлі немає аудіодоріжки")
        res = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=sr)

        def push(frames):
            if frames is None:
                return
            for f in frames if isinstance(frames, list) else [frames]:
                chunks.append(f.to_ndarray().reshape(-1).copy())

        bad = 0
        try:
            for packet in c.demux(stream):
                try:
                    frames = packet.decode()
                except (av.error.InvalidDataError, av.error.ValueError if hasattr(av.error, "ValueError") else ValueError):
                    bad += 1  # пошкоджений шматок (напр. обірваний запис OBS) — пропускаємо, а не падаємо
                    if bad > 500:
                        raise
                    continue
                for frame in frames:
                    frame.pts = None
                    push(res.resample(frame))
        except av.error.InvalidDataError:
            if not chunks:
                raise  # файл зіпсований від початку
            # обірваний кінець файлу — беремо все, що вдалося прочитати
        push(res.resample(None))
    if not chunks:
        raise ValueError("Не вдалося прочитати аудіо (порожній або пошкоджений файл)")
    audio = np.concatenate(chunks)
    return audio.astype(np.float32) / 32768.0


class _Cancelled(Exception):
    pass


_HALLUCINATIONS = (
    "dziękuję za obejrzenie", "dzięki za obejrzenie", "napisy wykonane", "napisy stworzone", "subskrybuj",
    "thanks for watching", "thank you for watching", "subtitles by", "amara.org", "продолжение следует",
    "дякую за перегляд", "редактор субтитров",
)


def _is_hallucination(seg, text: str) -> bool:
    """Типові «вигадки» Whisper на тиші: стандартні фрази, повтори, дуже невпевнені сегменти."""
    low = text.lower()
    if not any(ch.isalnum() for ch in text):  # «...», «—», «!!!»
        return True
    if any(h in low for h in _HALLUCINATIONS):
        return True
    if getattr(seg, "no_speech_prob", 0) > 0.7 and getattr(seg, "avg_logprob", 0) < -1.0:
        return True
    if getattr(seg, "compression_ratio", 0) > 2.6:  # «бла бла бла бла…»
        return True
    return False


def _norm_seg(t: str) -> str:
    return re.sub(r"[^\w]+", " ", t.lower()).strip()


def collapse_loops(segs: list[dict]) -> tuple[list[dict], int]:
    """«Петля» Whisper: та сама фраза кілька разів поспіль → лишаємо одну. Повертає (сегменти, скільки викинуто)."""
    out, dropped = [], 0
    for s in segs:
        if out and _norm_seg(s["text"]) == _norm_seg(out[-1]["text"]):
            dropped += 1
            continue
        out.append(s)
    return out, dropped


def quality(segs: list[dict], dropped: int, minutes: float) -> dict:
    """Наскільки розшифровка придатна для конспекту: слів за хвилину (лекція ≈ 90–130) і частка «петель»."""
    words = sum(len(s["text"].split()) for s in segs)
    wpm = round(words / max(minutes, 1), 0)
    loops = round(dropped / max(len(segs) + dropped, 1), 2)
    level = "good" if wpm >= 80 and loops < 0.05 else "weak" if wpm >= 45 else "bad"
    return {"wpm": wpm, "loops": loops, "level": level}


def _fmt_ts(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def _worker() -> None:
    while True:
        lid = _q.get()
        if lid in _cancel:
            _cancel.discard(lid)
            continue
        try:
            meta = lectures.read_meta(lid)
        except KeyError:
            continue
        if meta.get("transcribe", {}).get("state") not in ("queued", "running"):
            continue
        _current["id"] = lid
        try:
            try:
                _fallback["level"] = 0
                while True:
                    try:
                        _transcribe(lid, meta)
                        break
                    except _GarbageOutput:
                        if _fallback["level"] >= 2:
                            _set(lid, state="error", message="Модель повертає лише «...» навіть на процесорі. "
                                 "Спробуйте іншу модель у Налаштуваннях (напр. large-v3-turbo) і розшифруйте знову.")
                            break
                        _fallback["level"] += 1
                        _model.update(obj=None, key=None)
                        _set(lid, state="running", progress=0,
                             message="Модель видала порожній результат (збій обчислень на відеокарті) — повторюю "
                                     + ("на відеокарті в точнішому режимі…" if _fallback["level"] == 1 else "на процесорі…"))
                        meta = lectures.read_meta(lid)
            except Exception as e:
                # відеокарта без cuDNN/cuBLAS часто падає лише під час розшифровки — пробуємо процесор
                if _model.get("key") and _model["key"][1] == "cuda" and any(w in str(e).lower() for w in ("cud", "cublas", "gpu")):
                    _force_cpu["on"] = True
                    _model.update(obj=None, key=None)
                    _transcribe(lid, lectures.read_meta(lid))
                else:
                    raise
        except Exception as e:
            traceback.print_exc()
            _set(lid, state="error", message=f"{type(e).__name__}: {e}"[:500])
            applog.error("transcribe", lid, f"{type(e).__name__}: {e}")
            applog.event("transcribe", ok=False, lecture=lid)
        finally:
            _current["id"] = None


def _transcribe(lid: str, meta: dict) -> None:
    if not available():
        _set(lid, state="error", message="faster-whisper не встановлено (Налаштування → Розшифровка)")
        return
    audios = [f for f in meta["files"] if f["kind"] == "audio"]
    if not audios:
        _set(lid, state="error", message="Немає аудіофайлів")
        return
    _set(lid, state="running", progress=0, message="Завантаження моделі (перший раз може тривати кілька хвилин)…")
    model, dev = _load_model()
    lang = meta.get("audio_language") or "pl"
    d = storage.LECTURES_DIR / lid
    lines, segs_out = [], []
    total = sum(f.get("duration") or 0 for f in audios) or None
    done_before = 0.0
    started = time.time()
    settings = load_settings()
    use_enh = settings.get("audio_enhance", True)
    diags = []
    loops_total = {"n": 0}
    for idx, f in enumerate(audios):
        path = d / "audio" / f["name"]
        _set(lid, state="running", message=f"Читання аудіо {idx + 1}/{len(audios)}…")
        audio = _decode_audio(path)
        dur = len(audio) / 16000
        if total is None:  # тривалість невідома (браузер не зміг прочитати) — оцінюємо
            total = dur * len(audios)
        if use_enh:
            from . import audio_enhance
            _set(lid, state="running", message=f"Покращення звуку {idx + 1}/{len(audios)} (шумозаглушення, гучність)…")
            audio, diag = audio_enhance.enhance(audio)
            diags.append({"file": f["name"], **diag})
        if len(audios) > 1:
            lines.append(f"\n### Файл {idx + 1}: {f['name']}\n")

        def run(vad: bool):
            # 2.5: пороги проти «петель» (Tak. Tak. Tak…) тепер і з VAD, а не лише без нього;
            # hallucination_silence_threshold пропускає вигадки на довгих паузах (потрібні word_timestamps)
            kw = dict(language=lang, beam_size=5, condition_on_previous_text=False, no_speech_threshold=0.6,
                      log_prob_threshold=-1.0, compression_ratio_threshold=2.4, word_timestamps=True,
                      hallucination_silence_threshold=2.0)
            if vad:
                kw.update(vad_filter=True, vad_parameters={"threshold": 0.3, "min_silence_duration_ms": 700,
                                                           "speech_pad_ms": 300})
            else:
                kw.update(vad_filter=False)
            return model.transcribe(audio, **kw)

        nonlocal_state = {"last": 0.0}

        garbage = {"n": 0}

        def consume(segments, mode: str) -> list:
            got = []
            for seg in segments:
                if lid in _cancel:
                    raise _Cancelled()
                text = seg.text.strip()
                if text and not any(ch.isalnum() for ch in text):
                    garbage["n"] += 1
                if text and not _is_hallucination(seg, text):
                    got.append({"file": f["name"], "start": round(seg.start, 2), "end": round(seg.end, 2), "text": text})
                now = time.time()
                if now - nonlocal_state["last"] > 2:
                    nonlocal_state["last"] = now
                    tot = total or dur or 1
                    prog = min(99, int((done_before + seg.end) / tot * 100))
                    el = now - started
                    eta = int(el / max(prog, 1) * (100 - prog)) if prog > 2 else None
                    _set(lid, state="running", progress=prog, device=dev,
                         message=f"Розшифровка{mode} {prog}%" + (f", ще ~{eta // 60 + 1} хв" if eta else ""))
            return got

        try:
            segments, info = run(vad=True)
            got = consume(segments, "")
            speech = sum(g["end"] - g["start"] for g in got)
            # VAD нічого (або майже нічого) не знайшов — пробуємо без нього
            if dur > 60 and speech < 0.05 * dur:
                _set(lid, state="running", progress=0, message="Мовлення майже не знайдено — пробую ще раз без фільтра тиші…")
                segments, info = run(vad=False)
                got2 = consume(segments, " (2-а спроба)")
                if sum(g["end"] - g["start"] for g in got2) > speech:
                    got = got2
        except _Cancelled:
            _cancel.discard(lid)
            return
        if not got and garbage["n"] >= 3:
            raise _GarbageOutput()
        got, dropped = collapse_loops(got)
        loops_total["n"] += dropped
        for g in got:
            lines.append(f"[{_fmt_ts(g['start'])}] {g['text']}")
        segs_out.extend(got)
        done_before += dur
    if diags:
        storage.write_json(d / "audio_diagnostics.json", diags)
    if not segs_out:
        lvl = ""
        if diags:
            b = diags[0]["before"]
            lvl = f" Рівень голосу в записі: {b.get('speech_db')} dBFS, фон: {b.get('noise_db')} dBFS."
            if (b.get("speech_db") or 0) < -55:
                lvl += " Запис майже беззвучний — можливо, мікрофон був закритий або вимкнений."
        _set(lid, state="error", progress=0, device=dev,
             message="У записі не знайдено мовлення навіть після покращення звуку." + lvl)
        return
    text = "\n".join(lines).strip() + "\n"
    storage.write_json(d / "transcript.segments.json", segs_out)
    tmp = d / ".transcript.txt.tmp"
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, d / "transcript.txt")
    q = quality(segs_out, loops_total["n"], done_before / 60)
    hint = {"good": "", "weak": " · запис слабкий: частина мови не розпізналась",
            "bad": " · запис поганий: викладача майже не чути — наступного разу поклади телефон ближче до нього"}[q["level"]]
    _set(lid, state="done", progress=100, source="local", device=dev, quality=q,
         message=f"Готово за {int((time.time() - started) / 60) + 1} хв{hint}", model=load_settings().get("whisper_model"))
    applog.event("transcribe", ok=True, lecture=lid, audio_s=int(done_before), elapsed_s=int(time.time() - started), quality=q["level"], wpm=q["wpm"],
                 device=dev, model=load_settings().get("whisper_model"), files=len(audios))
    lectures.write_queue()
