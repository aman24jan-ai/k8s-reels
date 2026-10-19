"""Render a 15-second 1080x1920 motion-graphics reel with PIL + FFmpeg (no paid tools)."""
import math
import os
import random
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
DURATION = float(os.environ.get("REEL_SECONDS", "15"))
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "assets", "fonts")

BG = (9, 13, 28)
BLUE = (50, 108, 229)
CYAN = (34, 211, 238)
WHITE = (245, 247, 252)
MUTED = (148, 163, 196)
CARD = (20, 28, 52)

# Safe area: keep clear of Reels/Shorts UI (top bar, bottom caption, right buttons)
SAFE_L, SAFE_R, SAFE_T, SAFE_B = 90, 960, 250, 1500


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_out_back(t: float) -> float:
    t = max(0.0, min(1.0, t))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def wrap(text: str, fnt, max_w: int, draw) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_text(text, font_name, start_size, max_w, max_lines, draw):
    size = start_size
    while size > 30:
        fnt = font(font_name, size)
        lines = wrap(text, fnt, max_w, draw)
        if len(lines) <= max_lines and all(draw.textlength(l, font=fnt) <= max_w for l in lines):
            return fnt, lines
        size -= 4
    fnt = font(font_name, 30)
    return fnt, wrap(text, fnt, max_w, draw)[:max_lines]


def text_layer(lines, fnt, color, line_gap=1.12, align="left", width=None):
    """Pre-render text lines to a transparent RGBA image."""
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    asc, desc = fnt.getmetrics()
    lh = int((asc + desc) * line_gap)
    w = width or int(max(tmp.textlength(l, font=fnt) for l in lines)) + 8
    img = Image.new("RGBA", (w, lh * len(lines) + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        x = 0 if align == "left" else (w - d.textlength(l, font=fnt)) / 2
        d.text((x, i * lh), l, font=fnt, fill=color)
    return img


def with_opacity(img: Image.Image, a: float) -> Image.Image:
    if a >= 0.999:
        return img
    out = img.copy()
    alpha = out.getchannel("A").point(lambda v: int(v * max(0.0, a)))
    out.putalpha(alpha)
    return out


def paste(frame, layer, x, y, alpha=1.0):
    if alpha <= 0.01:
        return
    frame.alpha_composite(with_opacity(layer, alpha), (int(x), int(y)))


def hexagon(cx, cy, r, rot=0.0):
    return [(cx + r * math.cos(rot + math.pi / 3 * i + math.pi / 6),
             cy + r * math.sin(rot + math.pi / 3 * i + math.pi / 6)) for i in range(6)]


def build_background() -> Image.Image:
    bg = Image.new("RGBA", (W, H), BG + (255,))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse((-300, -200, 900, 900), fill=BLUE + (90,))
    g.ellipse((400, 1200, 1500, 2300), fill=CYAN + (45,))
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    bg.alpha_composite(glow)
    d = ImageDraw.Draw(bg)
    for x in range(0, W, 90):  # subtle grid
        d.line((x, 0, x, H), fill=(255, 255, 255, 10))
    for y in range(0, H, 90):
        d.line((0, y, W, y), fill=(255, 255, 255, 10))
    return bg


class Reel:
    def __init__(self, script: dict, day: int, handle: str):
        self.s, self.day, self.handle = script, day, handle
        self.bg = build_background()
        rnd = random.Random(day)
        self.hexes = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(30, 110),
                       rnd.uniform(-25, 25), rnd.uniform(-40, -15), rnd.uniform(0, 6))
                      for _ in range(14)]
        d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        maxw = SAFE_R - SAFE_L

        self.pill = self._pill(f"DAY {day}  •  KUBERNETES IN 15s")
        f, l = fit_text(script["hook"].upper(), "InterDisplay-Black.otf", 118, maxw, 4, d)
        self.hook = text_layer(l, f, WHITE, 1.05)
        f, l = fit_text(script["title"], "InterDisplay-Black.otf", 92, maxw - 140, 2, d)
        self.title = text_layer(l, f, WHITE, 1.05)
        self.points = []
        for p in script["points"]:
            f, l = fit_text(p, "Inter-SemiBold.otf", 54, maxw - 150, 2, d)
            self.points.append(text_layer(l, f, WHITE, 1.15))
        self.cmd = None
        if script.get("command"):
            f, l = fit_text("$ " + script["command"], "DejaVuSansMono-Bold.ttf", 40,
                            maxw - 80, 2, d)
            self.cmd = text_layer(l, f, CYAN, 1.2)
        self.cta = text_layer(["Follow for a new", "K8s concept daily"],
                              font("InterDisplay-Black.otf", 84), WHITE, 1.08, "center", maxw)
        self.handle_l = text_layer([handle], font("Inter-Bold.otf", 46), CYAN, 1.0,
                                   "center", maxw) if handle else None
        self.brand = text_layer([handle or "Kubernetes Daily"], font("Inter-Bold.otf", 34),
                                MUTED, 1.0)

    def _pill(self, text):
        f = font("Inter-Bold.otf", 34)
        tw = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(text, font=f)
        img = Image.new("RGBA", (int(tw) + 64, 72), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, img.width - 1, 71), 36, fill=BLUE + (255,))
        d.text((32, 15), text, font=f, fill=WHITE)
        return img

    def _hex_icon(self, frame, cx, cy, r, t, alpha):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.polygon(hexagon(cx, cy, r, t * 0.6), outline=CYAN + (int(255 * alpha),), width=8)
        d.polygon(hexagon(cx, cy, r * 0.58, -t * 0.9), fill=BLUE + (int(255 * alpha),))
        d.ellipse((cx - r * 0.18, cy - r * 0.18, cx + r * 0.18, cy + r * 0.18),
                  fill=WHITE + (int(255 * alpha),))
        frame.alpha_composite(layer)

    def frame(self, t: float) -> Image.Image:
        fr = self.bg.copy()
        d = ImageDraw.Draw(fr)
        # drifting hexagons
        for x, y, r, vx, vy, ph in self.hexes:
            px, py = (x + vx * t) % W, (y + vy * t) % H
            d.polygon(hexagon(px, py, r, ph + t * 0.15), outline=(90, 130, 230, 38), width=3)

        paste(fr, self.brand, SAFE_L, 150, 0.9)

        # Scene 1: hook (0 - 3.2 s)
        if t < 3.4:
            a_in = ease_out(t / 0.5)
            a_out = 1 - ease_out((t - 2.9) / 0.4)
            a = min(a_in, a_out)
            paste(fr, self.pill, SAFE_L, 560 - 40 * (1 - a_in), a)
            k = ease_out((t - 0.2) / 0.6)
            paste(fr, self.hook, SAFE_L, 680 + 120 * (1 - k), min(k, a_out))
            bar_w = int((SAFE_R - SAFE_L) * 0.35 * ease_out((t - 0.6) / 0.6))
            d.rounded_rectangle((SAFE_L, 680 + self.hook.height + 40,
                                 SAFE_L + max(bar_w, 1), 680 + self.hook.height + 56), 8,
                                fill=CYAN + (int(255 * a_out),))

        # Scene 2: title + points + command (3.2 - 12.4 s)
        if 3.0 <= t < 12.8:
            a_out = 1 - ease_out((t - 12.2) / 0.5)
            k = ease_out_back((t - 3.2) / 0.6)
            ia = min(ease_out((t - 3.2) / 0.4), a_out)
            self._hex_icon(fr, SAFE_L + 55, SAFE_T + 85, 55 * max(k, 0.01), t, ia)
            paste(fr, self.title, SAFE_L + 140 + 60 * (1 - ease_out((t - 3.3) / 0.5)),
                  SAFE_T + 85 - self.title.height / 2, min(ease_out((t - 3.3) / 0.5), a_out))
            y = SAFE_T + 260
            for i, pl in enumerate(self.points):
                st = 4.3 + i * 2.2
                kk = ease_out((t - st) / 0.55)
                if kk > 0:
                    a = min(kk, a_out)
                    ch = max(pl.height + 60, 150)
                    xoff = 80 * (1 - kk)
                    card = Image.new("RGBA", (SAFE_R - SAFE_L, ch), (0, 0, 0, 0))
                    cd = ImageDraw.Draw(card)
                    cd.rounded_rectangle((0, 0, card.width - 1, ch - 1), 28,
                                         fill=CARD + (235,), outline=(60, 90, 170, 255), width=2)
                    cd.rounded_rectangle((0, 0, 12, ch - 1), 6, fill=CYAN + (255,))
                    nf = font("InterDisplay-Black.otf", 56)
                    cd.ellipse((38, ch / 2 - 38, 114, ch / 2 + 38), fill=BLUE + (255,))
                    num = str(i + 1)
                    cd.text((76 - cd.textlength(num, font=nf) / 2, ch / 2 - 36), num,
                            font=nf, fill=WHITE)
                    card.alpha_composite(pl, (140, int((ch - pl.height) / 2) + 4))
                    paste(fr, card, SAFE_L + xoff, y, a)
                y += max(pl.height + 60, 150) + 30
            if self.cmd is not None:
                kk = ease_out((t - 10.6) / 0.5)
                if kk > 0:
                    box = Image.new("RGBA", (SAFE_R - SAFE_L, self.cmd.height + 90), (0, 0, 0, 0))
                    bd = ImageDraw.Draw(box)
                    bd.rounded_rectangle((0, 0, box.width - 1, box.height - 1), 22,
                                         fill=(4, 8, 18, 240), outline=(40, 60, 110, 255), width=2)
                    for j, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
                        bd.ellipse((26 + j * 34, 18, 46 + j * 34, 38), fill=c + (255,))
                    # typewriter reveal
                    reveal = ease_out((t - 10.7) / 1.0)
                    crop_w = max(1, int(self.cmd.width * reveal))
                    box.alpha_composite(self.cmd.crop((0, 0, crop_w, self.cmd.height)), (40, 60))
                    paste(fr, box, SAFE_L, max(y, SAFE_B - box.height - 20), min(kk, a_out))

        # Scene 3: call to action (12.4 - 15 s)
        if t >= 12.3:
            k = ease_out_back((t - 12.4) / 0.6)
            a = ease_out((t - 12.4) / 0.4)
            self._hex_icon(fr, W / 2, 700, 110 * max(k, 0.01), t, a)
            paste(fr, self.cta, SAFE_L, 880 + 60 * (1 - ease_out((t - 12.5) / 0.5)), a)
            if self.handle_l is not None:
                paste(fr, self.handle_l, SAFE_L, 880 + self.cta.height + 40,
                      ease_out((t - 12.9) / 0.4))

        # progress bar
        d.rectangle((0, H - 14, int(W * min(t / DURATION, 1)), H), fill=CYAN + (255,))
        return fr


def render(script: dict, audio_path: str | None, out_path: str, day: int = 1,
           handle: str = "") -> str:
    reel = Reel(script, day, handle)
    frames = int(DURATION * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio_path:
        cmd += ["-i", audio_path, "-filter_complex",
                "[1:a]adelay=400|400,apad,aresample=48000[a]", "-map", "0:v", "-map", "[a]",
                "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
    cmd += ["-t", str(DURATION), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(frames):
        proc.stdin.write(reel.frame(i / FPS).convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    return out_path
