"""UZIN UTZ - "Proof, not pages." concept film renderer (picture).

Pure vector motion design rendered with Skia (anti-aliased paths, perspective
homographies, blur/glow). Every frame is a pure function of time t.

Usage:
    python render.py stills 1.5 5.0 ...   -> review PNGs in ./stills
    python render.py video out.mp4        -> silent H.264 picture track
    python render.py endcard out.png
"""
import math
import os
import random
import subprocess
import sys

import numpy as np
import qrcode
import skia

from common import *  # noqa: F401,F403

HERE = os.path.dirname(os.path.abspath(__file__))
FD = '/usr/share/fonts/opentype/inter/'

# --------------------------------------------------------------------------
# basics
# --------------------------------------------------------------------------
_TF = {}


def font(name, size):
    if name not in _TF:
        _TF[name] = skia.Typeface.MakeFromFile(FD + name + '.otf')
    f = skia.Font(_TF[name], size)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    f.setHinting(skia.FontHinting.kNone)
    return f


TEAL = '#0096AA'
TEAL_HI = '#8AF0FA'
CHAR = '#394147'
WHITE = '#FFFFFF'
PALE = '#E5F5F7'
GREEN = '#43A879'
AMBER = '#E7A642'
GREY = '#7D888E'
LINE = '#E3EAED'


def rgb(h):
    if isinstance(h, tuple):
        return h
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def C(h, a=1.0):
    r, g, b = rgb(h)
    return skia.Color(r, g, b, int(round(255 * max(0.0, min(1.0, a)))))


def mixc(h1, h2, x):
    a, b = rgb(h1), rgb(h2)
    return tuple(int(round(a[i] + (b[i] - a[i]) * x)) for i in range(3))


def P(col, stroke=None, blur=0.0, shader=None, blend=None):
    p = skia.Paint(AntiAlias=True, Color=col)
    if stroke is not None:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
        p.setStrokeCap(skia.Paint.kRound_Cap)
        p.setStrokeJoin(skia.Paint.kRound_Join)
    if blur > 0.05:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if shader is not None:
        p.setShader(shader)
    if blend is not None:
        p.setBlendMode(blend)
    return p


def R(x, y, w, h):
    return skia.Rect.MakeXYWH(x, y, w, h)


def RR(x, y, w, h, r):
    return skia.RRect.MakeRectXY(R(x, y, w, h), r, r)


def lin(x0, y0, x1, y1, cols, pos=None):
    return skia.GradientShader.MakeLinear([skia.Point(x0, y0), skia.Point(x1, y1)], cols, pos)


def radg(x, y, r, cols, pos=None):
    return skia.GradientShader.MakeRadial(skia.Point(x, y), max(r, 0.1), cols, pos)


def poly(pts, close=True):
    p = skia.Path()
    p.addPoly([skia.Point(float(a), float(b)) for a, b in pts], close)
    return p


# easing ---------------------------------------------------------------------
def cl(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def pr(t, a, b):
    if b <= a:
        return 1.0 if t >= a else 0.0
    return cl((t - a) / (b - a))


def eoc(x):
    return 1 - (1 - x) ** 3


def eic(x):
    return x ** 3


def eio(x):
    return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2


def eoe(x):
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def eie(x):
    return 0.0 if x <= 0 else 2 ** (10 * x - 10)


def eob(x, s=1.7):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, x):
    return a + (b - a) * x


def lerp2(p, q, x):
    return (lerp(p[0], q[0], x), lerp(p[1], q[1], x))


# text -------------------------------------------------------------------------
def tw(s, f, track=0.0):
    if track == 0:
        return f.measureText(s)
    return sum(f.measureText(ch) for ch in s) + track * max(0, len(s) - 1)


def text(c, s, x, y, f, col=None, align='l', track=0.0, paint=None):
    w = tw(s, f, track)
    if align == 'c':
        x -= w / 2
    elif align == 'r':
        x -= w
    p = paint if paint is not None else P(col)
    if track == 0:
        c.drawString(s, x, y, f, p)
    else:
        for ch in s:
            c.drawString(ch, x, y, f, p)
            x += f.measureText(ch) + track
    return w


def reveal(c, s, x, y, f, col, t, t0, t_out=None, align='l', dur=0.5,
           stagger=0.07, cols=None, alpha=1.0, track=0.0):
    """Kinetic headline: words rise out of a mask, sharpen and settle."""
    if t < t0:
        return
    words = s.split(' ')
    sp = f.measureText(' ')
    widths = [tw(w_, f, track) for w_ in words]
    total = sum(widths) + sp * (len(words) - 1)
    if align == 'c':
        x -= total / 2
    elif align == 'r':
        x -= total
    size = f.getSize()
    out = eio(pr(t, t_out, t_out + 0.32)) if t_out is not None else 0.0
    if out >= 1:
        return
    c.save()
    c.clipRect(R(x - 40, y - size * 1.12 - out * size * 0.5, total + 80, size * 1.48))
    for i, (wd, ww) in enumerate(zip(words, widths)):
        p = eoe(pr(t, t0 + i * stagger, t0 + i * stagger + dur))
        dy = (1 - p) * size * 0.62 - out * size * 0.55
        a = p * (1 - out) * alpha
        col_i = cols[i] if cols else col
        text(c, wd, x, y + dy, f, track=track,
             paint=P(C(col_i, a), blur=(1 - p) * 5 + out * 4))
        x += ww + sp
    c.restore()


# geometry helpers ---------------------------------------------------------------
FOV = 1700.0


def proj_quad(w, h, cx, cy, rx=0.0, ry=0.0, rz=0.0, z=0.0, s=1.0):
    """Corners of a w*h card centred at (cx,cy), rotated in 3D, projected."""
    a, b, g = math.radians(rx), math.radians(ry), math.radians(rz)
    out = []
    for (x, y) in [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]:
        x *= s
        y *= s
        x, y = x * math.cos(g) - y * math.sin(g), x * math.sin(g) + y * math.cos(g)
        X = x * math.cos(b)
        Z = x * math.sin(b)
        Y = y * math.cos(a) - Z * math.sin(a)
        Z = y * math.sin(a) + Z * math.cos(a)
        Z += z
        k = FOV / (FOV + Z)
        out.append(((cx - 960 + X) * k + 960, (cy - 540 + Y) * k + 540))
    return out


def quad_matrix(w, h, quad):
    m = skia.Matrix()
    m.setPolyToPoly([skia.Point(0, 0), skia.Point(w, 0), skia.Point(w, h), skia.Point(0, h)],
                    [skia.Point(*q) for q in quad])
    return m


def card_matrix(w, h, cx, cy, **kw):
    return quad_matrix(w, h, proj_quad(w, h, cx, cy, **kw))


def mp(m, x, y):
    p = m.mapXY(x, y)
    return (p.x(), p.y())


def catmull(pts, n=10):
    if len(pts) < 3:
        return list(pts)
    out = []
    P_ = [pts[0]] + list(pts) + [pts[-1]]
    for i in range(1, len(P_) - 2):
        p0, p1, p2, p3 = P_[i - 1], P_[i], P_[i + 1], P_[i + 2]
        for j in range(n):
            u = j / n
            u2, u3 = u * u, u * u * u
            out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * u +
                                    (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * u2 +
                                    (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * u3) for k in range(2)))
    out.append(pts[-1])
    return out


class Polyline:
    def __init__(self, pts):
        self.pts = [tuple(map(float, p)) for p in pts]
        self.cum = [0.0]
        for a, b in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        self.L = self.cum[-1]

    def at(self, d):
        d = cl(d, 0, self.L)
        i = int(np.searchsorted(self.cum, d, side='right')) - 1
        i = min(max(i, 0), len(self.pts) - 2)
        seg = self.cum[i + 1] - self.cum[i]
        u = 0 if seg == 0 else (d - self.cum[i]) / seg
        return lerp2(self.pts[i], self.pts[i + 1], u)

    def sub(self, a, b):
        a, b = cl(a, 0, self.L), cl(b, 0, self.L)
        pts = [self.at(a)]
        for p, d in zip(self.pts, self.cum):
            if a < d < b:
                pts.append(p)
        pts.append(self.at(b))
        return pts

    def node_len(self, i):
        return self.cum[i]


def trail(c, pl, head, tail=0.0, w=5.0, a=1.0, fade=True, dot=True, glow=1.0, n=14):
    """Teal light trail along polyline pl from length `tail` to `head`."""
    if a <= 0.01 or head - tail < 0.5:
        return
    head = min(head, pl.L)
    tail = max(tail, 0)
    if fade:
        cuts = [tail + (head - tail) * i / n for i in range(n + 1)]
        chunks = [(pl.sub(cuts[i], cuts[i + 1]), ((i + 1) / n) ** 1.6) for i in range(n)]
    else:
        chunks = [(pl.sub(tail, head), 1.0)]
    for pts, al in chunks:
        path = poly(pts, False)
        c.drawPath(path, P(C(TEAL, 0.45 * a * al * glow), stroke=w * 4.5, blur=w * 2.6))
    for pts, al in chunks:
        path = poly(pts, False)
        c.drawPath(path, P(C(TEAL, a * al), stroke=w))
        c.drawPath(path, P(C(TEAL_HI, 0.85 * a * al), stroke=max(w * 0.38, 0.8)))
    if dot:
        hx, hy = pl.at(head)
        c.drawCircle(hx, hy, w * 6, P(C(TEAL, 0.55 * a), blur=w * 3.5))
        c.drawCircle(hx, hy, w * 1.25, P(C(WHITE, a)))


def check_path(cx, cy, r, p=1.0):
    """Check mark polyline inside a circle of radius r, drawn up to fraction p."""
    pts = [(cx - r * 0.42, cy + r * 0.02), (cx - r * 0.12, cy + r * 0.32), (cx + r * 0.45, cy - r * 0.3)]
    pl = Polyline(pts)
    return poly(pl.sub(0, pl.L * p), False)


def check_badge(c, cx, cy, r, t, t0, col=GREEN, label=None, lf=None):
    """Green check that pops in exactly at t0 (on the beat)."""
    if t < t0:
        c.drawCircle(cx, cy, r, P(C('#C9D3D8'), stroke=2.2))
        # rotating 'pending' arc
        ang = (t * 360) % 360
        path = skia.Path()
        path.addArc(R(cx - r, cy - r, 2 * r, 2 * r), ang, 70)
        c.drawPath(path, P(C(TEAL, 0.8), stroke=2.6))
        return
    p = pr(t, t0, t0 + 0.32)
    s = eob(p, 2.4) if p < 1 else 1
    burst = pr(t, t0, t0 + 0.55)
    if burst < 1:
        c.drawCircle(cx, cy, r * (1 + 1.4 * eoc(burst)), P(C(col, 0.5 * (1 - burst)), stroke=3))
    c.drawCircle(cx, cy, r * s * 1.6, P(C(col, 0.28 * (1 - 0.6 * burst)), blur=r * 0.7))
    c.drawCircle(cx, cy, r * s, P(C(col)))
    c.drawPath(check_path(cx, cy, r * s, eoc(pr(t, t0 + 0.05, t0 + 0.3))), P(C(WHITE), stroke=r * 0.2))


# --------------------------------------------------------------------------
# shared assets
# --------------------------------------------------------------------------
_qr = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
_qr.add_data('PROOF PACK concept | UZIN NC 567 | QNG')
_qr.make(fit=True)
QR = _qr.get_matrix()
QN = len(QR)

rng = np.random.default_rng(7)
GRAIN = []
for _i in range(4):
    g = (128 + rng.normal(0, 38, (H // 2, W // 2))).clip(0, 255).astype(np.uint8)
    rgba = np.dstack([g, g, g, np.full_like(g, 255)])
    GRAIN.append(skia.Image.fromarray(rgba, colorType=skia.ColorType.kRGBA_8888_ColorType))


def draw_qr(c, x, y, size, col=CHAR):
    m = size / QN
    p = P(C(col))
    p.setAntiAlias(False)
    for j, row in enumerate(QR):
        i = 0
        while i < QN:
            if row[i]:
                k = i
                while k < QN and row[k]:
                    k += 1
                c.drawRect(R(x + i * m, y + j * m, (k - i) * m + 0.4, m + 0.4), p)
                i = k
            else:
                i += 1


SACK_W, SACK_H = 300, 420
SACK_QR = (228, 330)        # QR centre in sack-local coordinates


def draw_sack(c, x, y, sc, light=1.0):
    """Product sack, local 300x420, drawn with top-left at (x,y)."""
    c.save()
    c.translate(x, y)
    c.scale(sc, sc)
    body = skia.Path()
    body.moveTo(20, 30)
    body.lineTo(280, 30)
    body.quadTo(308, 215, 290, 406)
    body.quadTo(150, 426, 10, 406)
    body.quadTo(-8, 215, 20, 30)
    body.close()
    c.drawPath(body, P(C('#0B1A20', 0.22), blur=14))
    c.drawPath(body, P(C(WHITE), shader=lin(0, 0, 300, 0, [C('#F4F6F7'), C('#FFFFFF'), C('#E3E8EA')], [0, .35, 1])))
    c.save()
    c.clipPath(body, doAntiAlias=True)
    c.drawRect(R(-20, 262, 340, 170), P(C(TEAL)))
    c.drawRect(R(-20, 254, 340, 6), P(C(CHAR)))
    c.drawRect(R(-20, 0, 340, 440), P(C(WHITE), shader=lin(0, 0, 300, 0, [C('#000000', 0.10), C('#000000', 0), C('#000000', 0.16)], [0, .4, 1])))
    c.restore()
    c.drawRRect(RR(14, 6, 272, 34, 8), P(C('#EEF1F2')))
    c.drawRRect(RR(14, 6, 272, 34, 8), P(C('#D5DCDF'), stroke=1.5))
    for i in range(22):
        c.drawLine(26 + i * 12, 23, 32 + i * 12, 23, P(C('#B9C3C7'), stroke=1.6))
    text(c, 'UZIN', 34, 122, font('InterDisplay-Black', 70), C(CHAR))
    text(c, 'NC 567', 36, 172, font('InterDisplay-SemiBold', 36), C(TEAL))
    for i, wd in enumerate([200, 170, 120]):
        c.drawRRect(RR(36, 196 + i * 16, wd, 7, 3.5), P(C('#D6DDE0')))
    c.drawRRect(RR(172, 274, 112, 112, 10), P(C(WHITE)))
    draw_qr(c, 182, 284, 92)
    c.restore()


def bg_light(c, t, grid_shift=0.0):
    c.drawRect(R(0, 0, W, H), P(C(WHITE), shader=lin(0, 0, 0, H, [C('#F7FCFD'), C('#E5F5F7')])))
    # architectural guide grid, slow parallax
    gp = P(C(TEAL, 0.07), stroke=1)
    off = (grid_shift + t * 18) % 120
    for i in range(-1, 18):
        x = i * 120 - off
        c.drawLine(x, 0, x, H, gp)
    for j in range(-1, 10):
        y = j * 120 + 30
        c.drawLine(0, y, W, y, gp)
    c.drawRect(R(0, 0, W, H), P(C(WHITE), shader=radg(960, 500, 1100, [C(WHITE, 0.0), C('#CFE6EA', 0.55)])))


def vignette(c, a=0.35, col='#000000'):
    c.drawRect(R(0, 0, W, H), P(C(col), shader=radg(960, 540, 1250, [C(col, 0), C(col, 0), C(col, a)], [0, 0.55, 1])))


def chip(c, x, y, label, col=TEAL, a=1.0, f=None, fill=None, txt=None):
    f = f or font('Inter-SemiBold', 18)
    w = tw(label, f) + 44
    c.drawRRect(RR(x, y, w, 40, 20), P(C(fill or col, a)))
    text(c, label, x + 22, y + 26.5, f, C(txt or WHITE, a))
    return w


# --------------------------------------------------------------------------
# SCENE 1 - studio, daycare model, floor plan (0 - 3.67)
# --------------------------------------------------------------------------
class Cam:
    def __init__(self, pos, tgt, f=1450.0):
        self.pos = np.array(pos, float)
        fwd = np.array(tgt, float) - self.pos
        self.fwd = fwd / np.linalg.norm(fwd)
        r = np.cross(self.fwd, [0, 0, 1.0])
        self.right = r / np.linalg.norm(r)
        self.up = np.cross(self.right, self.fwd)
        self.f = f

    def p(self, X):
        d = np.array(X, float) - self.pos
        z = max(d @ self.fwd, 1e-3)
        return (960 + self.f * (d @ self.right) / z, 540 - self.f * (d @ self.up) / z)

    def depth(self, X):
        return (np.array(X, float) - self.pos) @ self.fwd


LIGHT = np.array([-0.3, -1.0, -0.85])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def s1_cam(t):
    e = eio(pr(t, 0, 3.7))
    pos = (lerp(-26, -10, e), lerp(-132, -100, e), lerp(92, 70, e))
    tgt = (lerp(6, 14, e), lerp(14, 8, e), 0)
    return Cam(pos, tgt)


def gable_box(x0, x1, y0, y1, h, rh, axis):
    """Faces (list of 3D polygons) for a box with a pitched roof."""
    F = []
    if axis == 'x':
        ym = (y0 + y1) / 2
        F.append([(x0, y0, 0), (x1, y0, 0), (x1, y0, h), (x0, y0, h)])
        F.append([(x1, y1, 0), (x0, y1, 0), (x0, y1, h), (x1, y1, h)])
        F.append([(x0, y1, 0), (x0, y0, 0), (x0, y0, h), (x0, ym, h + rh), (x0, y1, h)])
        F.append([(x1, y0, 0), (x1, y1, 0), (x1, y1, h), (x1, ym, h + rh), (x1, y0, h)])
        F.append([(x0, y0, h), (x1, y0, h), (x1, ym, h + rh), (x0, ym, h + rh)])
        F.append([(x1, y1, h), (x0, y1, h), (x0, ym, h + rh), (x1, ym, h + rh)])
    else:
        xm = (x0 + x1) / 2
        F.append([(x0, y1, 0), (x0, y0, 0), (x0, y0, h), (x0, y1, h)])
        F.append([(x1, y0, 0), (x1, y1, 0), (x1, y1, h), (x1, y0, h)])
        F.append([(x0, y0, 0), (x1, y0, 0), (x1, y0, h), (xm, y0, h + rh), (x0, y0, h)])
        F.append([(x1, y1, 0), (x0, y1, 0), (x0, y1, h), (xm, y1, h + rh), (x1, y1, h)])
        F.append([(x1, y0, h), (x1, y1, h), (xm, y1, h + rh), (xm, y0, h + rh)])
        F.append([(x0, y1, h), (x0, y0, h), (xm, y0, h + rh), (xm, y1, h + rh)])
    return F


MODEL = [
    gable_box(40, 76, -16, -2, 7, 5, 'x'),
    gable_box(44, 58, -2, 22, 7, 5, 'y'),
    gable_box(62, 74, -2, 14, 5, 0.01, 'x'),
]
TREES = [(80, 6, 4.0), (36, 14, 3.4), (80, -10, 3.0), (66, 20, 3.6)]


def face_normal(f):
    a, b, c_ = (np.array(f[i], float) for i in (0, 1, 2))
    n = np.cross(b - a, c_ - a)
    return n / (np.linalg.norm(n) + 1e-9)


# floor plan in sheet-local px (1600 x 1000). world: x=-50+u/20, y=18-v/20
SHEET_ROUTE = [(760, 1120), (760, 760), (760, 470), (1180, 470), (1180, 330),
               (1500, 330), (1640, 330), (1800, 380)]


def sheet_matrix(cam):
    corners = [(-50, 18, 0), (30, 18, 0), (30, -32, 0), (-50, -32, 0)]
    return quad_matrix(1600, 1000, [cam.p(p) for p in corners])


def draw_plan(c, t):
    ink = C(CHAR, 0.9)
    thin = P(C(CHAR, 0.35), stroke=1.4)
    c.drawRect(R(0, 0, 1600, 1000), P(C('#FDFCFA')))
    c.drawRect(R(30, 30, 1540, 940), P(C(CHAR, 0.5), stroke=2))
    # structural grid with axis bubbles
    fa = font('Inter-Medium', 18)
    for i, x in enumerate([200, 480, 750, 1020, 1300]):
        c.drawLine(x, 90, x, 850, P(C(TEAL, 0.25), stroke=1.2))
        c.drawCircle(x, 70, 18, P(C(CHAR, 0.6), stroke=1.6))
        text(c, 'ABCDE'[i], x, 77, fa, C(CHAR, 0.7), 'c')
    for j, y in enumerate([180, 470, 760]):
        c.drawLine(110, y, 1390, y, P(C(TEAL, 0.25), stroke=1.2))
        c.drawCircle(90, y, 18, P(C(CHAR, 0.6), stroke=1.6))
        text(c, str(j + 1), 90, y + 7, fa, C(CHAR, 0.7), 'c')
    # walls
    c.drawRect(R(200, 180, 1100, 580), P(ink, stroke=11))
    wp = P(ink, stroke=6)
    for x0, y0, x1, y1 in [(200, 420, 1300, 420), (200, 520, 1300, 520), (480, 180, 480, 420),
                           (750, 180, 750, 420), (1020, 180, 1020, 420), (480, 520, 480, 760),
                           (900, 520, 900, 760), (1100, 520, 1100, 760)]:
        c.drawLine(x0, y0, x1, y1, wp)
    # door gaps + swings
    for (x, y, d) in [(330, 420, 1), (610, 420, 1), (880, 420, 1), (1150, 420, 1),
                      (330, 520, -1), (1000, 520, -1), (760, 760, -1)]:
        c.drawLine(x - 30, y, x + 30, y, P(C('#FDFCFA'), stroke=14))
        pth = skia.Path()
        pth.addArc(R(x - 30 - 60, y - 60, 120, 120), 0 if d < 0 else -90, 90 if d < 0 else 90)
        c.drawPath(pth, thin)
    # furniture hints
    for (x, y) in [(340, 300), (615, 300), (885, 300), (1160, 300)]:
        c.drawRRect(RR(x - 60, y - 30, 120, 60, 18), thin)
        for k in range(4):
            c.drawCircle(x - 45 + k * 30, y + 52, 9, thin)
    fl = font('Inter-SemiBold', 19)
    for (s, x, y) in [('GRUPPE 1', 340, 230), ('GRUPPE 2', 615, 230), ('GRUPPE 3', 885, 230),
                      ('SCHLAFEN', 1160, 230), ('FLUR', 1050, 478), ('GARDEROBE', 340, 640),
                      ('EINGANG', 690, 640), ('KÜCHE', 1000, 640), ('BAD', 1200, 640)]:
        text(c, s, x, y, fl, C(CHAR, 0.55), 'c', track=2)
    # dimension line
    c.drawLine(200, 840, 1300, 840, thin)
    for x in (200, 480, 750, 1020, 1300):
        c.drawLine(x - 8, 848, x + 8, 832, P(C(CHAR, 0.5), stroke=1.6))
    text(c, '27,50', 750, 830, font('Inter-Medium', 16), C(CHAR, 0.6), 'c')
    # title block
    c.drawRect(R(1240, 870, 330, 100), P(C(CHAR, 0.5), stroke=1.6))
    text(c, 'KITA STUTTGART-WEST', 1260, 905, font('Inter-Bold', 18), C(CHAR, 0.8))
    text(c, 'GRUNDRISS EG  ·  1:100', 1260, 940, font('Inter-Medium', 16), C(CHAR, 0.6))


def scene1(c, t):
    cam = s1_cam(t)
    # --- back wall + window (soft focus layer)
    blur = skia.Paint(ImageFilter=skia.ImageFilters.Blur(7, 7))
    c.saveLayer(None, blur)
    c.drawRect(R(-50, -50, W + 100, H + 100), P(C('#EFE7DB')))
    wall = [cam.p((-400, 95, 0)), cam.p((400, 95, 0)), cam.p((400, 95, 260)), cam.p((-400, 95, 260))]
    c.drawPath(poly(wall), P(C('#EDE4D6'), shader=lin(0, 0, W, 0, [C('#E2D7C7'), C('#F4ECDF')])))
    win = [cam.p((8, 95, 12)), cam.p((130, 95, 12)), cam.p((130, 95, 220)), cam.p((8, 95, 220))]
    c.drawPath(poly(win), P(C('#FFF6E6')))
    c.drawPath(poly(win), P(C('#FFFFFF', 0.9), blur=30))
    for xm in (48, 90):
        c.drawPath(poly([cam.p((xm - 1, 95, 12)), cam.p((xm + 1, 95, 12)), cam.p((xm + 1, 95, 220)), cam.p((xm - 1, 95, 220))]), P(C('#5E5850', 0.8)))
    c.drawPath(poly([cam.p((8, 95, 52)), cam.p((130, 95, 52)), cam.p((130, 95, 54)), cam.p((8, 95, 54))]), P(C('#5E5850', 0.8)))
    c.restore()

    # --- desk
    desk = [cam.p((-400, 95, 0)), cam.p((400, 95, 0)), cam.p((400, -200, 0)), cam.p((-400, -200, 0))]
    c.drawPath(poly(desk), P(C('#EAE3D8'), shader=lin(0, 250, 0, H, [C('#E9E1D4'), C('#F1ECE4')])))
    # warm morning light patch through the window on the desk
    def onDesk(x, z):
        tt = z / -LIGHT[2]
        return (x + LIGHT[0] * tt, 95 + LIGHT[1] * tt, 0)
    patch = [cam.p(onDesk(8, 12)), cam.p(onDesk(130, 12)), cam.p(onDesk(130, 140)), cam.p(onDesk(8, 140))]
    c.drawPath(poly(patch), P(C('#FFE7BF', 0.55), blur=26))

    # --- floor plan sheet (true perspective via homography)
    m = sheet_matrix(cam)
    c.save()
    c.concat(m)
    c.drawRect(R(18, 30, 1600, 1000), P(C('#3A2A10', 0.25), blur=22))
    draw_plan(c, t)
    # route
    head = eio(pr(t, 1.05, 3.25))
    pl = Polyline(SHEET_ROUTE)
    if head > 0:
        trail(c, pl, pl.L * head, 0, w=9, fade=False, dot=head < 1, glow=1.0)
        if head >= 1:
            hx, hy = pl.at(pl.L)
            k = 0.5 + 0.5 * math.sin((t - 3.25) * 14)
            c.drawCircle(hx, hy, 40 + 10 * k, P(C(TEAL, 0.6), blur=24))
            c.drawCircle(hx, hy, 12, P(C(WHITE)))
    c.restore()

    # --- the white architectural model (flat shaded, painter's algorithm)
    for (x, y, r) in TREES:
        pass
    shadow_pts = []
    for box in MODEL:
        base = [v for f in box for v in f if v[2] == 0]
        xs = [v[0] for v in base]
        ys = [v[1] for v in base]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        sh = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        shadow_pts.append([cam.p((a - 5, b - 9, 0)) for a, b in sh])
    for sp in shadow_pts:
        c.drawPath(poly(sp), P(C('#4A3A22', 0.28), blur=16))
    faces = []
    for box in MODEL:
        for f in box:
            n = face_normal(f)
            ctr = np.mean(np.array(f, float), axis=0)
            if n @ (cam.pos - ctr) <= 0:
                continue
            faces.append((cam.depth(ctr), f, n))
    for (x, y, r) in TREES:
        faces.append((cam.depth((x, y, r)), ('tree', x, y, r), None))
    faces.sort(key=lambda q: -q[0])
    for d, f, n in faces:
        if f[0] == 'tree':
            _, x, y, r = f
            cx, cy = cam.p((x, y, r * 1.6))
            ex, ey = cam.p((x + r, y, r * 1.6))
            rr = abs(ex - cx)
            bx, by = cam.p((x, y, 0))
            c.drawLine(bx, by, cx, cy, P(C('#B59A72'), stroke=3))
            c.drawCircle(cx, cy, rr, P(C('#D9C29C'), shader=radg(cx + rr * .3, cy - rr * .3, rr * 1.2, [C('#F0DFC2'), C('#C8AE84')])))
            continue
        lit = 0.80 + 0.20 * max(0.0, float(n @ -LIGHT))
        if n[2] > 0.5:
            lit = 0.97
        col = mixc('#B8B0A4', '#FFFDF9', lit)
        pts = [cam.p(v) for v in f]
        c.drawPath(poly(pts), P(C(col)))
        c.drawPath(poly(pts), P(C('#CFC7BB', 0.9), stroke=1.1))
        # punched windows on long walls
        if abs(n[2]) < 0.1 and len(f) == 4:
            a3, b3 = np.array(f[0], float), np.array(f[1], float)
            Lw = np.linalg.norm(b3 - a3)
            k = int(Lw // 6)
            for i in range(k):
                u0 = (i + 0.3) / k
                u1 = (i + 0.75) / k
                q = [a3 + (b3 - a3) * u0 + [0, 0, 2.2], a3 + (b3 - a3) * u1 + [0, 0, 2.2],
                     a3 + (b3 - a3) * u1 + [0, 0, 5.0], a3 + (b3 - a3) * u0 + [0, 0, 5.0]]
                c.drawPath(poly([cam.p(v) for v in q]), P(C('#8E877D', 0.55)))

    # --- volumetric shafts of morning light
    c.drawPath(poly([cam.p((8, 95, 150)), cam.p((130, 95, 150)), cam.p(onDesk(130, 12)), cam.p(onDesk(8, 12))]),
               P(C('#FFF1D6', 0.16), blur=40, blend=skia.BlendMode.kScreen))

    # --- Samantha: out-of-focus foreground silhouette (depth of field)
    sx = lerp(0, -30, eio(pr(t, 0, 3.7)))
    sil = skia.Path()
    sil.addOval(R(70 + sx, 380, 300, 370))
    sil.addOval(R(170 + sx, 330, 150, 130))
    body = skia.Path()
    body.moveTo(-160 + sx, H + 60)
    body.cubicTo(-120 + sx, 760, 60 + sx, 700, 230 + sx, 700)
    body.cubicTo(420 + sx, 700, 560 + sx, 820, 600 + sx, H + 60)
    body.close()
    c.drawPath(body, P(C('#2A2E31'), blur=16))
    c.drawPath(sil, P(C('#2E2A27'), blur=14))
    rim = skia.Path()
    rim.addArc(R(80 + sx, 360, 300, 380), -70, 75)
    c.drawPath(rim, P(C('#FFD9A0', 0.55), stroke=8, blur=8))

    # --- type
    a_out = 1 - pr(t, 3.15, 3.45)
    reveal(c, 'A daycare in Stuttgart', 120, 176, font('InterDisplay-Bold', 66), CHAR, t, 0.25, alpha=a_out)
    if t > 1.15:
        p = eob(pr(t, 1.15, 1.5), 2.0)
        c.save()
        c.translate(122, 214)
        c.scale(max(p, 0.001), max(p, 0.001))
        f = font('Inter-Bold', 22)
        wq = tw('QNG required', f, 2) + 64
        c.drawRRect(RR(0, 0, wq, 48, 24), P(C(TEAL, a_out)))
        c.drawCircle(26, 24, 6, P(C(WHITE, a_out)))
        text(c, 'QNG required', 44, 32, f, C(WHITE, a_out), track=2)
        c.restore()
    if t > 0.7:
        a = pr(t, 0.7, 1.1) * a_out
        f = font('Inter-Medium', 22)
        c.drawCircle(120, 1000, 6, P(C(TEAL, a)))
        text(c, 'Samantha  ·  Architect', 138, 1008, f, C(WHITE, 0.9 * a))
    vignette(c, 0.22, '#3B2A14')


def s1_head_screen(t):
    cam = s1_cam(t)
    m = sheet_matrix(cam)
    pl = Polyline(SHEET_ROUTE)
    return mp(m, *pl.at(pl.L))


# --------------------------------------------------------------------------
# SCENE 2 - scattered PDFs, certificates, emails (3.67 - 7.0)
# --------------------------------------------------------------------------
WINDOWS = [
    # kind, cx, cy, w, h, z, rz, title
    ('pdf', 700, 360, 440, 540, 220, -5, 'EPD_NC567_model.pdf'),
    ('mail', 1310, 320, 560, 360, 120, 3, 'Inbox  ·  RE: QNG evidence?'),
    ('cert', 470, 700, 400, 500, 60, 5, 'Emission_test_report.pdf'),
    ('web', 1460, 720, 540, 420, 260, -3, 'UZIN MK 92 S  ·  Product page'),
    ('sheet', 1010, 760, 520, 330, 20, 2, 'QNG_requirements_v4.xlsx'),
    ('pdf', 280, 300, 380, 480, 320, -7, 'Safety_data_sheet_v7.pdf'),
    ('mail', 1680, 380, 430, 300, -20, 6, 'FW: certificate missing?'),
    ('cert', 1080, 250, 420, 320, -110, -2, 'Declaration_2025.pdf'),
    ('pdf', 1660, 900, 380, 300, -60, 4, 'Test_report_scan_03.pdf'),
    ('web', 640, 920, 470, 320, -160, -5, 'Product data sheet'),
]


def draw_window(c, kind, w, h, title):
    c.drawRRect(RR(0, 18, w, h, 14), P(C('#000000', 0.45), blur=26))
    c.drawRRect(RR(0, 0, w, h, 14), P(C('#FBFCFC')))
    c.save()
    c.clipRRect(RR(0, 0, w, h, 14), doAntiAlias=True)
    c.drawRect(R(0, 0, w, 44), P(C('#E9EDEF')))
    for i, col in enumerate(['#D9A0A0', '#E5CD9A', '#A9CFA9']):
        c.drawCircle(22 + i * 20, 22, 6, P(C(col)))
    text(c, title, 90, 28, font('Inter-Medium', 16), C(CHAR, 0.85))
    gp = P(C('#DCE2E5'))
    if kind == 'pdf':
        c.drawRect(R(30, 70, w - 60, h - 100), P(C(WHITE)))
        c.drawRect(R(30, 70, w - 60, h - 100), P(C('#E1E6E8'), stroke=1.2))
        c.drawRect(R(54, 96, w * 0.45, 16), P(C(CHAR, 0.75)))
        for i in range(int((h - 180) / 22)):
            ww = (w - 110) * (0.55 + 0.45 * ((i * 37) % 10) / 10)
            c.drawRRect(RR(54, 136 + i * 22, ww, 8, 4), gp)
    elif kind == 'cert':
        c.drawCircle(w / 2, 130, 48, P(C(TEAL, 0.9), stroke=6))
        c.drawCircle(w / 2, 130, 34, P(C(TEAL, 0.25)))
        c.drawRect(R(w * 0.2, 200, w * 0.6, 14), P(C(CHAR, 0.7)))
        for i in range(int((h - 260) / 22)):
            c.drawRRect(RR(w * 0.15, 236 + i * 22, w * 0.7 * (0.6 + 0.4 * ((i * 53) % 10) / 10), 8, 4), gp)
    elif kind == 'mail':
        for i in range(int((h - 60) / 58)):
            y = 62 + i * 58
            c.drawCircle(40, y + 22, 16, P(C(['#9FB3BC', TEAL, '#C7B49B', '#8E9AA0'][i % 4], 0.8)))
            c.drawRRect(RR(70, y + 8, 160, 10, 5), P(C(CHAR, 0.6)))
            c.drawRRect(RR(70, y + 28, w - 120, 8, 4), gp)
            if i == 0:
                c.drawCircle(w - 30, y + 14, 6, P(C(AMBER)))
            c.drawLine(20, y + 52, w - 20, y + 52, P(C('#EDF0F1'), stroke=1))
    elif kind == 'web':
        c.drawRect(R(0, 44, w, 40), P(C('#F2F5F6')))
        c.drawRRect(RR(24, 104, w * 0.38, h - 140, 10), P(C(PALE)))
        c.drawRRect(RR(w * 0.38 + 48, 110, w * 0.4, 18, 6), P(C(CHAR, 0.7)))
        for i in range(int((h - 200) / 22)):
            c.drawRRect(RR(w * 0.38 + 48, 148 + i * 22, w * 0.5 * (0.5 + 0.5 * ((i * 29) % 10) / 10), 8, 4), gp)
    elif kind == 'sheet':
        for i in range(9):
            c.drawLine(0, 70 + i * 30, w, 70 + i * 30, P(C('#E1E6E8'), stroke=1))
        for j in range(6):
            c.drawLine(40 + j * 90, 44, 40 + j * 90, h, P(C('#E1E6E8'), stroke=1))
        for i in range(8):
            for j in range(5):
                if (i * 7 + j * 3) % 5:
                    c.drawRRect(RR(52 + j * 90, 81 + i * 30, 40 + ((i + j) % 3) * 12, 8, 4), gp)
            if i in (2, 5):
                c.drawRRect(RR(412, 78 + i * 30, 50, 14, 7), P(C(AMBER, 0.7)))
    c.restore()


def s2_win_state(i, t):
    kind, cx, cy, w, h, z, rz, title = WINDOWS[i]
    t0 = WINDOW_POPS[i]
    p = pr(t, t0, t0 + 0.32)
    s = 0.82 + 0.18 * eob(p, 1.6) if p < 1 else 1.0
    a = eoc(pr(t, t0, t0 + 0.12))
    zz = z - (t - S2) * 110
    ry = 6 * math.sin(t * 0.9 + i)
    rx = 3 * math.cos(t * 0.7 + i * 1.3)
    q = eio(pr(t, SLASH + 0.06 + i * 0.012, SLASH + 0.42 + i * 0.012))
    if q > 0:
        cx = lerp(cx, 960, q)
        cy = lerp(cy, 600, q)
        s *= lerp(1, 0.08, q)
        a *= 1 - q
        rz = lerp(rz, 0, q)
        zz = lerp(zz, 0, q)
    return dict(kind=kind, w=w, h=h, cx=cx, cy=cy, z=zz, rz=rz + (1 - p) * 4, ry=ry, rx=rx, s=s, a=a, title=title)


def s2_path():
    pts = [(960, 540)] + [(w[1], w[2]) for w in WINDOWS]
    return pts


def scene2(c, t):
    c.drawRect(R(0, 0, W, H), P(C(CHAR), shader=radg(960, 520, 1200, [C('#46525A'), C('#2A3135'), C('#1A1F22')], [0, .55, 1])))
    dp = P(C(WHITE, 0.06))
    for i in range(0, W, 48):
        for j in range(0, H, 48):
            c.drawCircle(i + 24, j + 24, 1.4, dp)
    states = [s2_win_state(i, t) for i in range(len(WINDOWS)) if t >= WINDOW_POPS[i]]
    states.sort(key=lambda s_: -s_['z'])
    for st in states:
        if st['a'] <= 0.01:
            continue
        m = card_matrix(st['w'], st['h'], st['cx'], st['cy'], rx=st['rx'], ry=st['ry'], rz=st['rz'], z=st['z'], s=st['s'])
        c.saveLayerAlpha(None, int(255 * st['a']))
        c.concat(m)
        draw_window(c, st['kind'], st['w'], st['h'], st['title'])
        c.restore()
    # the searching teal line, visiting each document as it opens
    pts = s2_path()
    times = [S2 - 0.05] + WINDOW_POPS
    pl = Polyline(catmull(pts, 12))
    # node lengths along smoothed path
    node_L = [pl.cum[i * 12] if i * 12 < len(pl.cum) else pl.L for i in range(len(pts))]
    if t <= times[0]:
        head = 0
    elif t >= times[-1]:
        head = pl.L
    else:
        k = int(np.searchsorted(times, t, side='right')) - 1
        u = eio(pr(t, times[k], times[k + 1]))
        head = lerp(node_L[k], node_L[k + 1], u)
    la = 1 - pr(t, SLASH, SLASH + 0.12)
    trail(c, pl, head, max(0, head - 1400), w=5, a=la)
    # samantha in the foreground, lit by the screens
    c.drawPath(poly([(-100, H + 50), (-60, 850), (150, 780), (330, 820), (470, H + 50)]), P(C('#0E1113'), blur=22))
    c.drawOval(R(40, 560, 250, 300), P(C('#101315'), blur=18))
    rim = skia.Path()
    rim.addArc(R(40, 560, 250, 300), -80, 80)
    c.drawPath(rim, P(C(TEAL, 0.45), stroke=6, blur=7))
    # headline with soft scrim
    a_out = 1 - pr(t, SLASH - 0.15, SLASH + 0.1)
    if t > bt(-5):
        c.drawOval(R(420, 420, 1080, 260), P(C('#0D1113', 0.65 * a_out * pr(t, bt(-5), bt(-5) + 0.3)), blur=60))
    reveal(c, 'Proof is scattered.', 960, 585, font('InterDisplay-Bold', 104), WHITE, t, bt(-5), align='c', alpha=a_out)
    # the slash: line cuts through the clutter
    if t >= SLASH:
        p = eoe(pr(t, SLASH, SLASH + 0.2))
        fade = 1 - pr(t, SLASH + 0.25, SLASH + 0.5)
        sl = Polyline([(-100, 610), (2020, 590)])
        trail(c, sl, sl.L * p, max(0, sl.L * p - 900), w=7, a=fade)
    vignette(c, 0.45)


# --------------------------------------------------------------------------
# SCENE 3 - one product page + PROOF PACK button (6.6 - 10.33)
# --------------------------------------------------------------------------
PC_W, PC_H = 1180, 660
BTN = (510, 392, 380, 88)


def s3_matrix(t):
    intro = eoc(pr(t, 6.62, 7.12))
    s = lerp(0.7, 1.0, intro)
    ry = lerp(9, -5, eio(pr(t, 6.7, 10.4)))
    return card_matrix(PC_W, PC_H, 960, 640, rx=4, ry=ry, z=lerp(0, -50, pr(t, 7, 10.4)), s=s)


def btn_scale(t):
    if t < CLICK - 0.08:
        return 1.0
    if t < CLICK:
        return 1 - 0.06 * pr(t, CLICK - 0.08, CLICK)
    return 0.94 + 0.06 * eob(pr(t, CLICK, CLICK + 0.35), 3)


def draw_proof_button(c, x, y, w, h, t, glow=1.0):
    k = math.exp(-max(0, t - CLICK) * 2.5) if t >= CLICK else 0.0
    c.drawRRect(RR(x - 6, y + 10, w + 12, h, h / 2), P(C(TEAL, 0.35 + 0.4 * k * glow), blur=22 + 30 * k))
    c.drawRRect(RR(x, y, w, h, h / 2), P(C(TEAL), shader=lin(x, y, x, y + h, [C('#11A9BC'), C('#008799')])))
    c.drawRRect(RR(x + 2, y + 2, w - 4, h * 0.5, h / 2 - 2), P(C(WHITE, 0.12)))
    # shield + check icon
    ix, iy = x + 52, y + h / 2
    sh = skia.Path()
    sh.moveTo(ix, iy - 20)
    sh.lineTo(ix + 16, iy - 13)
    sh.quadTo(ix + 16, iy + 12, ix, iy + 21)
    sh.quadTo(ix - 16, iy + 12, ix - 16, iy - 13)
    sh.close()
    c.drawPath(sh, P(C(WHITE), stroke=3))
    c.drawPath(check_path(ix, iy, 15), P(C(WHITE), stroke=3.4))
    text(c, 'PROOF PACK', x + 92, y + h / 2 + 9, font('Inter-Bold', 26), C(WHITE), track=4)


def draw_product_page(c, t):
    w, h = PC_W, PC_H
    c.drawRRect(RR(0, 30, w, h, 28), P(C('#0B2A33', 0.22), blur=40))
    c.drawRRect(RR(0, 0, w, h, 28), P(C(WHITE)))
    c.drawRRect(RR(0, 0, w, h, 28), P(C('#DDE7EA'), stroke=1.5))
    text(c, 'UZIN UTZ', 44, 46, font('Inter-Bold', 20), C(CHAR), track=3)
    fn = font('Inter-Medium', 16)
    for i, s in enumerate(['Products', 'Systems', 'Sustainability', 'Service']):
        text(c, s, 330 + i * 150, 45, fn, C(GREY))
    c.drawCircle(w - 60, 39, 13, P(C(GREY), stroke=2))
    c.drawLine(w - 50, 49, w - 42, 57, P(C(GREY), stroke=2))
    c.drawLine(0, 76, w, 76, P(C('#E8EEF0'), stroke=1.5))
    c.drawRRect(RR(40, 104, 420, 520, 22), P(C(PALE)))
    c.drawOval(R(110, 560, 290, 40), P(C('#0B2A33', 0.18), blur=12))
    draw_sack(c, 120, 140, 0.92)
    text(c, 'Products  /  Flooring  /  UZIN NC 567', 510, 146, font('Inter-Medium', 15), C(GREY))
    text(c, 'UZIN NC 567', 508, 214, font('InterDisplay-Bold', 56), C(CHAR))
    for i, wd in enumerate([520, 470, 330]):
        c.drawRRect(RR(510, 246 + i * 22, wd, 10, 5), P(C('#E3E9EC')))
    x = 510
    for s in ['Data sheet', 'SDS', 'EPD', 'Certificates']:
        f = font('Inter-Medium', 15)
        ww = tw(s, f) + 30
        c.drawRRect(RR(x, 330, ww, 34, 17), P(C('#C9D3D7'), stroke=1.4))
        text(c, s, x + 15, 352, f, C(GREY))
        x += ww + 10
    bx, by, bw, bh = BTN
    s = btn_scale(t)
    c.save()
    c.translate(bx + bw / 2, by + bh / 2)
    c.scale(s, s)
    draw_proof_button(c, -bw / 2, -bh / 2, bw, bh, t)
    c.restore()
    text(c, 'All sustainability evidence for your project, in one view.', 510, 524, font('Inter-Regular', 17), C(GREY))
    # line orbiting the page after activation
    if t > CLICK:
        x0, y0, x1, y1, r = 0, 0, w, h, 28
        per = [(bx + bw, by + bh / 2), (w, by + bh / 2), (w, h - r), (w - r, h), (r, h), (0, h - r), (0, r), (r, 0), (w - r, 0), (w, r), (w, by + bh / 2)]
        pl = Polyline(per)
        hd = eoc(pr(t, CLICK, CLICK + 2.6)) * pl.L
        trail(c, pl, hd, max(0, hd - 1600), w=4.5, a=1 - pr(t, 9.5, 9.8))


def draw_cursor(c, x, y, s=1.0):
    c.save()
    c.translate(x, y)
    c.scale(s, s)
    pth = poly([(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)])
    c.drawPath(pth, P(C('#000000', 0.35), blur=4))
    c.drawPath(pth, P(C(WHITE)))
    c.drawPath(pth, P(C(CHAR), stroke=2))
    c.restore()


def s3_button_quad(t):
    m = s3_matrix(t)
    bx, by, bw, bh = BTN
    return [mp(m, bx, by), mp(m, bx + bw, by), mp(m, bx + bw, by + bh), mp(m, bx, by + bh)]


def scene3(c, t):
    bg_light(c, t)
    m = s3_matrix(t)
    c.save()
    c.concat(m)
    draw_product_page(c, t)
    c.restore()
    # ripples from the click
    q = s3_button_quad(t)
    bcx = sum(p[0] for p in q) / 4
    bcy = sum(p[1] for p in q) / 4
    for d in (0.0, 0.14):
        p = pr(t, CLICK + d, CLICK + d + 0.9)
        if 0 < p < 1:
            r = 60 + 520 * eoc(p)
            c.drawCircle(bcx, bcy, r, P(C(TEAL, 0.55 * (1 - p)), stroke=3 + 6 * (1 - p)))
    # cursor
    if t < CLICK + 0.6:
        cp = eio(pr(t, 6.55, CLICK - 0.06))
        x = lerp(1560, bcx + 40, cp)
        y = lerp(1000, bcy + 6, cp)
        cs = 1.0 - 0.15 * (pr(t, CLICK - 0.06, CLICK) - pr(t, CLICK + 0.05, CLICK + 0.15))
        c.saveLayerAlpha(None, int(255 * (1 - pr(t, CLICK + 0.3, CLICK + 0.6))))
        draw_cursor(c, x, y, cs)
        c.restore()
    reveal(c, 'One place to check.', 960, 196, font('InterDisplay-Bold', 84), CHAR, t, bt(1), align='c',
           cols=[TEAL, TEAL, CHAR, CHAR], t_out=bt(5) - 0.1)
    # button expands to fill the frame -> becomes the Proof Pack interface
    e = eic(pr(t, bt(5), S4))
    if e > 0:
        x0 = min(p[0] for p in q)
        x1 = max(p[0] for p in q)
        y0 = min(p[1] for p in q)
        y1 = max(p[1] for p in q)
        X0, Y0, X1, Y1 = lerp(x0, -30, e), lerp(y0, -30, e), lerp(x1, W + 30, e), lerp(y1, H + 30, e)
        rr = lerp((y1 - y0) / 2, 0, e)
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(X0, Y0, X1, Y1), rr, rr), P(C(TEAL)))
        f = font('Inter-Bold', 26 + 70 * e)
        text(c, 'PROOF PACK', (X0 + X1) / 2, (Y0 + Y1) / 2 + 10 + 25 * e, f, C(WHITE, 1 - e * 0.6), 'c', track=4 + 14 * e)


# --------------------------------------------------------------------------
# SCENE 4/5 - Proof Pack interface + open point (10.33 - 19.22)
# --------------------------------------------------------------------------
PW, PH = 1180, 790
ROWS = [
    ('UZIN NC 567', 'Indoor air emissions', 'Test report', '03/2026', 'ok'),
    ('UZIN MK 92 S', 'Indoor air emissions', 'Test report', '02/2026', 'ok'),
    ('UZIN MK 92 S', 'Hazardous substances', 'Safety data sheet', '11/2025', 'ok'),
    ('UZIN NC 567', 'Life-cycle assessment', 'Model EPD', '01/2026', 'open'),
]
ROW_Y0, ROW_H, ROW_G = 288, 92, 12
ROW_T = ROW_CHECKS + [AMBER_IN]
LINE_X = 944


def panel_params(t):
    e = eio(pr(t, S4, S5 + 0.3))
    ry = lerp(-15, -8, e)
    z = lerp(120, 0, eoc(pr(t, S4, S4 + 1.6)))
    back = eio(pr(t, S5, S5 + 0.65))
    z += 520 * back
    cx = 1250 + lerp(0, -260, back)
    cy = 555 + 6 * math.sin(t * 1.3)
    return dict(cx=cx, cy=cy, rx=3, ry=lerp(ry, -2, back), z=z)


def panel_matrix(t):
    pp = panel_params(t)
    return card_matrix(PW, PH, pp['cx'], pp['cy'], rx=pp['rx'], ry=pp['ry'], z=pp['z'])


def draw_status(c, x, y, kind, t, t0):
    if kind == 'ok':
        check_badge(c, x + 16, y, 16, t, t0)
        if t >= t0:
            a = pr(t, t0 + 0.05, t0 + 0.3)
            text(c, 'Meets QNG', x + 44, y + 7, font('Inter-SemiBold', 18), C(GREEN, a))
        else:
            text(c, 'Checking…', x + 44, y + 7, font('Inter-Medium', 18), C(GREY, 0.8))
    else:
        if t < t0:
            text(c, 'Checking…', x + 44, y + 7, font('Inter-Medium', 18), C(GREY, 0.8))
            c.drawCircle(x + 16, y, 16, P(C('#C9D3D8'), stroke=2.2))
            return
        p = eob(pr(t, t0, t0 + 0.35), 2)
        c.drawCircle(x + 16, y, 16 * 1.8, P(C(AMBER, 0.25), blur=10))
        c.drawCircle(x + 16, y, 16 * p, P(C(AMBER)))
        text(c, '!', x + 16, y + 7, font('Inter-Bold', 20), C(WHITE), 'c')
        text(c, 'Open point', x + 44, y + 7, font('Inter-SemiBold', 18), C('#C9882A', pr(t, t0, t0 + 0.3)))


def draw_panel(c, t, header=True):
    w, h = PW, PH
    build = lambda i: eoc(pr(t, S4 + 0.32 + i * 0.07, S4 + 0.75 + i * 0.07))  # noqa: E731
    c.drawRRect(RR(0, 40, w, h, 30), P(C('#0B2A33', 0.20), blur=50))
    c.drawRRect(RR(0, 0, w, h, 30), P(C(WHITE, 0.94)))
    c.drawRRect(RR(0, 0, w, h, 30), P(C(WHITE), stroke=2))
    c.save()
    c.clipRRect(RR(0, 0, w, h, 30), doAntiAlias=True)
    if header:
        c.drawRect(R(0, 0, w, 100), P(C(TEAL), shader=lin(0, 0, w, 0, [C('#00A2B6'), C('#008A9C')])))
    a = pr(t, S4 + 0.45, S4 + 0.75)
    text(c, 'PROOF PACK', 44, 60, font('Inter-Bold', 24), C(WHITE, a), track=4)
    text(c, 'PROJECT', 700, 46, font('Inter-SemiBold', 13), C(WHITE, 0.75 * a), track=2.5)
    text(c, 'Daycare, Stuttgart', 700, 74, font('InterDisplay-SemiBold', 26), C(WHITE, a))
    c.drawRRect(RR(w - 150, 34, 110, 34, 17), P(C(WHITE, 0.2 * a)))
    text(c, '4 products', w - 95, 57, font('Inter-Medium', 15), C(WHITE, a), 'c')
    c.restore()
    # certification chips
    b = build(0)
    c.saveLayerAlpha(None, int(255 * b))
    c.translate(0, (1 - b) * 20)
    text(c, 'CERTIFICATION', 44, 146, font('Inter-SemiBold', 13), C(GREY), track=2.5)
    x = 44
    sel = eoc(pr(t, QNG_SELECT, QNG_SELECT + 0.25))
    for i, s in enumerate(['QNG', 'DGNB', 'LEED v4', 'EU Taxonomy']):
        f = font('Inter-SemiBold', 18)
        ww = tw(s, f) + 48
        if i == 0:
            if sel > 0:
                c.drawRRect(RR(x - 2, 162, ww + 4, 48, 24), P(C(TEAL, 0.35 * sel), blur=14))
            c.drawRRect(RR(x, 164, ww, 44, 22), P(C(TEAL, sel)))
            c.drawRRect(RR(x, 164, ww, 44, 22), P(C(mixc('#C9D3D7', TEAL, sel)), stroke=1.6))
            text(c, s, x + 24, 192, f, C(mixc(CHAR, WHITE, sel)))
        else:
            c.drawRRect(RR(x, 164, ww, 44, 22), P(C('#C9D3D7'), stroke=1.6))
            text(c, s, x + 24, 192, f, C(CHAR, 0.75))
        x += ww + 12
    c.restore()
    # table header
    b = build(1)
    hf = font('Inter-SemiBold', 13)
    for s, x in [('PRODUCT', 44), ('REQUIREMENT', 300), ('SOURCE', 572), ('DATE', 806), ('STATUS', 966)]:
        text(c, s, x, 266, hf, C(GREY, b), track=2.5)
    for i, (prod, req, src, date, kind) in enumerate(ROWS):
        b = build(2 + i)
        if b <= 0:
            continue
        y = ROW_Y0 + i * (ROW_H + ROW_G)
        c.saveLayerAlpha(None, int(255 * b))
        c.translate((1 - b) * 70, 0)
        fill = '#FFF8EC' if (kind == 'open' and t >= AMBER_IN) else '#F6FAFB'
        bord = '#F1D7A8' if (kind == 'open' and t >= AMBER_IN) else '#E2EBEE'
        c.drawRRect(RR(24, y, w - 48, ROW_H, 18), P(C(fill)))
        c.drawRRect(RR(24, y, w - 48, ROW_H, 18), P(C(bord), stroke=1.5))
        cy = y + ROW_H / 2
        text(c, prod, 44, cy + 8, font('InterDisplay-SemiBold', 22), C(CHAR))
        text(c, req, 300, cy + 7, font('Inter-Medium', 18), C(CHAR, 0.9))
        c.drawRRect(RR(572, cy - 12, 18, 24, 3), P(C(TEAL), stroke=1.8))
        c.drawLine(576, cy - 3, 586, cy - 3, P(C(TEAL), stroke=1.5))
        c.drawLine(576, cy + 3, 586, cy + 3, P(C(TEAL), stroke=1.5))
        text(c, src, 602, cy + 7, font('Inter-Regular', 18), C(CHAR, 0.9))
        text(c, date, 806, cy + 7, font('Inter-Regular', 18), C('#5B666C'))
        draw_status(c, 966, cy, kind, t, ROW_T[i])
        c.restore()
    # footer
    b = build(6)
    done = sum(1 for k in ROW_CHECKS if t >= k)
    fy = ROW_Y0 + 4 * (ROW_H + ROW_G) + 34
    s = f'{done} of 4 requirements verified' + ('  ·  1 open point' if t >= AMBER_IN else '')
    text(c, s, 44, fy + 6, font('Inter-Medium', 17), C(GREY, b))
    c.drawRRect(RR(700, fy - 6, 436, 10, 5), P(C('#E3ECEF', b)))
    prog = sum(eoc(pr(t, k, k + 0.3)) for k in ROW_CHECKS) / 4
    c.drawRRect(RR(700, fy - 6, max(436 * prog, 0.1), 10, 5), P(C(TEAL, b)))
    # the line runs down the status column, reaching each row on the beat
    nodes = [(LINE_X, 100)] + [(LINE_X, ROW_Y0 + i * (ROW_H + ROW_G) + ROW_H / 2) for i in range(4)]
    pl = Polyline(nodes)
    tt = [S4 + 0.6] + ROW_T
    if t > tt[0]:
        if t >= tt[-1]:
            hd = pl.L
        else:
            k = int(np.searchsorted(tt, t, side='right')) - 1
            hd = lerp(pl.cum[k], pl.cum[k + 1], eio(pr(t, tt[k], tt[k + 1])))
        trail(c, pl, hd, 0, w=4, fade=False, dot=t < tt[-1] + 0.2)


def side_card_a(c, t, a):
    c.drawRRect(RR(0, 20, 290, 116, 22), P(C('#0B2A33', 0.18), blur=26))
    c.drawRRect(RR(0, 0, 290, 116, 22), P(C(WHITE, 0.92)))
    c.drawRRect(RR(0, 0, 290, 116, 22), P(C(WHITE), stroke=2))
    text(c, 'SOURCES LINKED', 26, 38, font('Inter-SemiBold', 13), C(GREY), track=2.5)
    n = int(round(12 * eoc(pr(t, S4 + 0.9, S4 + 2.2))))
    text(c, str(n), 26, 96, font('InterDisplay-Bold', 48), C(TEAL))
    text(c, 'documents, one view', 92, 94, font('Inter-Medium', 17), C(CHAR, 0.8))


def side_card_b(c, t, a):
    c.drawRRect(RR(0, 20, 340, 124, 22), P(C('#0B2A33', 0.18), blur=26))
    c.drawRRect(RR(0, 0, 340, 124, 22), P(C(WHITE, 0.92)))
    c.drawRRect(RR(0, 0, 340, 124, 22), P(C(WHITE), stroke=2))
    prog = sum(eoc(pr(t, k, k + 0.3)) for k in ROW_CHECKS) / 4
    c.drawCircle(64, 62, 34, P(C('#E3ECEF'), stroke=9))
    arc = skia.Path()
    arc.addArc(R(30, 28, 68, 68), -90, 360 * prog)
    c.drawPath(arc, P(C(GREEN), stroke=9))
    text(c, 'QNG READINESS', 122, 50, font('Inter-SemiBold', 13), C(GREY), track=2.5)
    text(c, f'{int(round(prog * 100))} %', 122, 96, font('InterDisplay-Bold', 40), C(CHAR))


def amber_card(c, t, a=1.0):
    w, h = 980, 340
    c.drawRRect(RR(0, 30, w, h, 30), P(C('#5A3A08', 0.18), blur=44))
    c.drawRRect(RR(0, 0, w, h, 30), P(C(WHITE)))
    c.save()
    c.clipRRect(RR(0, 0, w, h, 30), doAntiAlias=True)
    c.drawRect(R(0, 0, 14, h), P(C(AMBER)))
    c.drawRect(R(0, 0, w, h), P(C(WHITE), shader=radg(80, 60, 700, [C(AMBER, 0.10), C(AMBER, 0.0)])))
    c.restore()
    c.drawRRect(RR(0, 0, w, h, 30), P(C('#F0D3A0'), stroke=2))
    if a <= 0:
        return
    c.saveLayerAlpha(None, int(255 * a))
    breathe = 0.5 + 0.5 * math.sin(t * 5.6)
    c.drawCircle(66, 72, 16 + 6 * breathe, P(C(AMBER, 0.35), blur=8))
    c.drawCircle(66, 72, 9, P(C(AMBER)))
    text(c, 'OPEN POINT', 92, 80, font('Inter-Bold', 20), C('#C9882A'), track=5)
    text(c, 'Product-specific EPD not available', 54, 166, font('InterDisplay-SemiBold', 46), C(CHAR))
    c.drawCircle(70, 226, 15, P(C(AMBER), stroke=2.6))
    text(c, 'i', 70, 233, font('Inter-Bold', 19), C(AMBER), 'c')
    text(c, 'Model EPD used', 100, 236, font('Inter-Medium', 32), C('#4E5960'))
    c.drawLine(54, 270, w - 54, 270, P(C('#EFE6D6'), stroke=1.5))
    text(c, 'UZIN NC 567   ·   Life-cycle assessment   ·   Source: model EPD, 01/2026', 54, 308, font('Inter-Regular', 19), C(GREY))
    c.restore()


AC_W, AC_H = 980, 340


def amber_quad(t, pm):
    """Amber card flies from its table row (in the panel) to the front."""
    y = ROW_Y0 + 3 * (ROW_H + ROW_G)
    src = [mp(pm, 24, y), mp(pm, PW - 24, y), mp(pm, PW - 24, y + ROW_H), mp(pm, 24, y + ROW_H)]
    sway = 2.5 * math.sin((t - S5) * 1.4)
    dst = proj_quad(AC_W, AC_H, 960, 640, rx=0, ry=sway, z=lerp(60, -20, pr(t, S5, S6)))
    e = eio(pr(t, S5 + 0.05, S5 + 0.7))
    return [lerp2(p, q, e) for p, q in zip(src, dst)], e


def scene45(c, t, ox=0.0):
    bg_light(c, t, grid_shift=-ox)
    c.save()
    c.translate(ox, 0)
    pm = panel_matrix(t)
    back = eio(pr(t, S5, S5 + 0.65))
    # header transition: full-frame teal shrinks into the panel header
    hdr = eio(pr(t, S4, S4 + 0.55))
    # floating side cards (separate depth -> parallax)
    def side(fn, cx, cy, z, t0, w_, h_):
        b = eoc(pr(t, t0, t0 + 0.5))
        if b <= 0:
            return
        bz = z + (1 - b) * 900 + back * 700
        aa = b * (1 - back)
        if aa <= 0.01:
            return
        m = card_matrix(w_, h_, cx + 12 * math.sin(t * 1.1 + cx), cy + 8 * math.cos(t * 1.4), rx=3, ry=-10, z=bz)
        c.saveLayerAlpha(None, int(255 * aa))
        c.concat(m)
        fn(c, t, aa)
        c.restore()
    if back > 0:
        blur = skia.Paint(ImageFilter=skia.ImageFilters.Blur(9 * back, 9 * back))
        c.saveLayer(None, blur)
    pass
    c.save()
    c.concat(pm)
    a_body = pr(t, S4 + 0.2, S4 + 0.5)
    if a_body > 0:
        c.saveLayerAlpha(None, int(255 * a_body))
        draw_panel(c, t, header=hdr >= 1)
        c.restore()
    c.restore()
    side(side_card_a, 330, 880, -60, S4 + 0.7, 290, 116)
    side(side_card_b, 760, 925, -220, S4 + 1.2, 340, 124)
    if back > 0:
        c.drawRect(R(-2000, -100, 6000, H + 200), P(C('#F2FAFB', 0.5 * back)))
        c.restore()
    if hdr < 1:
        hq = [mp(pm, 0, 0), mp(pm, PW, 0), mp(pm, PW, 100), mp(pm, 0, 100)]
        full = [(-ox - 40, -40), (W - ox + 40, -40), (W - ox + 40, H + 40), (-ox - 40, H + 40)]
        q = [lerp2(a, b, hdr) for a, b in zip(full, hq)]
        c.drawPath(poly(q), P(C(TEAL)))
    # kinetic copy
    out = S5 - 0.05
    f = font('InterDisplay-Bold', 62)
    reveal(c, 'Every requirement.', 96, 430, f, CHAR, t, bt(7), t_out=out)
    reveal(c, 'Every source.', 96, 516, f, CHAR, t, bt(10), t_out=out + 0.05)
    reveal(c, 'One page.', 96, 602, f, TEAL, t, bt(13), t_out=out + 0.1)
    # ---- scene 5: the open point comes forward
    if t >= S5:
        quad, e = amber_quad(t, pm)
        m = quad_matrix(AC_W, AC_H, quad)
        for tp in AMBER_PULSES:
            p = pr(t, tp, tp + 1.0)
            if 0 < p < 1:
                c.save()
                c.concat(quad_matrix(AC_W, AC_H, proj_quad(AC_W, AC_H, 960, 640, s=1 + 0.09 * eoc(p))))
                c.drawRRect(RR(0, 0, AC_W, AC_H, 30), P(C(AMBER, 0.55 * (1 - p)), stroke=3 + 3 * (1 - p)))
                c.restore()
                c.drawOval(R(960 - 560, 640 - 230, 1120, 460), P(C(AMBER, 0.10 * (1 - p)), blur=60))
        c.save()
        c.concat(m)
        amber_card(c, t, pr(e, 0.35, 1.0))
        c.restore()
        reveal(c, 'Clear about what is missing.', 960, 330, font('InterDisplay-Bold', 76), CHAR, t, bt(17), align='c',
               cols=[CHAR, CHAR, CHAR, CHAR, AMBER])
    c.restore()
    vignette(c, 0.12, '#0B2A33')


# --------------------------------------------------------------------------
# SCENE 6 - auditor tablet, verification ring (19.22 - 23.11)
# --------------------------------------------------------------------------
TB_W, TB_H = 1040, 700
RING_C = (26 + 790, 26 + 300)
RING_R = 150


def tablet_matrix(t, ox=0.0):
    sway = math.sin((t - S6) * 1.2) * 1.5
    return card_matrix(TB_W, TB_H, 1040 + ox, 625, rx=-20, ry=-7 + sway, rz=-2.5, z=lerp(80, -20, pr(t, S6, S7)))


def ring_screen(t, ox=0.0):
    m = tablet_matrix(t, ox)
    cx, cy = mp(m, *RING_C)
    ex, ey = mp(m, RING_C[0] + RING_R, RING_C[1])
    vx, vy = mp(m, RING_C[0], RING_C[1] + RING_R)
    return cx, cy, (math.hypot(ex - cx, ey - cy) + math.hypot(vx - cx, vy - cy)) / 2


def draw_tablet(c, t):
    w, h = TB_W, TB_H
    c.drawRRect(RR(10, 50, w - 20, h, 56), P(C('#0B2A33', 0.35), blur=46))
    c.drawRRect(RR(0, 0, w, h, 54), P(C('#1E2427')))
    c.drawRRect(RR(0, 0, w, h, 54), P(C('#4A5358'), stroke=2.5))
    c.drawCircle(w / 2, 14, 4, P(C('#3A4247')))
    c.save()
    c.translate(26, 26)
    sw, sh = w - 52, h - 52
    c.clipRRect(RR(0, 0, sw, sh, 32), doAntiAlias=True)
    c.drawRect(R(0, 0, sw, sh), P(C(WHITE), shader=lin(0, 0, 0, sh, [C(WHITE), C('#F3F9FA')])))
    text(c, 'AUDIT REVIEW', 56, 70, font('Inter-SemiBold', 15), C(GREY), track=3)
    text(c, 'Daycare, Stuttgart', 54, 116, font('InterDisplay-Bold', 38), C(CHAR))
    chip(c, 400, 86, 'QNG', f=font('Inter-Bold', 18))
    items = [('SOURCE', 'Accredited test report'), ('DATE', '03/2026  ·  valid'), ('STATUS', 'Meets QNG requirement')]
    for i, (lab, val) in enumerate(items):
        y = 162 + i * 96
        c.drawRRect(RR(44, y, 490, 80, 18), P(C('#F4F9FA')))
        c.drawRRect(RR(44, y, 490, 80, 18), P(C('#E1EAED'), stroke=1.5))
        text(c, lab, 74, y + 32, font('Inter-SemiBold', 13), C(GREY), track=2.5)
        text(c, val, 74, y + 62, font('Inter-SemiBold', 21), C(CHAR))
        check_badge(c, 492, y + 40, 18, t, AUDIT_CHECKS[i])
    c.drawCircle(64, 476, 7, P(C(AMBER)))
    text(c, '1 open point, documented', 82, 482, font('Inter-Medium', 17), C('#B07A22'))
    # verification ring = the teal line closing into a circle
    rx, ry = RING_C[0] - 26, RING_C[1] - 26
    c.drawCircle(rx, ry, RING_R, P(C('#E4ECEF'), stroke=16))
    p = eio(pr(t, RING_START, RING_DONE))
    done = pr(t, RING_DONE, RING_DONE + 0.18)
    col = mixc(TEAL, GREEN, done)
    if p > 0:
        arc = skia.Path()
        arc.addArc(R(rx - RING_R, ry - RING_R, 2 * RING_R, 2 * RING_R), -90, 359.9 * p)
        c.drawPath(arc, P(C(col, 0.45), stroke=26, blur=14))
        c.drawPath(arc, P(C(col), stroke=16))
        if p < 1:
            ang = math.radians(-90 + 360 * p)
            hx, hy = rx + RING_R * math.cos(ang), ry + RING_R * math.sin(ang)
            c.drawCircle(hx, hy, 26, P(C(TEAL, 0.6), blur=14))
            c.drawCircle(hx, hy, 7, P(C(WHITE)))
    if t >= RING_DONE:
        q = pr(t, RING_DONE, RING_DONE + 0.4)
        s = eob(q, 2.2)
        c.drawCircle(rx, ry, (RING_R - 26) * s, P(C(GREEN, 0.14)))
        c.drawPath(check_path(rx, ry, 110 * s, eoc(pr(t, RING_DONE + 0.04, RING_DONE + 0.32))), P(C(GREEN), stroke=20))
        bq = pr(t, RING_DONE, RING_DONE + 0.7)
        c.drawCircle(rx, ry, RING_R * (1 + 0.35 * eoc(bq)), P(C(GREEN, 0.5 * (1 - bq)), stroke=4))
        text(c, 'Verified', rx, ry + 222, font('InterDisplay-Bold', 36), C(GREEN, pr(t, RING_DONE, RING_DONE + 0.25)), 'c')
        text(c, 'Review time  ·  4 min', rx, ry + 256, font('Inter-Medium', 18), C(GREY, pr(t, RING_DONE + 0.1, RING_DONE + 0.35)), 'c')
    else:
        text(c, 'Checking sources…', rx, ry + 230, font('Inter-Medium', 22), C(GREY, pr(t, S6 + 0.4, S6 + 0.8)), 'c')
    c.restore()


def scene6(c, t, ox=0.0, bg=True):
    if bg:
        bg_light(c, t)
    # desk plane to ground the tablet
    c.drawRect(R(0, 690, W, H - 690), P(C(WHITE), shader=lin(0, 690, 0, H, [C('#DCEEF1', 0.0), C('#CFE6EA', 0.9)])))
    m = tablet_matrix(t, ox)
    c.save()
    c.concat(m)
    draw_tablet(c, t)
    c.restore()
    # auditor tag
    a = pr(t, S6 + 0.5, S6 + 0.9)
    if a > 0:
        c.saveLayerAlpha(None, int(255 * a))
        c.translate(ox, (1 - a) * 20)
        c.drawRRect(RR(150, 905, 290, 70, 35), P(C('#0B2A33', 0.15), blur=16))
        c.drawRRect(RR(150, 900, 290, 70, 35), P(C(WHITE)))
        c.drawCircle(186, 935, 22, P(C(CHAR)))
        c.drawCircle(186, 928, 8, P(C(WHITE)))
        c.drawOval(R(173, 939, 26, 18), P(C(WHITE)))
        text(c, 'QNG Auditor', 222, 932, font('Inter-SemiBold', 19), C(CHAR))
        text(c, 'Independent review', 222, 956, font('Inter-Regular', 15), C(GREY))
        c.restore()
    reveal(c, 'Verified in minutes.', 960 + ox, 176, font('InterDisplay-Bold', 84), CHAR, t, bt(24), align='c',
           cols=[GREEN, CHAR, CHAR], t_out=S7 - 0.35)


# --------------------------------------------------------------------------
# SCENE 7 - QR on the sack -> construction site becomes finished daycare
# --------------------------------------------------------------------------
VP = (960, 430)


def rp(u, s, hgt=0.0):
    return (VP[0] + 400 * u * s, VP[1] + (210 - 390 * hgt) * s)


SACK_POS = (0.30, 2.25)          # floor (u, s)
SACK_SC = 0.92


def sack_origin():
    bx, by = rp(*SACK_POS)
    return bx - SACK_W * SACK_SC / 2, by - SACK_H * SACK_SC + 10


def qr_screen():
    x, y = sack_origin()
    return x + SACK_QR[0] * SACK_SC, y + SACK_QR[1] * SACK_SC


_r7 = random.Random(11)
BLOTCH_W = [(_r7.uniform(-1, 1), _r7.uniform(1, 3.5), _r7.uniform(0.05, 0.95), _r7.uniform(14, 60), _r7.uniform(0.04, 0.12)) for _ in range(70)]
BLOTCH_F = [(_r7.uniform(-0.95, 0.95), _r7.uniform(1.05, 3.6), _r7.uniform(18, 70), _r7.uniform(0.05, 0.14)) for _ in range(60)]
DUST = [(_r7.uniform(0, W), _r7.uniform(0, H), _r7.uniform(1, 3), _r7.uniform(0.2, 1)) for _ in range(90)]
PLANKS = [_r7.uniform(0, 1) for _ in range(400)]


def room_shell(c, wall, back, floor, ceil):
    c.drawRect(R(0, 0, W, H), P(C(wall)))
    c.drawPath(poly([rp(-1, 1, 1), rp(1, 1, 1), rp(1, 6, 1), rp(-1, 6, 1)]), P(C(ceil)))
    c.drawPath(poly([rp(-1, 1, 0), rp(1, 1, 0), rp(1, 6, 0), rp(-1, 6, 0)]), P(C(floor)))
    c.drawPath(poly([rp(-1, 1, 0), rp(-1, 1, 1), rp(-1, 6, 1), rp(-1, 6, 0)]), P(C(mixc(wall, '#000000', 0.06))))
    c.drawPath(poly([rp(1, 1, 0), rp(1, 1, 1), rp(1, 6, 1), rp(1, 6, 0)]), P(C(mixc(wall, '#FFFFFF', 0.05))))
    c.drawPath(poly([rp(-1, 1, 0), rp(1, 1, 0), rp(1, 1, 1), rp(-1, 1, 1)]), P(C(back)))


def win_quad(s0, s1, h0, h1):
    return [rp(1, s0, h0), rp(1, s1, h0), rp(1, s1, h1), rp(1, s0, h1)]


def construction(c, t):
    room_shell(c, '#BDB8B0', '#C8C3BB', '#A3A09A', '#CFCBC4')
    # raw plaster blotches
    for (u, s, hg, r, a) in BLOTCH_W:
        if abs(u) > 0.98:
            continue
        x, y = rp(u, 1, hg)
        c.drawCircle(x, y, r * 0.7, P(C('#8F8A82', a), blur=r * 0.4))
    for (u, s, r, a) in BLOTCH_F:
        x, y = rp(u, s, 0)
        c.drawOval(R(x - r * s * 0.6, y - r * s * 0.12, r * s * 1.2, r * s * 0.24), P(C('#6E6B66', a), blur=6 * s))
    # window opening with protective sheeting
    for (s0, s1) in [(1.15, 1.6), (1.9, 2.6)]:
        q = win_quad(s0, s1, 0.22, 0.82)
        c.drawPath(poly(q), P(C('#F4F1EA')))
        c.drawPath(poly(q), P(C('#FFFFFF', 0.7), blur=20))
        c.drawPath(poly(q), P(C('#D8D4CC', 0.5), stroke=3))
    # light from window on the screed
    c.drawPath(poly([rp(0.98, 1.9, 0), rp(0.98, 2.6, 0), rp(0.2, 3.0, 0), rp(0.3, 2.1, 0)]), P(C('#FFF4DF', 0.28), blur=40))
    # conduits on the ceiling + bare bulb
    for k in (-0.4, 0.15):
        c.drawLine(*rp(k, 1, 1), *rp(k, 4, 1), P(C('#8C877F'), stroke=4))
    bx, by = rp(-0.1, 1.6, 0.72)
    c.drawLine(bx, rp(-0.1, 1.6, 1)[1], bx, by, P(C('#3C3A37'), stroke=2))
    c.drawCircle(bx, by, 70, P(C('#FFE6B0', 0.5), blur=40))
    c.drawCircle(bx, by, 10, P(C('#FFF6DD')))
    # ladder against the left wall
    lp = P(C('#6C6760'), stroke=7)
    a0, a1 = rp(-0.98, 1.5, 0), rp(-0.98, 1.25, 0.8)
    b0, b1 = rp(-0.85, 1.55, 0), rp(-0.85, 1.28, 0.8)
    c.drawLine(*a0, *a1, lp)
    c.drawLine(*b0, *b1, lp)
    for i in range(1, 7):
        u = i / 7
        c.drawLine(*lerp2(a0, a1, u), *lerp2(b0, b1, u), P(C('#6C6760'), stroke=5))
    # stacked sacks at the back, a bucket
    for i, (u, s) in enumerate([(0.62, 1.25), (0.74, 1.3), (0.68, 1.22)]):
        x, y = rp(u, s, 0)
        sc = s * 0.28
        c.drawRRect(RR(x - 150 * sc, y - 220 * sc - (i == 2) * 110 * sc, 300 * sc, 210 * sc, 20 * sc), P(C('#E9ECEC')))
        c.drawRect(R(x - 150 * sc, y - 90 * sc - (i == 2) * 110 * sc, 300 * sc, 70 * sc), P(C(TEAL, 0.85)))
    x, y = rp(-0.45, 1.8, 0)
    c.drawOval(R(x - 60, y - 18, 120, 30), P(C('#000000', 0.2), blur=8))
    c.drawPath(poly([(x - 55, y - 120), (x + 55, y - 120), (x + 46, y), (x - 46, y)]), P(C('#5E6A70')))
    c.drawOval(R(x - 55, y - 132, 110, 26), P(C('#4A5459')))
    c.drawOval(R(x - 48, y - 128, 96, 18), P(C('#9A958D')))
    # hero sack
    sx, sy = sack_origin()
    c.drawOval(R(sx - 10, sy + SACK_H * SACK_SC - 30, SACK_W * SACK_SC + 40, 50), P(C('#000000', 0.28), blur=14))
    draw_sack(c, sx, sy, SACK_SC)
    # floating dust
    for (x, y, r, a) in DUST:
        yy = (y - t * 14 * a) % H
        c.drawCircle(x + 8 * math.sin(t + y), yy, r, P(C('#FFF8E8', 0.25 * a)))
    c.drawRect(R(0, 0, W, H), P(C('#000000'), shader=lin(0, 0, 0, H, [C('#2A2015', 0.18), C('#2A2015', 0.0), C('#2A2015', 0.22)], [0, .4, 1])))


def shoe(c, x, y, sc, col, ang):
    c.save()
    c.translate(x, y)
    c.rotate(ang)
    c.scale(sc, sc * 0.55)
    c.drawOval(R(-30, -12 + 8, 64, 28), P(C('#000000', 0.18), blur=4))
    body = skia.Path()
    body.addRRect(RR(-30, -13, 62, 26, 13))
    c.drawPath(body, P(C(WHITE)))
    c.drawRRect(RR(-27, -10, 56, 20, 10), P(C(col)))
    c.drawOval(R(-20, -6, 22, 12), P(C(mixc(col, '#000000', 0.35))))
    c.drawLine(4, -6, 4, 6, P(C(WHITE), stroke=2.2))
    c.drawLine(12, -6, 12, 6, P(C(WHITE), stroke=2.2))
    c.restore()


def finished(c, t):
    room_shell(c, '#F6F3EE', '#FBFAF7', '#D9BC92', '#FDFCFA')
    # wainscot in pale teal on back + left wall
    c.drawPath(poly([rp(-1, 1, 0), rp(1, 1, 0), rp(1, 1, 0.3), rp(-1, 1, 0.3)]), P(C(PALE)))
    c.drawPath(poly([rp(-1, 1, 0), rp(-1, 1, 0.3), rp(-1, 6, 0.3), rp(-1, 6, 0)]), P(C('#DCEFF2')))
    # wooden floor planks converging to the vanishing point
    for k in range(-12, 13):
        u = k / 12
        c.drawLine(*rp(u, 1, 0), *rp(u, 6, 0), P(C('#B8976B', 0.45), stroke=1.4))
    i = 0
    for k in range(-12, 12):
        s = 1.0
        while s < 6:
            s += 0.35 + PLANKS[i % 400] * 0.6
            i += 1
            u0, u1 = k / 12, (k + 1) / 12
            c.drawLine(*rp(u0, s, 0), *rp(u1, s, 0), P(C('#B8976B', 0.35), stroke=1.2))
    # floor sheen
    c.drawPath(poly([rp(0.98, 1.15, 0), rp(0.98, 2.6, 0), rp(0.1, 3.4, 0), rp(0.25, 1.4, 0)]), P(C('#FFF7E6', 0.45), blur=46))
    # big low windows with garden view
    for (s0, s1) in [(1.15, 1.6), (1.9, 2.6)]:
        q = win_quad(s0, s1, 0.18, 0.82)
        c.drawPath(poly(q), P(C('#E8F4F8')))
        c.save()
        c.clipPath(poly(q), doAntiAlias=True)
        x0 = min(p[0] for p in q)
        y0 = min(p[1] for p in q)
        y1 = max(p[1] for p in q)
        c.drawRect(R(x0, y0, 600, y1 - y0), P(C(WHITE), shader=lin(0, y0, 0, y1, [C('#DDEFF7'), C('#F7FBF6')])))
        for j in range(5):
            c.drawCircle(x0 + 40 + j * 70, y1 - 30, 60 + 10 * (j % 2), P(C('#8FC79A', 0.8), blur=10))
        c.restore()
        c.drawPath(poly(q), P(C(WHITE), stroke=10))
        mid = [lerp2(q[0], q[1], 0.5), lerp2(q[3], q[2], 0.5)]
        c.drawLine(*mid[0], *mid[1], P(C(WHITE), stroke=6))
    # entrance door on the left wall
    door = [rp(-1, 1.18, 0), rp(-1, 1.55, 0), rp(-1, 1.55, 0.66), rp(-1, 1.18, 0.66)]
    c.drawPath(poly(door), P(C(TEAL)))
    c.drawPath(poly(door), P(C(WHITE), stroke=6))
    gl = [lerp2(door[0], door[3], 0.55), lerp2(door[1], door[2], 0.55), lerp2(door[1], door[2], 0.9), lerp2(door[0], door[3], 0.9)]
    gl = [lerp2(gl[0], gl[1], 0.2), lerp2(gl[0], gl[1], 0.8), lerp2(gl[3], gl[2], 0.8), lerp2(gl[3], gl[2], 0.2)]
    c.drawPath(poly(gl), P(C('#DDF1F5')))
    # coat hooks with little jackets
    for j, col in enumerate(['#E5533D', '#F2B33D', '#3D7FE5', '#43A879']):
        s = 1.75 + j * 0.28
        hx, hy = rp(-1, s, 0.52)
        c.drawCircle(hx, hy, 3 * s, P(C(CHAR)))
        jx, jy = rp(-1, s, 0.5)
        jb = rp(-1, s, 0.33)
        c.drawRRect(RR(jx - 9 * s, jy, 18 * s, jb[1] - jy, 6 * s), P(C(col, 0.9)))
    # low bench
    c.drawPath(poly([rp(-1, 1.7, 0.12), rp(-0.9, 1.7, 0.12), rp(-0.9, 2.9, 0.12), rp(-1, 2.9, 0.12)]), P(C('#E9D7BB')))
    c.drawPath(poly([rp(-0.9, 1.7, 0.12), rp(-0.9, 2.9, 0.12), rp(-0.9, 2.9, 0.0), rp(-0.9, 1.7, 0.0)]), P(C('#D5BF9C')))
    # colourful children's shoes near the entrance
    for (u, s, col, ang) in [(-0.84, 1.75, '#E5533D', -12), (-0.80, 1.78, '#E5533D', -8),
                             (-0.70, 2.15, '#F2B33D', 8), (-0.66, 2.2, '#F2B33D', 14),
                             (-0.80, 2.55, '#3D7FE5', -20), (-0.76, 2.6, '#3D7FE5', -14),
                             (-0.58, 2.85, '#E58FB0', 6), (-0.54, 2.92, '#E58FB0', 12)]:
        x, y = rp(u, s, 0)
        shoe(c, x, y, s * 0.55, col, ang)
    # small table + chairs
    tx, ty = rp(0.48, 1.55, 0.18)
    c.drawOval(R(tx - 120, ty + 50, 240, 30), P(C('#000000', 0.15), blur=10))
    for dx in (-80, 80):
        c.drawLine(tx + dx, ty + 6, tx + dx, ty + 62, P(C('#E9D7BB'), stroke=8))
    c.drawRRect(RR(tx - 110, ty - 10, 220, 24, 12), P(C(WHITE)))
    c.drawRRect(RR(tx - 110, ty - 10, 220, 24, 12), P(C('#E1D6C6'), stroke=1.5))
    for dx, col in [(-160, '#F2B33D'), (160, '#E5533D')]:
        c.drawRRect(RR(tx + dx - 26, ty - 30, 52, 60, 12), P(C(col)))
        c.drawRRect(RR(tx + dx - 30, ty + 18, 60, 14, 7), P(C(mixc(col, '#000000', 0.15))))
    # toy blocks
    for j, col in enumerate([TEAL, '#F2B33D', '#E5533D']):
        x, y = rp(-0.2 + j * 0.06, 1.18, 0)
        c.drawRect(R(x, y - 26, 26, 26), P(C(col)))
    # pendant lights
    for u in (-0.9, 0.9):
        x, y = rp(u, 1.6, 0.8)
        c.drawLine(x, rp(u, 1.6, 1)[1], x, y, P(C(CHAR), stroke=2))
        c.drawCircle(x, y + 10, 70, P(C('#FFF2D6', 0.5), blur=36))
        pth = skia.Path()
        pth.addArc(R(x - 34, y - 6, 68, 34), 180, 180)
        c.drawPath(pth, P(C(WHITE)))
    c.drawRect(R(0, 0, W, H), P(C(WHITE), shader=radg(1500, 500, 1300, [C('#FFF8EA', 0.25), C('#FFF8EA', 0.0)])))


PHONE_W, PHONE_H = 300, 610


def draw_phone(c, t):
    w, h = PHONE_W, PHONE_H
    c.drawRRect(RR(-6, 30, w + 12, h, 50), P(C('#000000', 0.35), blur=30))
    c.drawRRect(RR(0, 0, w, h, 46), P(C('#15191B')))
    c.save()
    c.clipRRect(RR(12, 12, w - 24, h - 24, 36), doAntiAlias=True)
    c.drawRect(R(0, 0, w, h), P(C('#8E8B85')))
    c.drawRect(R(0, 0, w, h), P(C('#000000'), shader=lin(0, 0, 0, h, [C('#000000', 0.1), C('#000000', 0.35)])))
    # camera view of the QR code
    qx, qy, qs = w / 2 - 70, 210, 140
    c.drawRRect(RR(qx - 12, qy - 12, qs + 24, qs + 24, 10), P(C(WHITE)))
    draw_qr(c, qx, qy, qs)
    br = P(C(TEAL), stroke=6)
    for (x, y, dx, dy) in [(qx - 30, qy - 30, 1, 1), (qx + qs + 30, qy - 30, -1, 1), (qx - 30, qy + qs + 30, 1, -1), (qx + qs + 30, qy + qs + 30, -1, -1)]:
        c.drawLine(x, y, x + 30 * dx, y, br)
        c.drawLine(x, y, x, y + 30 * dy, br)
    if t < QR_SCAN:
        sy = qy - 20 + (qs + 40) * (0.5 + 0.5 * math.sin((t - 23.5) * 9))
        c.drawLine(qx - 30, sy, qx + qs + 30, sy, P(C(TEAL_HI), stroke=3))
        c.drawLine(qx - 30, sy, qx + qs + 30, sy, P(C(TEAL, 0.7), stroke=14, blur=8))
    else:
        p = eoc(pr(t, QR_SCAN, QR_SCAN + 0.35))
        c.drawRRect(RR(22, h - 220 + (1 - p) * 120, w - 44, 190, 24), P(C(WHITE, p)))
        check_badge(c, 62, h - 170 + (1 - p) * 120, 20, t, QR_SCAN + 0.05)
        text(c, 'Proof Pack', 94, h - 162 + (1 - p) * 120, font('Inter-Bold', 22), C(CHAR, p))
        text(c, 'UZIN NC 567', 42, h - 110 + (1 - p) * 120, font('Inter-SemiBold', 18), C(CHAR, p))
        text(c, 'QNG  ·  4 sources  ·  1 open point', 42, h - 80 + (1 - p) * 120, font('Inter-Regular', 14), C(GREY, p))
    c.restore()
    c.drawRRect(RR(w / 2 - 50, 22, 100, 26, 13), P(C('#0A0C0D')))


def scene7_world(c, t, sweep_x):
    """Draws the room; left of sweep_x is already the finished daycare."""
    c.save()
    c.clipRect(R(sweep_x, -2000, 9000, 6000))
    construction(c, t)
    # worker's phone + gloved hand scanning the QR code
    pin = eoc(pr(t, S7 + 0.55, QR_SCAN - 0.05))
    if pin > 0:
        px = lerp(2000, 1560, pin)
        py = lerp(1300, 700, pin)
        m = card_matrix(PHONE_W, PHONE_H, px, py, rz=-9 + 3 * math.sin(t * 2), ry=-8)
        sl = skia.Path()
        sl.moveTo(px + 40, py + 180)
        sl.cubicTo(px + 160, py + 300, px + 300, py + 420, px + 520, py + 560)
        c.drawPath(sl, P(C('#2F3538'), stroke=170, blur=3))
        c.drawPath(sl, P(C('#D8DDE0', 0.6), stroke=14, blur=2))
        c.save()
        c.concat(m)
        draw_phone(c, t)
        for j in range(4):
            c.drawRRect(RR(-26, 250 + j * 58, 52, 48, 22), P(C('#3C4347')))
        c.drawRRect(RR(PHONE_W - 30, 330, 60, 120, 28), P(C('#3C4347')))
        c.restore()
    c.restore()
    if sweep_x > 0:
        c.save()
        c.clipRect(R(-2000, -2000, sweep_x + 2000, 6000))
        finished(c, t)
        c.restore()


def reticle(c, x, y, r, col, a=1.0):
    c.drawCircle(x, y, r, P(C(col, 0.4 * a), stroke=r * 0.12, blur=r * 0.08))
    c.drawCircle(x, y, r, P(C(col, a), stroke=max(3, r * 0.07)))


def scene7(c, t):
    qx, qy = qr_screen()
    rcx, rcy, rr = ring_screen(S7)
    rr *= S6_PUSH
    rcx, rcy = s6_push_map(rcx, rcy)
    R_WORLD = 92
    e = eio(pr(t, S7, S7 + 0.8))
    s = lerp(rr / R_WORLD, 1.0, e)
    px, py = lerp(rcx, qx, e), lerp(rcy, qy, e)
    sweep = eio(pr(t, SWEEP_START, SWEEP_END))
    sx = lerp(-80, W + 80, sweep)
    c.save()
    c.translate(px, py)
    c.scale(s, s)
    c.translate(-qx, -qy)
    scene7_world(c, t, sx if sweep > 0 else -1)
    # reticle around the QR (match-cut from the verification ring)
    ra = 1 - pr(t, QR_SCAN + 0.2, QR_SCAN + 0.6)
    if ra > 0 and (sweep <= 0 or sx < qx - 100):
        col = mixc(GREEN, TEAL, pr(t, S7, S7 + 0.35))
        reticle(c, qx, qy, R_WORLD * (1 + 0.08 * math.sin((t - S7) * 8)), col, ra)
    c.restore()
    if sweep > 0 and sweep < 1:
        # the scanning line sweeps the site into the finished room
        c.drawRect(R(sx - 260, 0, 260, H), P(C(TEAL), shader=lin(sx - 260, 0, sx, 0, [C(TEAL, 0), C(TEAL, 0.22)])))
        pl = Polyline([(sx, -20), (sx, H + 20)])
        trail(c, pl, pl.L, 0, w=7, fade=False, dot=False, glow=1.6)
        for k in range(14):
            yy = (k * 97 + t * 400) % H
            c.drawCircle(sx + 6 * math.sin(k + t * 9), yy, 3, P(C(WHITE, 0.8)))
    reveal(c, 'From product to handover.', 960, 168, font('InterDisplay-Bold', 80), CHAR, t, bt(33), align='c',
           cols=[CHAR, TEAL, CHAR, CHAR])
    vignette(c, 0.18, '#1A1408')


S6_PUSH = 1.45


def s6_push_map(x, y):
    return x, y


# --------------------------------------------------------------------------
# SCENE 8 - end card (27 - 30)
# --------------------------------------------------------------------------
def scene8(c, t, img7=None):
    c.drawRect(R(0, 0, W, H), P(C(CHAR)))
    c.drawRect(R(0, 0, W, H), P(C(CHAR), shader=radg(960, 560, 1100, [C('#4A545B'), C(CHAR), C('#2C3338')], [0, .5, 1])))
    gp = P(C(WHITE, 0.035), stroke=1)
    for i in range(0, W + 1, 120):
        c.drawLine(i, 0, i, H, gp)
    for j in range(0, H + 1, 120):
        c.drawLine(0, j, W, j, gp)
    if img7 is not None and t < FINAL_HIT:
        p = pr(t, FINAL_HIT - 0.55, FINAL_HIT)
        s = lerp(1.0, 0.05, eie(p) * 0.6 + eic(p) * 0.4)
        ang = -6 * eic(p)
        c.save()
        c.translate(960, 560)
        c.rotate(ang)
        c.scale(s, s)
        r = 40 / max(s, 0.05)
        c.drawRRect(RR(-960, -540 + 50 / max(s, 0.2), W, H, r), P(C('#000000', 0.5), blur=40))
        c.clipRRect(RR(-960, -540, W, H, r * min(1, p * 3)), doAntiAlias=True)
        c.drawImage(img7, -960, -540)
        c.restore()
        # fading info cards zooming past
        return
    tt = t - FINAL_HIT
    flash = math.exp(-tt * 7)
    c.drawCircle(960, 600, 900, P(C(TEAL, 0.25 * flash), blur=200))
    push = 1 + 0.025 * eoc(pr(t, FINAL_HIT, DUR))
    c.save()
    c.translate(960, 560)
    c.scale(push, push)
    c.translate(-960, -560)
    f = font('InterDisplay-Bold', 128)
    slogan = 'Proof, not pages.'
    sw = tw(slogan, f)
    p = eoe(pr(t, FINAL_HIT, FINAL_HIT + 0.45))
    c.save()
    sc = lerp(1.12, 1.0, p)
    c.translate(960, 600)
    c.scale(sc, sc)
    text(c, slogan, 0, 0, f, align='c', paint=P(C(WHITE, p), blur=(1 - p) * 10))
    c.restore()
    # UZIN UTZ wordmark (typography only, no logo invented)
    p2 = eoc(pr(t, FINAL_HIT + 0.12, FINAL_HIT + 0.6))
    text(c, 'UZIN UTZ', 960, 430 - (1 - p2) * 14, font('Inter-Bold', 38), C(WHITE, 0.95 * p2), 'c', track=12)
    # the teal line becomes the underline
    lp = eoe(pr(t, FINAL_HIT, FINAL_HIT + 0.7))
    pl = Polyline([(960 - sw / 2, 668), (960 + sw / 2, 668)])
    trail(c, pl, pl.L * lp, 0, w=7, fade=False, dot=lp < 0.995, glow=1.0 + 0.6 * math.exp(-tt * 3))
    p3 = pr(t, FINAL_HIT + 0.7, FINAL_HIT + 1.2)
    text(c, 'Concept film  ·  AI-assisted', 960, 1010, font('Inter-Medium', 22), C(WHITE, 0.55 * p3), 'c', track=2)
    c.restore()
    vignette(c, 0.35)


# --------------------------------------------------------------------------
# master timeline
# --------------------------------------------------------------------------
def snapshot(fn, *a):
    s = skia.Surface(W, H)
    fn(s.getCanvas(), *a)
    return s.makeImageSnapshot()


SAMP = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)


def draw_scaled(c, img, cx, cy, s, a=1.0):
    c.save()
    c.translate(cx, cy)
    c.scale(s, s)
    c.translate(-cx, -cy)
    p = skia.Paint(AntiAlias=True)
    p.setAlphaf(a)
    c.drawImage(img, 0, 0, SAMP, p)
    c.restore()


def bridge_trail(c, t, ox):
    """Teal line from the amber card (scene 5) into the auditor's ring (scene 6).
    ox = horizontal offset of the scene-5 frame (0 -> -1920 during the pan)."""
    if not (bt(21) < t < RING_START + 0.3):
        return
    m = tablet_matrix(t, ox + 1920)
    top = mp(m, RING_C[0], RING_C[1] - RING_R)
    pts = [(1450 + ox, 640), (1760 + ox, 600), (2150 + ox, 500), (top[0] - 380, top[1] - 120), (top[0] - 120, top[1] - 30), top]
    pl = Polyline(catmull(pts, 14))
    hd = eio(pr(t, bt(21), RING_START)) * pl.L
    trail(c, pl, hd, max(0, hd - 1100), w=5, a=1 - pr(t, RING_START, RING_START + 0.3))


def compose(c, t):
    if t < 3.25:
        scene1(c, t)
    elif t < S2 + 0.22:
        # dive into the line head -> into the screen
        hx, hy = s1_head_screen(3.25)
        img = snapshot(scene1, min(t, 3.6))
        p = pr(t, 3.25, S2 + 0.22)
        c.clear(C('#1A1F22'))
        draw_scaled(c, img, hx, hy, 1 + 9 * eie(p), 1 - pr(t, S2 - 0.1, S2 + 0.2))
        if t > S2 - 0.12:
            img2 = snapshot(scene2, t)
            q = pr(t, S2 - 0.12, S2 + 0.22)
            draw_scaled(c, img2, 960, 540, lerp(1.25, 1.0, eoc(q)), eoc(q))
        g = math.exp(-((t - S2) / 0.12) ** 2)
        c.drawCircle(hx * (1 - p) + 960 * p, hy * (1 - p) + 540 * p, 500, P(C(TEAL, 0.55 * g), blur=160))
    elif t < 6.62:
        scene2(c, t)
    elif t < 7.12:
        scene2(c, t)
        r = 1400 * eoc(pr(t, 6.62, 7.12))
        path = skia.Path()
        path.addCircle(960, 600, max(r, 0.1))
        c.save()
        c.clipPath(path, doAntiAlias=True)
        scene3(c, t)
        c.restore()
        c.drawCircle(960, 600, r, P(C(TEAL, 0.6 * (1 - pr(t, 6.9, 7.12))), stroke=6, blur=4))
    elif t < S4:
        scene3(c, t)
    elif t < S6:
        scene45(c, t)
        bridge_trail(c, t, 0)
    elif t < S6 + 0.75:
        e = eio(pr(t, S6, S6 + 0.75))
        ox = -1920 * e
        bg_light(c, t, grid_shift=-ox)
        img = snapshot(scene45, t, ox)
        c.drawImage(img, 0, 0)
        scene6(c, t, ox + 1920, bg=False)
        bridge_trail(c, t, ox)
    elif t < S7:
        # push into the ring just before the match cut
        p = eic(pr(t, S7 - 0.55, S7))
        cx, cy, rr = ring_screen(t)
        s = 1 + 0.45 * p
        c.save()
        c.translate(cx, cy)
        c.scale(s, s)
        c.translate(-cx, -cy)
        scene6(c, t)
        bridge_trail(c, t, -1920)
        c.restore()
    elif t < FINAL_HIT - 0.55:
        scene7(c, t)
    elif t < FINAL_HIT:
        img7 = snapshot(scene7, t)
        scene8(c, t, img7)
    else:
        scene8(c, t)


def finish(c, t):
    p = skia.Paint()
    p.setBlendMode(skia.BlendMode.kOverlay)
    p.setAlphaf(0.10)
    c.drawImageRect(GRAIN[int(t * FPS) % 4], R(0, 0, W, H), SAMP, p)


def frame(t):
    s = skia.Surface(W, H)
    c = s.getCanvas()
    c.clear(C(WHITE))
    compose(c, t)
    finish(c, t)
    return s.makeImageSnapshot().toarray(colorType=skia.ColorType.kRGBA_8888_ColorType)


def _frame_bytes(i):
    return frame(i / FPS)[:, :, :3].tobytes()


def main():
    cmd = sys.argv[1]
    if cmd == 'stills':
        os.makedirs(os.path.join(HERE, 'stills'), exist_ok=True)
        from PIL import Image
        for a in sys.argv[2:]:
            t = float(a)
            Image.fromarray(frame(t)[:, :, :3]).save(os.path.join(HERE, 'stills', f'{t:06.2f}.png'))
            print('still', t)
    elif cmd == 'endcard':
        from PIL import Image
        Image.fromarray(frame(29.9)[:, :, :3]).save(sys.argv[2])
    elif cmd == 'video':
        out = sys.argv[2]
        n = int(round(DUR * FPS))
        ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                               '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'slow',
                               '-crf', '14', '-pix_fmt', 'yuv420p', '-tune', 'animation', out], stdin=subprocess.PIPE)
        from multiprocessing import Pool
        with Pool(int(os.environ.get('JOBS', os.cpu_count()))) as pool:
            for i, b in enumerate(pool.imap(_frame_bytes, range(n), chunksize=2)):
                ff.stdin.write(b)
                if i % 30 == 0:
                    print(f'frame {i}/{n}', flush=True)
        ff.stdin.close()
        ff.wait()


if __name__ == '__main__':
    main()
