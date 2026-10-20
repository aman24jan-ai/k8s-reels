"""Mix voice + background music + sound effects into one track (all free, no downloads).

Music: put your own royalty-free tracks (e.g. from YouTube Audio Library) in assets/music/.
One is picked per day. If the folder is empty, a soft lo-fi beat is generated in code.
"""
import glob
import os
import subprocess

import numpy as np

SR = 48000
HERE = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(HERE, "..", "assets", "music")


def _decode(path: str) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1",
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def _env(n, attack, release):
    e = np.ones(n, dtype=np.float32)
    a, r = max(1, int(attack * SR)), max(1, int(release * SR))
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.exp(-np.linspace(0, 6, r))
    return e


def _note(freq, dur, vol=0.2, attack=0.01, release=None, wave="sine"):
    n = int(dur * SR)
    t = np.arange(n) / SR
    if wave == "sine":
        s = np.sin(2 * np.pi * freq * t)
    else:  # soft triangle-ish pluck
        s = (2 / np.pi) * np.arcsin(np.sin(2 * np.pi * freq * t))
    return (s * _env(n, attack, release or dur) * vol).astype(np.float32)


def _noise(dur, vol, seed=0):
    return (np.random.default_rng(seed).standard_normal(int(dur * SR)) * vol).astype(np.float32)


def _lowpass(x, alpha):
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):  # short signals only
        acc += alpha * (v - acc)
        y[i] = acc
    return y


def generated_beat(seconds: float, seed: int = 0) -> np.ndarray:
    """Gentle 96 BPM lo-fi bed: chord pads, pluck arpeggio, soft kick and hats."""
    n = int(seconds * SR)
    out = np.zeros(n + SR, dtype=np.float32)
    beat = 60 / 96
    rng = np.random.default_rng(seed)
    progs = [[(220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (196.0, 246.9, 293.7),
              (164.8, 207.7, 246.9)],
             [(261.6, 329.6, 392.0), (220.0, 261.6, 329.6), (174.6, 220.0, 261.6),
              (196.0, 246.9, 293.7)]]
    prog = progs[seed % len(progs)]
    bar = beat * 4
    kick = _note(55, 0.35, 0.55, 0.002, 0.3) * np.exp(-np.linspace(0, 4, int(0.35 * SR)))
    hat = _lowpass(_noise(0.05, 0.12, seed), 0.6)
    hat = (_noise(0.05, 0.10, seed) - hat) * _env(len(hat), 0.001, 0.05)
    t = 0.0
    i = 0
    while t < seconds:
        chord = prog[i % len(prog)]
        s = int(t * SR)
        for f in chord:  # pad
            p = _note(f, bar + 0.4, 0.045, 0.3, 0.6)
            out[s:s + len(p)] += p[:len(out) - s]
        for k in range(8):  # arpeggio 8ths
            f = chord[k % 3] * 2
            p = _note(f, beat * 0.9, 0.035 + rng.uniform(0, 0.01), 0.005, beat * 0.9, "tri")
            ss = s + int(k * beat / 2 * SR)
            out[ss:ss + len(p)] += p[:max(0, len(out) - ss)]
        for k in (0, 2):  # kick
            ss = s + int(k * beat * SR)
            out[ss:ss + len(kick)] += kick[:max(0, len(out) - ss)]
        for k in range(8):  # hats
            ss = s + int((k + 0.5) * beat / 2 * SR) if k % 2 else s + int(k * beat / 2 * SR)
            out[ss:ss + len(hat)] += hat[:max(0, len(out) - ss)] * (0.7 if k % 2 else 0.4)
        t += bar
        i += 1
    out = out[:n]
    return out / (np.abs(out).max() + 1e-6) * 0.5


def _music(seconds: float, day: int) -> np.ndarray:
    files = sorted(glob.glob(os.path.join(MUSIC_DIR, "*.mp3")) +
                   glob.glob(os.path.join(MUSIC_DIR, "*.wav")) +
                   glob.glob(os.path.join(MUSIC_DIR, "*.m4a")))
    n = int(seconds * SR)
    if files:
        m = _decode(files[day % len(files)])
        if len(m) < n:
            m = np.tile(m, n // max(len(m), 1) + 1)
        m = m[:n]
        return m / (np.abs(m).max() + 1e-6) * 0.5
    return generated_beat(seconds, day)


def sfx(kind: str) -> np.ndarray:
    if kind == "whoosh":
        d = 0.45
        x = _noise(d, 0.5, 7)
        sweep = np.linspace(0.02, 0.35, len(x)) ** 1.5
        y = np.empty_like(x)
        acc = 0.0
        for i, v in enumerate(x):
            acc += sweep[i] * (v - acc)
            y[i] = acc
        return y * np.sin(np.linspace(0, np.pi, len(y))) * 0.9
    if kind == "pop":
        d = 0.12
        t = np.arange(int(d * SR)) / SR
        f = 900 * np.exp(-t * 18) + 300
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30) * 0.45).astype(np.float32)
    if kind == "tick":
        return _lowpass(_noise(0.02, 0.25, 3), 0.5) * _env(int(0.02 * SR), 0.001, 0.02)
    if kind == "ding":
        return _note(1318.5, 0.6, 0.18, 0.003, 0.6) + _note(1975.5, 0.6, 0.08, 0.003, 0.5)
    if kind == "error":  # two short low buzzes
        out = np.zeros(int(0.42 * SR), dtype=np.float32)
        for k in (0, 1):
            n = int(0.14 * SR)
            t = np.arange(n) / SR
            b = np.sign(np.sin(2 * np.pi * 180 * t)) * 0.18 * _env(n, 0.005, 0.12)
            i = int(k * 0.2 * SR)
            out[i:i + n] += _lowpass(b.astype(np.float32), 0.25)
        return out
    if kind == "boom":
        d = 0.6
        t = np.arange(int(d * SR)) / SR
        f = 120 * np.exp(-t * 6) + 40
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5) * 0.8).astype(np.float32)
    raise ValueError(kind)


def mix(voice_path: str | None, events: list[tuple[float, str]], out_wav: str,
        seconds: float, day: int = 0, voice_delay: float = 0.35) -> str:
    n = int(seconds * SR)
    track = np.zeros(n, dtype=np.float32)

    voice = np.zeros(n, dtype=np.float32)
    if voice_path:
        v = _decode(voice_path)
        s = int(voice_delay * SR)
        voice[s:s + len(v)] = v[:max(0, n - s)]

    # music, ducked while the voice talks
    music = _music(seconds, day)
    music_vol = float(os.environ.get("MUSIC_VOLUME", "0.22"))
    win = int(0.25 * SR)
    loud = np.convolve(np.abs(voice), np.ones(win) / win, mode="same")
    duck = 1.0 - 0.55 * np.clip(loud / (loud.max() + 1e-6) * 3, 0, 1)
    fade = np.ones(n, dtype=np.float32)
    fade[:int(0.3 * SR)] = np.linspace(0, 1, int(0.3 * SR))
    fade[-int(0.8 * SR):] = np.linspace(1, 0, int(0.8 * SR))
    track += music[:n] * duck * fade * music_vol

    for t, kind in events:
        s = sfx(kind) * float(os.environ.get("SFX_VOLUME", "0.6"))
        i = int(t * SR)
        if 0 <= i < n:
            track[i:i + len(s)] += s[:n - i]

    track += voice
    peak = np.abs(track).max()
    if peak > 0.98:
        track *= 0.98 / peak
    stereo = np.repeat(track[:, None], 2, axis=1)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR),
                    "-ac", "2", "-i", "-", out_wav], input=stereo.astype(np.float32).tobytes(),
                   check=True)
    return out_wav
