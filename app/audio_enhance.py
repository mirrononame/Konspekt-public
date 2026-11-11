"""Покращення запису лекції перед розшифровкою (лише numpy, без додаткових бібліотек).

Типові проблеми записів з аудиторії: викладач далеко від телефона (тихо),
гул проектора/вентиляції, луна. Whisper-VAD тоді вирішує, що «мовлення немає».

Кроки:
1. Прибрати постійну складову та низькочастотний гул (< 80 Гц).
2. Спектральне шумозаглушення (spectral gating): профіль шуму оцінюється по
   найтихіших фрагментах запису, слабкі частотні складові нижче шуму пригнічуються.
3. Автоматичне вирівнювання гучності (AGC): тихі фрагменти підсилюються до
   ~-20 dBFS (до +30 дБ), паузи підсилюються мало, щоб не роздувати шум.
4. М'який лімітер від перевантаження.
"""
from __future__ import annotations

import numpy as np

SR = 16000
N_FFT = 512
HOP = 256


def db(x: float) -> float:
    return float(20 * np.log10(max(float(x), 1e-9)))


def analyze(audio: np.ndarray) -> dict:
    """Короткий діагноз: загальний рівень, рівень мовлення, частка тиші."""
    if len(audio) == 0:
        return {"rms_db": -120.0, "peak_db": -120.0, "speech_db": -120.0}
    win = SR // 2
    n = len(audio) // win
    if n == 0:
        r = np.sqrt(np.mean(audio ** 2))
        return {"rms_db": db(r), "peak_db": db(np.max(np.abs(audio))), "speech_db": db(r)}
    frames = audio[: n * win].reshape(n, win)
    rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
    return {
        "rms_db": round(db(np.sqrt(np.mean(audio ** 2))), 1),
        "peak_db": round(db(np.max(np.abs(audio))), 1),
        "speech_db": round(db(np.percentile(rms, 90)), 1),   # гучні 10% ≈ рівень голосу
        "noise_db": round(db(np.percentile(rms, 10)), 1),    # тихі 10% ≈ фон
    }


def _frames_idx(n_samples: int) -> int:
    return max(0, (n_samples - N_FFT) // HOP + 1)


def denoise(audio: np.ndarray, strength: float = 1.5, floor: float = 0.12, progress=None) -> np.ndarray:
    """Спектральне шумозаглушення з overlap-add (обробка блоками — мало пам'яті)."""
    n = len(audio)
    if n < N_FFT * 4:
        return audio
    pad = np.concatenate([np.zeros(N_FFT, np.float32), audio, np.zeros(N_FFT, np.float32)])
    nf = _frames_idx(len(pad))
    win = np.hanning(N_FFT).astype(np.float32)
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    hp = (freqs >= 80).astype(np.float32)  # відрізаємо гул < 80 Гц

    # --- профіль шуму: 15-й перцентиль амплітуд по ~4000 рівномірно розкиданих кадрах
    sample_idx = np.linspace(0, nf - 1, num=min(nf, 4000)).astype(np.int64)
    sframes = np.stack([pad[i * HOP: i * HOP + N_FFT] for i in sample_idx]) * win
    smag = np.abs(np.fft.rfft(sframes, axis=1))
    noise = np.percentile(smag, 15, axis=0).astype(np.float32) + 1e-9

    out = np.zeros(len(pad), np.float32)
    norm = np.zeros(len(pad), np.float32)
    wsq = win ** 2
    block = 4096
    prev_gain = None
    for b0 in range(0, nf, block):
        b1 = min(nf, b0 + block)
        idx = (np.arange(b0, b1)[:, None] * HOP + np.arange(N_FFT)[None, :])
        fr = pad[idx] * win
        spec = np.fft.rfft(fr, axis=1)
        mag = np.abs(spec) + 1e-9
        gain = np.clip((mag - strength * noise) / mag, floor, 1.0)
        # згладжування в часі — менше «музикального» шуму
        if prev_gain is not None:
            gain[0] = 0.5 * gain[0] + 0.5 * prev_gain
        gain[1:] = 0.5 * gain[1:] + 0.5 * gain[:-1]
        prev_gain = gain[-1].copy()
        gain *= hp
        rec = np.fft.irfft(spec * gain, n=N_FFT, axis=1).astype(np.float32) * win
        for k in range(b1 - b0):
            s = (b0 + k) * HOP
            out[s: s + N_FFT] += rec[k]
            norm[s: s + N_FFT] += wsq
        if progress:
            progress(b1 / nf)
    norm[norm < 1e-6] = 1.0
    return (out / norm)[N_FFT: N_FFT + n]


def agc(audio: np.ndarray, target_db: float = -20.0, max_gain_db: float = 30.0) -> np.ndarray:
    """Плавне вирівнювання гучності по вікнах 0,4 с."""
    win = int(0.4 * SR)
    n = len(audio) // win
    if n < 2:
        peak = np.max(np.abs(audio)) or 1.0
        return audio * min(0.9 / peak, 10 ** (max_gain_db / 20))
    frames = audio[: n * win].reshape(n, win)
    rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
    noise_rms = np.percentile(rms, 10)
    target = 10 ** (target_db / 20)
    gain = target / rms
    gain = np.minimum(gain, 10 ** (max_gain_db / 20))
    gain = np.maximum(gain, 10 ** (-12 / 20))
    # паузи (рівень близький до фону) підсилюємо обережно
    quiet = rms < noise_rms * 2.0
    gain[quiet] = np.minimum(gain[quiet], np.median(gain[~quiet]) if (~quiet).any() else gain[quiet])
    # згладжування коефіцієнтів (≈2 с)
    k = 5
    gain = np.convolve(np.pad(gain, (k // 2, k // 2), mode="edge"), np.ones(k) / k, mode="valid")
    centers = (np.arange(n) + 0.5) * win
    g = np.interp(np.arange(len(audio)), centers, gain).astype(np.float32)
    return audio * g


def limiter(audio: np.ndarray, ceiling: float = 0.95) -> np.ndarray:
    return (np.tanh(audio / ceiling) * ceiling).astype(np.float32)


def enhance(audio: np.ndarray, progress=None) -> tuple[np.ndarray, dict]:
    """Повертає (покращене аудіо, діагностика до/після)."""
    before = analyze(audio)
    x = audio.astype(np.float32) - float(np.mean(audio))
    x = denoise(x, progress=progress)
    x = agc(x)
    x = limiter(x)
    after = analyze(x)
    return x, {"before": before, "after": after}
