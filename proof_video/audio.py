"""Original score + sound design for "Proof, not pages." (fully synthesized).

108 BPM, A minor -> C major resolution. Everything is generated here with
numpy/scipy, so the music is original and free of third-party rights.

Structure (k = beat index, k=0 at 7.0 s):
  0-7 s     tension: precise clock ticks, low drone, filtered arp, riser
  7 s       drop when PROOF PACK is pressed (kick, bass, open arp)
  12-24 s   full groove + piano hook
  24.8-27 s lift: snare build, rising filter, riser
  27 s      final hit on C(add9), then resolved piano/pad tail
"""
import sys

import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

from common import *  # noqa: F401,F403

SR = 48000
N = int(DUR * SR)
rng = np.random.default_rng(3)


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def buf():
    return np.zeros((N, 2))


def place(bus, sig, t, gain=1.0, pan=0.0):
    """Add mono/stereo signal into stereo bus at time t with constant-power pan."""
    i = int(round(t * SR))
    if i >= N:
        return
    if sig.ndim == 1:
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        sig = np.stack([sig * l * 1.414, sig * r * 1.414], 1)
    if i < 0:
        sig = sig[-i:]
        i = 0
    n = min(len(sig), N - i)
    bus[i:i + n] += sig[:n] * gain


def lp(x, fc, order=2):
    fc = min(max(fc, 20), SR / 2 * 0.95)
    return sosfilt(butter(order, fc, 'low', fs=SR, output='sos'), x, axis=0)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc, 'high', fs=SR, output='sos'), x, axis=0)


def bp(x, f1, f2, order=2):
    return sosfilt(butter(order, [f1, f2], 'band', fs=SR, output='sos'), x, axis=0)


def env_adsr(n, a, d, s, r, sustain_len):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    sl = max(int(sustain_len * SR) - a - d, 0)
    e = np.concatenate([np.linspace(0, 1, max(a, 1)), np.linspace(1, s, max(d, 1)),
                        np.full(sl, s), np.linspace(s, 0, max(r, 1))])
    if len(e) < n:
        e = np.concatenate([e, np.zeros(n - len(e))])
    return e[:n]


def saw(f, dur, detune=0.0, maxh=None):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    ff = f * (1 + detune)
    H_ = int(min(maxh or 60, (SR / 2.2) / ff))
    ph = rng.uniform(0, 2 * np.pi)
    for h in range(1, H_ + 1):
        out += np.sin(2 * np.pi * ff * h * t + ph * h) / h
    return out * 0.6


def sq(f, dur, maxh=40):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for h in range(1, min(maxh, int(SR / 2.2 / f)) + 1, 2):
        out += np.sin(2 * np.pi * f * h * t) / h
    return out * 0.7


# ---------------------------------------------------------------- instruments
def kick(strong=1.0):
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = 46 + 110 * np.exp(-t * 38)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * (7.5 / strong))
    click = hp(rng.normal(0, 1, n), 2500) * np.exp(-t * 300) * 0.25
    return np.tanh((body + click) * 1.6) * 0.9


def sub_boom():
    n = int(2.6 * SR)
    t = np.arange(n) / SR
    f = 38 + 70 * np.exp(-t * 14)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.tanh(np.sin(ph) * np.exp(-t * 1.6) * 1.4) * 0.9


def clap():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    noise = bp(rng.normal(0, 1, n), 900, 5200)
    e = np.zeros(n)
    for d in (0, 0.011, 0.022):
        e += (t >= d) * np.exp(-np.clip(t - d, 0, None) * 140) * 0.6
    e += np.exp(-t * 18) * 0.5
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.3
    return (noise * e + body) * 0.55


def snare_roll_hit(vel):
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    return bp(rng.normal(0, 1, n), 1200, 7000) * np.exp(-t * 40) * vel * 0.45


def hat(open_=False):
    n = int((0.28 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    x = hp(rng.normal(0, 1, n), 7500, 4)
    return x * np.exp(-t * (14 if open_ else 95)) * 0.35


def tick(accent=False):
    """Precise clock tick: short sine blip + band noise."""
    n = int(0.03 * SR)
    t = np.arange(n) / SR
    f = 3400 if accent else 2600
    s = np.sin(2 * np.pi * f * t) * np.exp(-t * 260)
    s += bp(rng.normal(0, 1, n), 3000, 9000) * np.exp(-t * 400) * 0.4
    return s * (0.5 if accent else 0.32)


def pluck(m, dur, cutoff=4000, bright=1.0):
    f = mtof(m)
    n = int(dur * SR)
    x = saw(f, dur, maxh=30) * 0.6 + sq(f * 2, dur, 12) * 0.15
    t = np.arange(n) / SR
    # filter envelope approximation: blend bright and dark versions
    hi = lp(x, cutoff * bright)
    lo = lp(x, 600)
    fe = np.exp(-t * 18)
    y = hi * fe + lo * (1 - fe)
    return y * np.exp(-t * 7.5) * env_adsr(n, 0.002, 0.01, 1, 0.02, dur)


def piano(m, dur=2.5, vel=1.0):
    f = mtof(m)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for h, a in enumerate([1, 0.45, 0.22, 0.12, 0.07, 0.04], 1):
        inh = 1 + 0.0004 * h * h
        y += a * np.sin(2 * np.pi * f * h * inh * t) * np.exp(-t * (1.6 + h * 0.9))
    y += hp(rng.normal(0, 1, n), 2000) * np.exp(-t * 200) * 0.05
    return y * vel * env_adsr(n, 0.003, 0.05, 1, 0.08, dur)


def pad_chord(ms, dur, cutoff=1400, a=0.4, r=0.6):
    n = int(dur * SR)
    out = np.zeros((n, 2))
    for i, m in enumerate(ms):
        f = mtof(m)
        for j, d in enumerate((-0.004, 0.0, 0.0045)):
            s = saw(f, dur, detune=d, maxh=24)
            pan = (-0.6, 0.0, 0.6)[j]
            out[:, 0] += s * np.cos((pan + 1) * np.pi / 4)
            out[:, 1] += s * np.sin((pan + 1) * np.pi / 4)
    out = lp(out, cutoff, 2)
    e = env_adsr(n, a, 0.2, 0.85, r, dur - r)
    return out * e[:, None] * 0.12


def bass_note(m, dur, cutoff=420):
    f = mtof(m)
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = saw(f, dur, maxh=40) * 0.7 + np.sin(2 * np.pi * f * t) * 0.6
    s = lp(s, cutoff, 2)
    return np.tanh(s * 1.4) * env_adsr(n, 0.004, 0.08, 0.7, 0.04, dur) * 0.55


def chime(ms, vel=1.0, dur=0.9):
    n = int(dur * SR)
    out = np.zeros(n)
    for i, m in enumerate(ms):
        f = mtof(m)
        d = int(i * 0.07 * SR)
        t = np.arange(n - d) / SR
        s = (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t * 9)) * np.exp(-t * 6)
        s *= np.minimum(1, t / 0.004)
        out[d:] += s
    return out * 0.22 * vel


def whoosh(dur, f0, f1, vel=1.0, shape='sin'):
    n = int(dur * SR)
    x = rng.normal(0, 1, n)
    # process in a few bands for a moving filter
    k = 12
    y = np.zeros(n)
    for j in range(k):
        a, b = j * n // k, (j + 1) * n // k
        fc = f0 * (f1 / f0) ** ((j + .5) / k)
        part = bp(x, max(fc * 0.6, 40), min(fc * 1.6, 20000))
        w = np.zeros(n)
        w[a:b] = 1
        y += part * lp(w, 30, 1)
    u = np.linspace(0, 1, n)
    if shape == 'rise':
        e = u ** 2.2 * np.minimum(1, (1 - u) / 0.03)
    else:
        e = np.sin(np.pi * u) ** 1.5
    return y * e * 0.35 * vel


def riser(dur, f0=300, f1=6000, vel=1.0):
    return whoosh(dur, f0, f1, 1.0, shape='rise') * 0.7 * vel


def ui_click(vel=1.0):
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * 1850 * t) * np.exp(-t * 160) + 0.6 * np.sin(2 * np.pi * 900 * t) * np.exp(-t * 120)
    s += hp(rng.normal(0, 1, n), 4000) * np.exp(-t * 500) * 0.3
    return s * 0.3 * vel


def scan_sound(dur=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 1300 + 1400 * t / dur
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * (0.6 + 0.4 * np.sin(2 * np.pi * 34 * t)) * np.sin(np.pi * t / dur)
    return s * 0.08


def reverb_ir(sec=2.2, damp=4000):
    n = int(sec * SR)
    t = np.arange(n) / SR
    ir = rng.normal(0, 1, (n, 2)) * np.exp(-t * 3.2)[:, None]
    ir = lp(ir, damp, 1)
    ir[: int(0.012 * SR)] = 0
    return ir / np.sqrt((ir ** 2).sum(0))


# -------------------------------------------------------------- arrangement
CHORDS = {  # (bass midi, pad voicing, arp tones)
    'Am': (45, [57, 60, 64, 71], [69, 72, 76, 79, 81, 76]),
    'F': (41, [53, 57, 60, 64], [65, 69, 72, 76, 77, 72]),
    'C': (48, [55, 60, 64, 74], [67, 72, 76, 79, 84, 79]),
    'G': (43, [55, 59, 62, 69], [67, 71, 74, 79, 81, 74]),
    'Dm': (50, [53, 57, 60, 62], [62, 65, 69, 72, 74, 69]),
}
PROG = ['Am', 'F', 'C', 'G', 'Am', 'F', 'C', 'G', 'Dm']   # bars from k=0 .. k=36
HOOK = {
    'Am': [(0, 76, .7), (0.75, 72, .5), (1.5, 74, .9), (3, 71, .5)],
    'F': [(0, 72, .7), (0.75, 69, .5), (1.5, 72, .9), (3, 74, .5)],
    'C': [(0, 76, .7), (0.75, 72, .5), (1.5, 79, .9), (3, 76, .5)],
    'G': [(0, 74, .7), (0.75, 71, .5), (1.5, 74, .9), (2.5, 79, .5), (3.25, 78 - 1, .4)],
    'Dm': [(0, 74, .6), (0.75, 72, .5), (1.5, 77, .9), (2.5, 79, 1.2)],
}


def build():
    drums, bass, music, verb_send, sfx = buf(), buf(), buf(), buf(), buf()
    kick_times = []

    # ===== INTRO 0-7 s : ticking pulse + tension
    k = -12
    while bt(k) < bt(0) - 1e-6:
        t = bt(k)
        if k == int(k):
            place(drums, tick(accent=True), t, 1.0, 0.15)
        else:
            place(drums, tick(), t, 0.9, -0.15)
        k += 0.5
    k = -6.0
    while bt(k) < bt(-0.25):
        if (k * 4) % 2 == 1:
            place(drums, tick(), bt(k), 0.45, 0.4)
        k += 0.25
    # muted heartbeat thumps from scene 2
    for kk in range(-6, 0):
        place(drums, lp(kick(0.8), 180), bt(kk), 0.55)
    # low drone A1 + fifth, swelling
    dd = bt(0) - 0.0
    n = int(dd * SR)
    tt = np.arange(n) / SR
    drone = (np.sin(2 * np.pi * mtof(33) * tt) * 0.5 + lp(saw(mtof(45), dd, maxh=20), 300) * 0.5
             + lp(saw(mtof(52), dd, maxh=20, detune=0.003), 400) * 0.25)
    drone *= np.minimum(1, tt / 2.0) * (0.5 + 0.5 * tt / dd)
    place(music, drone, 0, 0.35)
    # pad bed (Am add9), dark
    place(music, pad_chord([57, 60, 64, 71], bt(0) - 0.6, cutoff=700, a=2.5, r=0.6), 0.6, 0.6)
    # filtered arp creeping in on 16ths from k=-8
    arp = CHORDS['Am'][2]
    k = -8.0
    i = 0
    while bt(k) < bt(-0.25):
        prog = (k + 8) / 8
        place(music, pluck(arp[i % 6], 0.3, cutoff=500 + 2500 * prog ** 2), bt(k), 0.18 + 0.2 * prog, (-0.35, 0.35)[i % 2])
        place(verb_send, pluck(arp[i % 6], 0.3, cutoff=500 + 2500 * prog ** 2), bt(k), 0.05)
        k += 0.25
        i += 1
    # riser into the drop + tiny breath before it
    place(sfx, riser(bt(0) - bt(-4) - 0.12, 250, 7000), bt(-4), 0.9)

    # ===== GROOVE 7-27 s
    for kk in range(0, 36):
        t = bt(kk)
        if kk < 4 and kk % 2 == 1:
            continue
        if 35 <= kk:
            continue                        # breath before the final hit
        place(drums, kick(), t, 0.95)
        kick_times.append(t)
    for kk in range(4, 34):
        if kk % 2 == 1:
            place(drums, clap(), bt(kk), 0.75, 0.05)
            place(verb_send, clap(), bt(kk), 0.12)
    for kk in range(0, 35):
        place(drums, hat(), bt(kk + 0.5), 0.8, 0.3)
        if kk >= 8:
            place(drums, hat(), bt(kk + 0.25), 0.28, -0.3)
            place(drums, hat(), bt(kk + 0.75), 0.28, -0.3)
        if kk >= 12 and kk % 2 == 0 and kk < 32:
            place(drums, hat(True), bt(kk + 0.5), 0.35, 0.35)
    # snare build in the lift (k 32-35.5)
    k = 32.0
    while k < 35.5:
        step = 0.5 if k < 34 else 0.25
        vel = 0.4 + 0.6 * (k - 32) / 3.5
        place(drums, snare_roll_hit(vel), bt(k), 1.0, 0.0)
        place(verb_send, snare_roll_hit(vel), bt(k), 0.15)
        k += step

    for bar, name in enumerate(PROG):
        k0 = bar * 4
        b_m, pad, arp = CHORDS[name]
        lift = bar >= 7
        # bass: 8ths, octave pop on the 'and' of 2 and 4
        for e in range(8):
            kk = k0 + e * 0.5
            if kk >= 35.5:
                break
            m = b_m + (12 if e in (3, 7) else 0)
            place(bass, bass_note(m, B * 0.45, cutoff=380 + (260 if lift else 0) + 200 * (e % 2)), bt(kk), 1.0)
        # pad
        cut = 1300 if bar < 2 else 1800
        if lift:
            cut = 2600 if bar == 7 else 3400
        dur = 4 * B + 0.3 if bar < 8 else 3.5 * B
        place(music, pad_chord(pad, dur, cutoff=cut, a=0.08, r=0.3), bt(k0), 0.55)
        place(verb_send, pad_chord(pad, dur, cutoff=cut, a=0.08, r=0.3), bt(k0), 0.25)
        # arp 16ths
        for s16 in range(16):
            kk = k0 + s16 * 0.25
            if kk >= 35.5:
                break
            m = arp[s16 % 6] + (12 if (lift and s16 >= 8) or bar == 8 else 0)
            br = 1.2 if lift else 1.0
            nv = pluck(m, 0.28, cutoff=4200, bright=br)
            acc = 1.0 if s16 % 4 == 0 else 0.72
            place(music, nv, bt(kk), 0.30 * acc, (-0.3, 0.3)[s16 % 2])
            place(verb_send, nv, bt(kk), 0.06)
        # piano hook from bar 2 (k=8, ~11.4 s)
        if bar >= 2:
            for (off, m, d) in HOOK[name]:
                if k0 + off >= 35.5:
                    continue
                pv = piano(m, 1.8, 0.85)
                place(music, pv, bt(k0 + off), 0.30, 0.12)
                place(verb_send, pv, bt(k0 + off), 0.16)

    # ===== FINAL HIT at 27.0 + resolved ending
    t = FINAL_HIT
    place(drums, kick(1.6), t, 1.1)
    place(drums, sub_boom(), t, 0.85)
    crash = hp(rng.normal(0, 1, int(2.4 * SR)), 3500, 2) * np.exp(-np.arange(int(2.4 * SR)) / SR * 2.6) * 0.12
    place(drums, crash, t, 1.0, -0.1)
    place(drums, crash[::-1].copy() * 0.0, t, 0.0)
    final_pad = [48, 55, 60, 64, 67, 74]
    place(music, pad_chord(final_pad, 3.0, cutoff=3200, a=0.01, r=2.2), t, 0.75)
    place(verb_send, pad_chord(final_pad, 3.0, cutoff=3200, a=0.01, r=2.2), t, 0.5)
    place(bass, bass_note(36, 2.6, cutoff=300) * np.linspace(1, 0, int(2.6 * SR)), t, 1.0)
    for i, m in enumerate([48, 60, 64, 67, 74, 79]):
        pv = piano(m, 3.0, 0.9)
        place(music, pv, t + i * 0.012, 0.32)
        place(verb_send, pv, t + i * 0.012, 0.35)
    # gentle resolving arp after the hit
    for i, m in enumerate([84, 79, 76, 74, 72]):
        tt_ = bt(37 + i * 0.5)
        if tt_ < DUR - 0.6:
            nv = pluck(m, 0.4, cutoff=3000)
            place(music, nv, tt_, 0.16 * (1 - i * 0.12), (-0.4, 0.4)[i % 2])
            place(verb_send, nv, tt_, 0.18)
    pv = piano(72, 2.0, 0.6)
    place(music, pv, bt(38.5), 0.13)
    place(verb_send, pv, bt(38.5), 0.15)
    place(sfx, riser(bt(36) - bt(32) - 0.15, 400, 9000, 1.0), bt(32), 0.9)

    # ===== SOUND DESIGN (kept under the music)
    place(sfx, whoosh(0.55, 200, 3500, 1.2), S2 - 0.35, 0.8)                   # dive into screen
    xs = [700, 1310, 470, 1460, 1010, 280, 1680, 1080, 1660, 640]
    for i, tp in enumerate(WINDOW_POPS):
        pan = (xs[i] - 960) / 960 * 0.8
        place(sfx, whoosh(0.16, 2500, 900, 0.8), tp - 0.02, 0.55, pan)
        place(sfx, ui_click(0.6), tp, 0.45, pan)
    place(sfx, whoosh(0.32, 600, 8000, 1.4), SLASH - 0.05, 0.9)                 # line cuts the clutter
    place(sfx, whoosh(0.45, 6000, 400, 1.0), SLASH + 0.12, 0.55)                # windows collapse
    place(sfx, ui_click(1.3), CLICK - 0.005, 0.9)                              # PROOF PACK press
    place(sfx, chime([76, 83], 0.7), CLICK + 0.02, 0.5)
    place(sfx, whoosh(0.6, 300, 6000, 1.0), bt(5), 0.6)                        # button expands
    place(sfx, whoosh(0.4, 5000, 600, 0.8), S4, 0.45)
    place(sfx, ui_click(0.8), QNG_SELECT, 0.6, 0.3)
    for i, tc in enumerate(ROW_CHECKS):
        place(sfx, chime([72 + [0, 4, 7][i], 79 + [0, 0, 5][i]], 0.75), tc, 0.55, 0.35)
    place(sfx, chime([69, 64], 0.55, 1.1), AMBER_IN, 0.4, 0.35)                # calm, not an alarm
    for tp in AMBER_PULSES:
        place(sfx, lp(chime([57], 0.6, 1.0), 900), tp, 0.55)
    place(sfx, whoosh(0.7, 300, 4000, 1.0), S6 - 0.1, 0.55, 0.4)               # pan to auditor
    for i, tc in enumerate(AUDIT_CHECKS):
        place(sfx, chime([74 + [0, 3, 5][i], 81 + [0, 2, 5][i]], 0.7), tc, 0.5, -0.2)
    place(sfx, chime([72, 76, 79, 84], 1.2, 1.6), RING_DONE, 0.7)              # verification
    place(verb_send, chime([72, 76, 79, 84], 1.2, 1.6), RING_DONE, 0.4)
    place(sfx, whoosh(0.5, 500, 5000, 1.0), S7 - 0.3, 0.6)                     # match cut
    place(sfx, scan_sound(0.55), QR_SCAN - 0.5, 0.9, 0.4)                       # QR scan
    place(sfx, chime([84, 91], 0.8, 0.5), QR_SCAN, 0.45, 0.4)
    sw = whoosh(SWEEP_END - SWEEP_START + 0.2, 400, 3500, 1.2)
    n_ = len(sw)
    pan_l = np.cos(np.linspace(0, np.pi / 2, n_))
    pan_r = np.sin(np.linspace(0, np.pi / 2, n_))
    place(sfx, np.stack([sw * pan_l, sw * pan_r], 1) * 1.3, SWEEP_START - 0.1, 0.7)
    place(sfx, whoosh(0.5, 8000, 300, 1.2), FINAL_HIT - 0.5, 0.6)              # zoom-out into end card

    # ---------------------------------------------------------------- mix
    env = np.ones(N)
    for t in kick_times:                     # sidechain pump
        i = int(t * SR)
        d = int(0.32 * SR)
        e = 1 - 0.75 * np.exp(-np.arange(d) / SR * 14)
        env[i:i + d] = np.minimum(env[i:i + d], e[:min(d, N - i)])
    music *= env[:, None] ** 0.6
    bass *= env[:, None]
    # ping-pong delay on the music bus (dotted 8th)
    dly = int(0.75 * B * SR)
    echo = np.zeros_like(music)
    src = lp(hp(music, 400), 5000) * 0.28
    for r in range(1, 5):
        sh = dly * r
        if sh >= N:
            break
        part = src[:-sh] * (0.55 ** (r - 1))
        if r % 2:
            part = part[:, ::-1]
        echo[sh:] += part
    music += echo
    verb = fftconvolve(verb_send, reverb_ir(), axes=0)[:N] * 0.55
    sfx = hp(sfx, 120)
    mix = drums * 0.9 + bass * 0.95 + music * 0.85 + verb + sfx * 0.6
    mix = hp(mix, 28)
    # glue: soft knee saturation + peak normalisation
    mix = np.tanh(mix * 0.9) / np.tanh(0.9)
    mix *= 0.89 / np.max(np.abs(mix))
    # fade the very end tail
    fo = int(0.35 * SR)
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 2
    return mix


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'score.wav'
    from scipy.io import wavfile
    mix = build()
    wavfile.write(out, SR, (mix * 32767).astype(np.int16))
    print('wrote', out, mix.shape)
