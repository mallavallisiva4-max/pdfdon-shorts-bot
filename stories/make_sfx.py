"""Builds the story sound effects from scratch (no downloads, no copyright): stories/sfx/*.mp3

    python stories/make_sfx.py
Only needed once; the mp3 files are kept in the repo.
"""
import pathlib
import subprocess
import wave

import numpy as np

SR = 44100
OUT = pathlib.Path(__file__).parent / "sfx"
rng = np.random.default_rng(7)


def t(sec):
    return np.arange(int(sec * SR)) / SR


def env(n, attack, release):
    e = np.ones(n)
    a, r = min(n // 2, int(attack * SR)), min(n // 2, int(release * SR))
    if a: e[:a] = np.linspace(0, 1, a)
    if r: e[-r:] *= np.linspace(1, 0, r)
    return e


def lowpass(x, cutoff):
    """One-pole low-pass; cutoff may be a number or an array (sweeping)."""
    c = np.broadcast_to(np.asarray(cutoff, float), x.shape)
    a = np.exp(-2 * np.pi * c / SR)
    y = np.empty_like(x)
    prev = 0.0
    for i in range(len(x)):
        prev = (1 - a[i]) * x[i] + a[i] * prev
        y[i] = prev
    return y


def save(name, x, peak=0.9):
    x = x / (np.max(np.abs(x)) + 1e-9) * peak
    OUT.mkdir(exist_ok=True)
    wav = OUT / f"{name}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "96k", str(OUT / f"{name}.mp3")], check=True)
    wav.unlink()
    print("made", name)


def place(buf, clip, at):
    i = int(at * SR)
    j = min(len(buf), i + len(clip))
    buf[i:j] += clip[: j - i]


# ---- night: several crickets + soft wind -------------------------------------------------
def crickets(sec=12.0):
    out = np.zeros(int(sec * SR))
    for freq, amp, period in [(4300, 1.0, 0.62), (4850, 0.7, 0.81), (5400, 0.45, 0.53), (3900, 0.35, 1.1)]:
        pulse_t = t(0.016)
        pulse = np.sin(2 * np.pi * freq * pulse_t) * np.hanning(len(pulse_t))
        at = rng.uniform(0, period)
        while at < sec - 0.2:
            for k in range(rng.integers(3, 5)):          # 3-4 pulses make one chirp
                place(out, pulse * amp * rng.uniform(.8, 1), at + k * 0.032)
            at += period * rng.uniform(.85, 1.15)
    wind = lowpass(rng.normal(0, 1, len(out)), 350) * 0.6
    wind *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t(sec))
    out = out * 0.5 + wind
    fade = int(0.3 * SR)                                   # seamless loop
    out[:fade] = out[:fade] * np.linspace(0, 1, fade) + out[-fade:] * np.linspace(1, 0, fade)
    return out[:-fade]


# ---- day: songbirds + breeze ---------------------------------------------------------------
def bird_note(f0, f1, dur, amp=1.0):
    tt = t(dur)
    f = np.linspace(f0, f1, len(tt)) + 120 * np.sin(2 * np.pi * 38 * tt)   # little warble
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = np.sin(ph) + 0.25 * np.sin(2 * ph)
    return tone * np.hanning(len(tt)) * amp


def birds(sec=12.0):
    out = np.zeros(int(sec * SR))
    at = 0.3
    while at < sec - 1:
        kind = rng.integers(0, 3)
        if kind == 0:   # trill
            for k in range(rng.integers(4, 8)):
                place(out, bird_note(3600, 4300, 0.05, .7), at + k * 0.07)
        elif kind == 1:  # descending whistle
            place(out, bird_note(3400, 2300, 0.28, 1.0), at)
            place(out, bird_note(3300, 2500, 0.22, .8), at + 0.38)
        else:            # chirp-chirp
            for k in range(2):
                place(out, bird_note(2600, 4800, 0.09, .9), at + k * 0.16)
        at += rng.uniform(0.7, 1.8)
    breeze = lowpass(rng.normal(0, 1, len(out)), 500) * 0.5
    out = out * 0.6 + breeze
    fade = int(0.3 * SR)
    out[:fade] = out[:fade] * np.linspace(0, 1, fade) + out[-fade:] * np.linspace(1, 0, fade)
    return out[:-fade]


# ---- owl hoot: hoo ... hoo-hoo ---------------------------------------------------------------
def hoot():
    def one(dur, f):
        tt = t(dur)
        freq = f * (1 + 0.04 * np.sin(2 * np.pi * 5 * tt)) * np.linspace(1.03, .96, len(tt))
        ph = 2 * np.pi * np.cumsum(freq) / SR
        tone = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.05 * rng.normal(0, 1, len(tt))
        return tone * env(len(tt), .06, .18)
    out = np.zeros(int(1.9 * SR))
    place(out, one(0.42, 390), 0.0)
    place(out, one(0.22, 410), 0.75)
    place(out, one(0.5, 380), 1.05)
    return lowpass(out, 1800)


# ---- UI-ish effects --------------------------------------------------------------------------
def pop():
    tt = t(0.09)
    f = 950 * np.exp(-tt * 28) + 260
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-tt * 40)


def ding():
    tt = t(1.4)
    base = 1320
    x = sum(a * np.sin(2 * np.pi * base * r * tt) * np.exp(-tt * d) for r, a, d in [(1, 1, 3), (2.76, .45, 5), (5.4, .2, 8), (2, .3, 4)])
    return x * env(len(tt), .002, .05)


def buzz():
    out = np.zeros(int(0.75 * SR))
    for k in range(2):
        tt = t(0.24)
        sq = np.sign(np.sin(2 * np.pi * 140 * tt)) * 0.6 + np.sin(2 * np.pi * 280 * tt) * 0.4
        place(out, lowpass(sq, 2500) * env(len(tt), .005, .03), k * 0.32)
    return out


def whoosh():
    n = int(0.55 * SR)
    sweep = np.concatenate([np.linspace(300, 4000, n // 2), np.linspace(4000, 600, n - n // 2)])
    x = lowpass(rng.normal(0, 1, n), sweep)
    return x * np.hanning(n)


def tada():
    out = np.zeros(int(2.0 * SR))
    notes = [523.25, 659.25, 783.99, 1046.5]
    def brass(f, dur):
        tt = t(dur)
        saw = sum(np.sin(2 * np.pi * f * h * tt) / h for h in range(1, 8))
        return lowpass(saw, 3000) * env(len(tt), .02, .25) * (1 + .03 * np.sin(2 * np.pi * 6 * tt))
    for i, f in enumerate(notes[:3]):
        place(out, brass(f, 0.14), i * 0.11)
    for f in notes:
        place(out, brass(f, 1.5) * 0.6, 0.36)
    return out


def sparkle():
    out = np.zeros(int(1.6 * SR))
    for k in range(26):
        tt = t(0.25)
        f = rng.uniform(2500, 6000)
        place(out, np.sin(2 * np.pi * f * tt) * np.exp(-tt * 18) * rng.uniform(.3, 1), rng.uniform(0, 1.3))
    return out


def snore():
    sec = 5.0
    n = int(sec * SR)
    x = lowpass(rng.normal(0, 1, n), 260)
    tt = t(sec)
    breath = np.clip(np.sin(2 * np.pi * tt / 2.5), 0, None) ** 1.5
    rumble = 1 + 0.6 * np.sin(2 * np.pi * 32 * tt)
    return x * breath * rumble


# ---- soft music-box lullaby (original melody) -----------------------------------------------
def lullaby():
    beat = 0.42
    # scale degrees in C major, 0 = rest
    tune = [5, 3, 5, 8, 6, 5, 3, 0, 4, 2, 4, 6, 5, 3, 1, 0,
            5, 3, 5, 8, 9, 8, 6, 0, 5, 6, 5, 3, 2, 3, 1, 0]
    scale = {1: 523.25, 2: 587.33, 3: 659.25, 4: 698.46, 5: 783.99, 6: 880.0, 8: 1046.5, 9: 1174.66}
    bass = [261.63, 196.0, 220.0, 174.61]
    out = np.zeros(int(len(tune) * beat * SR) + SR)
    def box(f, dur, amp):
        tt = t(dur)
        return (np.sin(2 * np.pi * f * tt) + .3 * np.sin(2 * np.pi * 2 * f * tt) + .1 * np.sin(2 * np.pi * 3 * f * tt)) * np.exp(-tt * 3.2) * amp
    for i, d in enumerate(tune):
        if d: place(out, box(scale[d], 1.2, 1.0), i * beat)
        if i % 4 == 0: place(out, box(bass[(i // 4) % 4], 1.6, .45), i * beat)
    loop = int(len(tune) * beat * SR)
    out[: SR] += out[loop: loop + SR]                       # let the tail ring into the loop start
    return out[:loop]


if __name__ == "__main__":
    save("crickets", crickets(), .8)
    save("birds", birds(), .8)
    save("hoot", hoot())
    save("pop", pop(), .8)
    save("ding", ding(), .8)
    save("buzz", buzz(), .7)
    save("whoosh", whoosh(), .7)
    save("tada", tada(), .85)
    save("sparkle", sparkle(), .6)
    save("snore", snore(), .7)
    save("lullaby", lullaby(), .8)
