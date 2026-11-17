"""Shared timeline for picture and sound.

Tempo: 108 BPM. The grid is anchored so that the beat drop lands exactly on
7.0 s (Proof Pack activated) and the final hit lands exactly on 27.0 s
(36 beats = 9 bars later). Every cut, check mark and transition is placed on
this grid via bt(k).
"""

BPM = 108.0
B = 60.0 / BPM          # one beat = 0.5556 s
T0 = 7.0                # beat k=0 -> the drop
FPS = 30
DUR = 30.0
W, H = 1920, 1080


def bt(k):
    """Time (s) of beat k on the grid (k may be negative / fractional)."""
    return T0 + k * B


# Scene boundaries (all on the beat grid)
S1 = 0.0
S2 = bt(-6)    # 3.667  teal line dives into the screen
S3 = bt(0)     # 7.000  Proof Pack pressed -> beat drops
S4 = bt(6)     # 10.333 Proof Pack interface
S5 = bt(16)    # 15.889 open point
S6 = bt(22)    # 19.222 auditor tablet
S7 = bt(29)    # 23.111 match cut to QR code on the sack
S8 = bt(36)    # 27.000 end card + final hit

# Key events used by both the renderer and the sound design
WINDOW_POPS = [S2 + 0.12 + i * B / 2 for i in range(10)]     # scattered docs (8th notes)
SLASH = bt(-1)                                               # line cuts through clutter
CLICK = bt(0)                                                # Proof Pack pressed
QNG_SELECT = bt(8)
ROW_CHECKS = [bt(10), bt(11), bt(12)]                       # green checks in the table
AMBER_IN = bt(14)
AMBER_PULSES = [bt(17), bt(19), bt(21)]
AUDIT_CHECKS = [bt(24), bt(25), bt(26)]
RING_START, RING_DONE = bt(24), bt(27)                      # ring closes -> green check
QR_SCAN = bt(31)
SWEEP_START, SWEEP_END = bt(32), bt(34)
FINAL_HIT = bt(36)
