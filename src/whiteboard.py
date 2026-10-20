"""Whiteboard-story animation engine: black canvas, marker lettering, teal diagrams.

The video is a tall "world" canvas. Each scene sits at its own world_y and the camera
glides from scene to scene. Elements (text, boxes, containers, pods, arrows, terminals,
stick figures, badges, pills) pop in at given times and can change state later
(e.g. a pod crashing).

Because the background is a flat colour, fading is done by blending colours toward the
background, which keeps rendering fast (no per-element alpha layers).
"""
import math
import os
import re
import subprocess

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "assets", "fonts")

BG = (10, 10, 11)
WHITE = (238, 238, 238)
TEAL = (64, 196, 206)
TEAL_LINE = (46, 140, 150)
TEAL_FILL = (14, 30, 33)
CONT = (47, 157, 181)
RED = (226, 88, 88)
RED_LINE = (150, 58, 58)
RED_FILL = (40, 16, 18)
ORANGE = (245, 166, 35)
BLUE = (50, 108, 229)
GREY = (95, 98, 104)
DIM = (60, 62, 68)

MARKER = "PermanentMarker-Regular.ttf"
HAND = "GochiHand-Regular.ttf"
MONO = "DejaVuSansMono-Bold.ttf"

_fonts = {}


def font(name, size):
    key = (name, int(size))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(os.path.join(FONTS, name), max(6, int(size)))
    return _fonts[key]


def clamp(t):
    return max(0.0, min(1.0, t))


def ease_out(t):
    return 1 - (1 - clamp(t)) ** 3


def ease_in_out(t):
    t = clamp(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t):
    t = clamp(t)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def fade(c, a):
    a = clamp(a)
    return tuple(int(BG[i] + (c[i] - BG[i]) * a) for i in range(3))


def mixc(c1, c2, k):
    k = clamp(k)
    return tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3))


# ---------------------------------------------------------------- elements
class El:
    """Base element. t0 = appear time, t1 = disappear time (None = stays)."""
    sfx = "pop"

    def __init__(self, t0, t1=None, anim="pop", dur=0.4, sfx=None):
        self.t0, self.t1, self.anim, self.dur = t0, t1, anim, dur
        if sfx is not None:
            self.sfx = sfx

    def state(self, t):
        if t < self.t0 or (self.t1 is not None and t > self.t1 + 0.35):
            return None
        k = (t - self.t0) / self.dur
        a = ease_out(k * 1.6)
        if self.t1 is not None:
            a = min(a, 1 - ease_out((t - self.t1) / 0.35))
        if self.anim == "pop":
            s = 0.82 + 0.18 * ease_out_back(k)
            dy = 0
        elif self.anim == "rise":
            s, dy = 1.0, 40 * (1 - ease_out(k))
        else:  # fade
            s, dy = 1.0, 0
        return a, s, dy

    def events(self):
        return [(self.t0, self.sfx)] if self.sfx else []

    def draw(self, d, t, cam):
        st = self.state(t)
        if st:
            self.paint(d, t, cam, *st)

    def paint(self, d, t, cam, a, s, dy):
        raise NotImplementedError


class Text(El):
    sfx = None

    def __init__(self, t0, x, y, text, size=60, color=WHITE, fnt=MARKER, anchor="mm",
                 t1=None, anim="rise", typewriter=0.0, sfx=None):
        super().__init__(t0, t1, anim, sfx=sfx)
        self.x, self.y, self.text, self.size, self.color = x, y, text, size, color
        self.fnt, self.anchor, self.typewriter = fnt, anchor, typewriter

    def paint(self, d, t, cam, a, s, dy):
        txt = self.text
        if self.typewriter:
            n = int(len(txt) * clamp((t - self.t0) / self.typewriter))
            txt = txt[:n]
        if txt:
            d.text((self.x, self.y - cam + dy), txt, font=font(self.fnt, self.size * s),
                   fill=fade(self.color, a), anchor=self.anchor)


def rounded(d, box, r, fill=None, outline=None, width=3):
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def dashed_rect(d, box, color, width=3, dash=16, gap=11):
    x0, y0, x1, y1 = box
    for (ax, ay, bx, by) in [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]:
        dashed_line(d, (ax, ay), (bx, by), color, width, dash, gap)


def dashed_line(d, p1, p2, color, width=3, dash=16, gap=11, progress=1.0):
    (x1, y1), (x2, y2) = p1, p2
    length = math.hypot(x2 - x1, y2 - y1) * progress
    if length <= 0:
        return
    ux, uy = (x2 - x1) / math.hypot(x2 - x1, y2 - y1), (y2 - y1) / math.hypot(x2 - x1, y2 - y1)
    pos = 0.0
    while pos < length:
        e = min(pos + dash, length)
        d.line((x1 + ux * pos, y1 + uy * pos, x1 + ux * e, y1 + uy * e), fill=color, width=width)
        pos += dash + gap


class Box(El):
    """Panel with optional label. style: teal | red | dashed | dashed_red | plain"""
    sfx = "pop"

    def __init__(self, t0, x, y, w, h, style="teal", label=None, label_pos="top",
                 t1=None, crash_t=None, radius=22, sfx=None, label_size=46):
        super().__init__(t0, t1, "pop", sfx=sfx)
        self.x, self.y, self.w, self.h, self.style = x, y, w, h, style
        self.label, self.label_pos, self.crash_t, self.radius = label, label_pos, crash_t, radius
        self.label_size = label_size

    def colors(self, t):
        k = 0.0 if self.crash_t is None else clamp((t - self.crash_t) / 0.3)
        if self.style.endswith("red"):
            k = 1.0
        return mixc(TEAL_LINE, RED_LINE, k), mixc(TEAL_FILL, RED_FILL, k), mixc(TEAL, RED, k)

    def events(self):
        ev = super().events()
        if self.crash_t is not None:
            ev.append((self.crash_t, "error"))
        return ev

    def paint(self, d, t, cam, a, s, dy):
        cx, cy = self.x + self.w / 2, self.y + self.h / 2 - cam + dy
        w, h = self.w * s, self.h * s
        box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        line, fill, txt = self.colors(t)
        if self.style.startswith("dashed"):
            rounded(d, box, self.radius, fill=fade(fill, a * 0.6))
            dashed_rect(d, box, fade(line, a), 3)
        elif self.style != "plain":
            rounded(d, box, self.radius, fill=fade(fill, a), outline=fade(line, a), width=3)
        if self.label:
            ly = box[1] - 38 if self.label_pos == "top" else box[3] + 38
            d.text((cx, ly), self.label, font=font(MARKER, self.label_size * s),
                   fill=fade(txt, a), anchor="mm")


class Containers(El):
    """A row of small container squares; `red` = indexes drawn as failed."""
    sfx = "tick"

    def __init__(self, t0, x, y, n, size=50, gap=14, t1=None, stagger=0.06,
                 crash_t=None, color=CONT, empty_after=None):
        super().__init__(t0, t1, "pop")
        self.x, self.y, self.n, self.size, self.gap = x, y, n, size, gap
        self.stagger, self.crash_t, self.color, self.empty_after = stagger, crash_t, color, empty_after

    def width(self):
        return self.n * self.size + (self.n - 1) * self.gap

    def events(self):
        return [(self.t0, "tick")]

    def paint(self, d, t, cam, a, s, dy):
        for i in range(self.n):
            ti = self.t0 + i * self.stagger
            if t < ti:
                continue
            k = ease_out_back((t - ti) / 0.3)
            ai = min(a, ease_out((t - ti) / 0.2))
            sz = self.size * (0.4 + 0.6 * k)
            cx = self.x + i * (self.size + self.gap) + self.size / 2
            cy = self.y + self.size / 2 - cam + dy
            box = (cx - sz / 2, cy - sz / 2, cx + sz / 2, cy + sz / 2)
            red = self.crash_t is not None and t >= self.crash_t
            if self.empty_after is not None and t >= self.empty_after:
                rounded(d, box, 8, outline=fade(RED_LINE, ai), width=2)
            else:
                c = mixc(self.color, RED, clamp((t - self.crash_t) / 0.3)) if red else self.color
                rounded(d, box, 8, fill=fade(c, ai))


class AppCard(El):
    """A container drawn as a card: title + a few grey 'code' lines."""
    sfx = "pop"

    def __init__(self, t0, x, y, w, h, title, t1=None, crash_t=None, slide_from=None,
                 slide_t=None, slide_dur=0.7):
        super().__init__(t0, t1, "pop")
        self.x, self.y, self.w, self.h, self.title = x, y, w, h, title
        self.crash_t = crash_t
        self.slide_from, self.slide_t, self.slide_dur = slide_from, slide_t, slide_dur

    def pos(self, t):
        if self.slide_from and self.slide_t is not None:
            k = ease_in_out((t - self.slide_t) / self.slide_dur)
            return (self.slide_from[0] + (self.x - self.slide_from[0]) * k,
                    self.slide_from[1] + (self.y - self.slide_from[1]) * k)
        return self.x, self.y

    def paint(self, d, t, cam, a, s, dy):
        x, y = self.pos(t)
        cx, cy = x + self.w / 2, y + self.h / 2 - cam + dy
        w, h = self.w * s, self.h * s
        box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        k = 0 if self.crash_t is None else clamp((t - self.crash_t) / 0.3)
        rounded(d, box, 16, fill=fade(mixc((18, 40, 44), RED_FILL, k), a),
                outline=fade(mixc(TEAL_LINE, RED_LINE, k), a), width=3)
        size = 40
        while size > 18 and font(MARKER, size).getlength(self.title) > self.w - 28:
            size -= 2
        d.text((cx, box[1] + h * 0.28), self.title, font=font(MARKER, size * s),
               fill=fade(mixc(TEAL, RED, k), a), anchor="mm")
        for i, frac in enumerate((0.7, 0.55, 0.62)):
            ly = box[1] + h * (0.5 + i * 0.14)
            lw = w * frac
            d.line((cx - lw / 2, ly, cx + lw / 2, ly), fill=fade(mixc(GREY, RED_LINE, k), a),
                   width=5)


class Badge(El):
    """Status chip, e.g. WORKING / DOWN / NEW. Can switch text+style at switch_t."""
    sfx = None

    def __init__(self, t0, x, y, text, style="teal", t1=None, switch_t=None,
                 new_text=None, new_style=None, size=34):
        super().__init__(t0, t1, "pop")
        self.x, self.y, self.text, self.style = x, y, text, style
        self.switch_t, self.new_text, self.new_style, self.size = switch_t, new_text, new_style, size

    def paint(self, d, t, cam, a, s, dy):
        text, style = self.text, self.style
        if self.switch_t is not None and t >= self.switch_t:
            text, style = self.new_text, self.new_style
        col = {"teal": TEAL, "red": RED, "orange": ORANGE, "white": WHITE}[style]
        f = font(MARKER, self.size * s)
        tw = d.textlength(text, font=f)
        pad = 18 * s
        y = self.y - cam + dy
        box = (self.x - tw / 2 - pad - 14, y - self.size * 0.75 * s,
               self.x + tw / 2 + pad, y + self.size * 0.75 * s)
        rounded(d, box, 12, fill=fade(mixc(BG, col, 0.12), a), outline=fade(col, a * 0.8), width=2)
        d.ellipse((box[0] + 12, y - 5, box[0] + 22, y + 5), fill=fade(col, a))
        d.text((self.x + 7, y), text, font=f, fill=fade(col, a), anchor="mm")


class Arrow(El):
    sfx = None

    def __init__(self, t0, p1, p2, color=RED, t1=None, dur=0.6, dashed=True, both=False):
        super().__init__(t0, t1, "fade", dur)
        self.p1, self.p2, self.color, self.dashed, self.both = p1, p2, color, dashed, both

    def paint(self, d, t, cam, a, s, dy):
        prog = ease_out((t - self.t0) / self.dur)
        p1 = (self.p1[0], self.p1[1] - cam)
        p2 = (self.p2[0], self.p2[1] - cam)
        c = fade(self.color, a)
        if self.dashed:
            dashed_line(d, p1, p2, c, 4, 14, 10, prog)
        else:
            d.line((p1, (p1[0] + (p2[0] - p1[0]) * prog, p1[1] + (p2[1] - p1[1]) * prog)),
                   fill=c, width=4)
        if prog > 0.95:
            for (a_, b_) in ([(p1, p2)] + ([(p2, p1)] if self.both else [])):
                ang = math.atan2(b_[1] - a_[1], b_[0] - a_[0])
                for side in (-1, 1):
                    d.line((b_[0], b_[1], b_[0] - 22 * math.cos(ang + side * 0.5),
                            b_[1] - 22 * math.sin(ang + side * 0.5)), fill=c, width=4)


class Terminal(El):
    sfx = "pop"

    def __init__(self, t0, x, y, w, lines, t1=None, type_speed=14, size=46):
        super().__init__(t0, t1, "pop")
        longest = max((len(l) for l in lines), default=1)
        size = min(size, int((w - 90) / (0.61 * longest)))  # shrink long commands to fit
        self.x, self.y, self.w, self.lines, self.speed, self.size = x, y, w, lines, type_speed, size
        self.h = 110 + len(lines) * size * 1.35

    def events(self):
        ev = [(self.t0, "pop")]
        start = self.t0 + 0.4
        for line in self.lines:
            ev += [(start + i / self.speed, "tick") for i in range(0, len(line), 2)]
            start += len(line) / self.speed + 0.2
        return ev

    def paint(self, d, t, cam, a, s, dy):
        cx, cy = self.x + self.w / 2, self.y + self.h / 2 - cam + dy
        w, h = self.w * s, self.h * s
        box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        rounded(d, box, 18, fill=fade((16, 22, 28), a), outline=fade(TEAL_LINE, a), width=3)
        for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            d.ellipse((box[0] + 24 + i * 30, box[1] + 22, box[0] + 42 + i * 30, box[1] + 40),
                      fill=fade(c, a))
        f = font(MONO, self.size * s)
        start = self.t0 + 0.4
        cursor = None
        for li, line in enumerate(self.lines):
            n = int(clamp((t - start) * self.speed / max(len(line), 1)) * len(line))
            ly = box[1] + 80 * s + li * self.size * 1.35 * s
            if n > 0:
                d.text((box[0] + 40 * s, ly), line[:n], font=f, fill=fade(TEAL, a))
            if 0 < n < len(line) or (n == len(line) and li == len(self.lines) - 1):
                cursor = (box[0] + 40 * s + d.textlength(line[:n], font=f) + 4, ly)
            start += len(line) / self.speed + 0.2
        if cursor and int(t * 3) % 2 == 0:
            d.rectangle((cursor[0], cursor[1] + 4, cursor[0] + 20 * s, cursor[1] + self.size * s),
                        fill=fade(TEAL, a))


class Stick(El):
    """Stick-figure narrator. pose: point | think | wave | shrug"""
    sfx = None

    def __init__(self, t0, x, y, pose="point", t1=None, scale=1.0, poses=None):
        super().__init__(t0, t1, "rise")
        self.x, self.y, self.pose, self.sc = x, y, pose, scale
        self.poses = poses or []  # [(time, pose)]

    def paint(self, d, t, cam, a, s, dy):
        pose = self.pose
        for pt, p in self.poses:
            if t >= pt:
                pose = p
        k = self.sc
        x, y = self.x, self.y - cam + dy
        c = fade(WHITE, a)
        wd = int(5 * k)
        hr = 34 * k
        d.ellipse((x - hr, y - hr, x + hr, y + hr), outline=c, width=wd)
        neck, hip = y + hr, y + hr + 150 * k
        d.line((x, neck, x, hip), fill=c, width=wd)
        d.line((x, hip, x - 45 * k, hip + 130 * k), fill=c, width=wd)
        d.line((x, hip, x + 45 * k, hip + 130 * k), fill=c, width=wd)
        sh = neck + 40 * k
        wob = math.sin(t * 6) * 8 * k
        if pose == "point":
            d.line((x, sh, x - 55 * k, sh + 95 * k), fill=c, width=wd)
            d.line((x, sh, x + 70 * k, sh - 20 * k), fill=c, width=wd)
            d.line((x + 70 * k, sh - 20 * k, x + 130 * k, sh - 70 * k + wob), fill=c, width=wd)
        elif pose == "think":
            d.line((x, sh, x - 55 * k, sh + 95 * k), fill=c, width=wd)
            d.line((x, sh, x + 55 * k, sh + 40 * k), fill=c, width=wd)
            d.line((x + 55 * k, sh + 40 * k, x + 22 * k, y + hr * 0.6), fill=c, width=wd)
        elif pose == "wave":
            d.line((x, sh, x - 55 * k, sh + 95 * k), fill=c, width=wd)
            d.line((x, sh, x + 60 * k, sh - 50 * k), fill=c, width=wd)
            d.line((x + 60 * k, sh - 50 * k, x + 70 * k + wob * 2, sh - 130 * k), fill=c, width=wd)
        else:  # shrug
            for side in (-1, 1):
                d.line((x, sh, x + side * 60 * k, sh + 30 * k), fill=c, width=wd)
                d.line((x + side * 60 * k, sh + 30 * k, x + side * 85 * k, sh - 40 * k),
                       fill=c, width=wd)


class Thought(El):
    """Thought bubble (ellipse + two small circles) around a child element area."""
    sfx = "pop"

    def __init__(self, t0, cx, cy, rx, ry, tail, t1=None):
        super().__init__(t0, t1, "pop")
        self.cx, self.cy, self.rx, self.ry, self.tail = cx, cy, rx, ry, tail

    def paint(self, d, t, cam, a, s, dy):
        cy = self.cy - cam + dy
        c = fade(WHITE, a)
        d.ellipse((self.cx - self.rx * s, cy - self.ry * s, self.cx + self.rx * s,
                   cy + self.ry * s), outline=c, width=4)
        for (tx, ty, r) in self.tail:
            d.ellipse((tx - r, ty - cam - r, tx + r, ty - cam + r), outline=c, width=3)


class Hex(El):
    """Our own blue hexagon 'pod' icon (a cube inside a hexagon)."""
    sfx = "pop"

    def __init__(self, t0, x, y, r=50, t1=None, spin=True):
        super().__init__(t0, t1, "pop")
        self.x, self.y, self.r, self.spin = x, y, r, spin

    def paint(self, d, t, cam, a, s, dy):
        r = self.r * s
        x, y = self.x, self.y - cam + dy
        rot = (t - self.t0) * 0.0 if not self.spin else math.sin(t * 1.5) * 0.06
        pts = [(x + r * math.cos(rot + math.pi / 3 * i + math.pi / 6),
                y + r * math.sin(rot + math.pi / 3 * i + math.pi / 6)) for i in range(6)]
        d.polygon(pts, fill=fade(BLUE, a), outline=fade(WHITE, a))
        q = r * 0.42  # isometric cube
        c = fade(WHITE, a)
        top = [(x, y - q), (x + q * 0.87, y - q / 2), (x, y), (x - q * 0.87, y - q / 2)]
        d.polygon(top, outline=c, width=max(2, int(r / 16)))
        d.line((x - q * 0.87, y - q / 2, x - q * 0.87, y + q / 2), fill=c, width=max(2, int(r / 16)))
        d.line((x + q * 0.87, y - q / 2, x + q * 0.87, y + q / 2), fill=c, width=max(2, int(r / 16)))
        d.line((x, y, x, y + q), fill=c, width=max(2, int(r / 16)))
        d.line((x - q * 0.87, y + q / 2, x, y + q), fill=c, width=max(2, int(r / 16)))
        d.line((x + q * 0.87, y + q / 2, x, y + q), fill=c, width=max(2, int(r / 16)))


class Pill(El):
    sfx = "pop"

    def __init__(self, t0, x, y, text, w=560, t1=None, color=WHITE):
        super().__init__(t0, t1, "pop")
        self.x, self.y, self.text, self.w, self.color = x, y, text, w, color

    def paint(self, d, t, cam, a, s, dy):
        y = self.y - cam + dy
        w, h = self.w * s, 84 * s
        rounded(d, (self.x - w / 2, y - h / 2, self.x + w / 2, y + h / 2), h / 2,
                outline=fade(self.color, a), width=3)
        size = 40
        while size > 22 and font(MARKER, size).getlength(self.text) > self.w - 60:
            size -= 2
        d.text((self.x, y), self.text, font=font(MARKER, size * s), fill=fade(self.color, a),
               anchor="mm")


class Strike(El):
    """Line crossing out a text row (for 'you don't do this' lists)."""
    sfx = None

    def __init__(self, t0, x0, x1, y, color=WHITE, dur=0.4):
        super().__init__(t0, None, "fade", dur)
        self.x0, self.x1, self.y, self.color = x0, x1, y, color

    def paint(self, d, t, cam, a, s, dy):
        k = ease_out((t - self.t0) / self.dur)
        d.line((self.x0, self.y - cam, self.x0 + (self.x1 - self.x0) * k, self.y - cam),
               fill=fade(self.color, a), width=4)


# ---------------------------------------------------------------- scenes / timing
class Scene:
    """A beat of the story: its voice line, where it sits on the canvas, its timing."""

    def __init__(self, vo, world_y, hold=0.0):
        self.vo, self.world_y, self.hold = vo, world_y, hold
        self.start = 0.0
        self.dur = 0.0
        self.words = []  # [{word,start,end}] relative to scene start

    def at(self, word, fallback=0.5, nth=1):
        """Time (absolute) when `word` is spoken in this scene's voice line."""
        target = re.sub(r"[^\w]", "", word.lower())
        seen = 0
        for w in self.words:
            if re.sub(r"[^\w]", "", w["word"].lower()) == target:
                seen += 1
                if seen == nth:
                    return self.start + w["start"]
        return self.start + self.dur * fallback

    def frac(self, f):
        return self.start + self.dur * f


def estimate_words(text, seconds):
    words = text.split()
    total = sum(len(w) + 2 for w in words) or 1
    t, out = 0.0, []
    for w in words:
        dd = seconds * (len(w) + 2) / total
        out.append({"word": w, "start": t, "end": t + dd * 0.9})
        t += dd
    return out


VOICE_LEAD = 0.25   # silence before each line
SCENE_TAIL = 0.45   # pause after each line


def time_scenes(scenes, voice_fn=None, out_dir="."):
    """Give every scene a start/duration. voice_fn(text, path) -> (seconds, words).

    Returns a list of (start_time, mp3_path) for the voice clips (empty if no voice)."""
    t, clips = 0.0, []
    for i, sc in enumerate(scenes):
        sc.start = t
        if voice_fn:
            path = os.path.join(out_dir, f"vo_{i}.mp3")
            secs, words = voice_fn(sc.vo, path)
            clips.append((t + VOICE_LEAD, path))
        else:
            secs = len(sc.vo.split()) / 2.7
            words = estimate_words(sc.vo, secs)
        for w in words:
            w["start"] += VOICE_LEAD
            w["end"] += VOICE_LEAD
        sc.words = words
        sc.dur = VOICE_LEAD + secs + SCENE_TAIL + sc.hold
        t += sc.dur
    return clips


def camera(scenes, t, move=0.8):
    """Camera y: glide to each scene's world_y at its start."""
    y = scenes[0].world_y
    for sc in scenes[1:]:
        if t >= sc.start - move * 0.5:
            k = ease_in_out((t - (sc.start - move * 0.5)) / move)
            y = y + (sc.world_y - y) * k
    return y


def render(scenes, elements, out_path, voice_clips=(), day=0, music=True):
    """Draw every frame, mix voice + music + sound effects, encode MP4."""
    import numpy as np
    from audio import SR, mix

    total = scenes[-1].start + scenes[-1].dur + 0.6
    # one voice track from the clips
    voice_wav = None
    if voice_clips:
        n = int(total * SR)
        track = np.zeros(n, dtype=np.float32)
        from audio import _decode
        for start, path in voice_clips:
            v = _decode(path)
            i = int(start * SR)
            track[i:i + len(v)] += v[:max(0, n - i)]
        voice_wav = out_path + ".voice.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR),
                        "-ac", "1", "-i", "-", voice_wav], input=track.tobytes(), check=True)

    events = []
    for e in elements:
        events += e.events()
    for prev, sc in zip(scenes, scenes[1:]):
        if sc.world_y != prev.world_y:
            events.append((sc.start - 0.4, "whoosh"))
    mixed = out_path + ".mix.wav"
    os.environ.setdefault("MUSIC_VOLUME", "0.14" if music else "0")
    os.environ.setdefault("SFX_VOLUME", "0.45")
    mix(voice_wav, events, mixed, total, day, voice_delay=0.0)

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", mixed, "-map", "0:v", "-map",
           "1:a", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", "-c:v", "libx264",
           "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(total * FPS)):
        t = i / FPS
        frame = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(frame)
        cam = camera(scenes, t)
        for e in elements:
            e.draw(d, t, cam)
        d.rectangle((0, H - 10, int(W * t / total), H), fill=TEAL)  # progress bar
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    for p in (mixed, voice_wav):
        if p and os.path.exists(p):
            os.remove(p)
    return out_path
