"""Render a 15-second 1080x1920 motion-graphics reel with PIL + FFmpeg (no paid tools).

Timeline (seconds):
  0.0 - 2.2   hook: flash + slam-in text (scroll stopper)
  2.2 - 4.6   title + real-world analogy
  4.6 - 12.4  one idea per screen: point 1, 2, 3, then the kubectl command
  12.4 - 15   comment question + follow CTA
Word-by-word captions synced to the voice run along the bottom the whole time.
"""
import math
import os
import random
import re
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
DURATION = float(os.environ.get("REEL_SECONDS", "15"))
VOICE_DELAY = 0.35
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "assets", "fonts")

BG = (9, 13, 28)
BLUE = (50, 108, 229)
CYAN = (34, 211, 238)
YELLOW = (250, 204, 21)
WHITE = (245, 247, 252)
MUTED = (148, 163, 196)
CARD = (20, 28, 52)

# Safe area: keep clear of Reels/Shorts UI (top bar, bottom caption, right buttons)
SAFE_L, SAFE_R, SAFE_T, SAFE_B = 90, 960, 250, 1500
MAXW = SAFE_R - SAFE_L
CAPTION_Y = 1330  # centre line of the captions

T_HOOK, T_TITLE, T_POINTS, T_CTA = 0.0, 2.2, 4.6, 12.4
POINT_LEN = 2.0


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def clamp(t):
    return max(0.0, min(1.0, t))


def ease_out(t: float) -> float:
    return 1 - (1 - clamp(t)) ** 3


def ease_out_back(t: float) -> float:
    t = clamp(t)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


_MEASURE = ImageDraw.Draw(Image.new("RGBA", (1, 1)))


def wrap(text: str, fnt, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if _MEASURE.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_text(text, font_name, start_size, max_w, max_lines):
    size = start_size
    while size > 30:
        fnt = font(font_name, size)
        lines = wrap(text, fnt, max_w)
        if len(lines) <= max_lines and all(_MEASURE.textlength(l, font=fnt) <= max_w
                                           for l in lines):
            return fnt, lines
        size -= 4
    fnt = font(font_name, 30)
    return fnt, wrap(text, fnt, max_w)[:max_lines]


def text_layer(lines, fnt, color, line_gap=1.12, align="left", width=None,
               stroke=0, stroke_fill=(0, 0, 0), highlight=None):
    """Pre-render text lines to a transparent RGBA image.

    highlight: set of lowercase words drawn in YELLOW (keyword emphasis).
    """
    asc, desc = fnt.getmetrics()
    lh = int((asc + desc) * line_gap)
    w = width or int(max(_MEASURE.textlength(l, font=fnt) for l in lines)) + 8 + stroke * 2
    img = Image.new("RGBA", (w, lh * len(lines) + 8 + stroke * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    space = _MEASURE.textlength(" ", font=fnt)
    for i, l in enumerate(lines):
        lw = d.textlength(l, font=fnt)
        x = stroke if align == "left" else (w - lw) / 2
        y = i * lh + stroke
        if not highlight:
            d.text((x, y), l, font=fnt, fill=color, stroke_width=stroke, stroke_fill=stroke_fill)
            continue
        for word in l.split(" "):
            key = re.sub(r"[^\w-]", "", word).lower()
            c = YELLOW if key in highlight else color
            d.text((x, y), word, font=fnt, fill=c, stroke_width=stroke, stroke_fill=stroke_fill)
            x += d.textlength(word, font=fnt) + space
    return img


def with_opacity(img: Image.Image, a: float) -> Image.Image:
    if a >= 0.999:
        return img
    out = img.copy()
    out.putalpha(out.getchannel("A").point(lambda v: int(v * max(0.0, a))))
    return out


def scaled(img: Image.Image, s: float) -> Image.Image:
    if abs(s - 1) < 0.01:
        return img
    return img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))),
                      Image.BILINEAR)


def paste(frame, layer, x, y, alpha=1.0):
    if alpha <= 0.01:
        return
    frame.alpha_composite(with_opacity(layer, alpha), (int(x), int(y)))


def paste_center(frame, layer, cx, cy, alpha=1.0, scale=1.0):
    if alpha <= 0.01:
        return
    l = scaled(layer, scale)
    paste(frame, l, cx - l.width / 2, cy - l.height / 2, alpha)


def hexagon(cx, cy, r, rot=0.0):
    return [(cx + r * math.cos(rot + math.pi / 3 * i + math.pi / 6),
             cy + r * math.sin(rot + math.pi / 3 * i + math.pi / 6)) for i in range(6)]


def build_background() -> Image.Image:
    bg = Image.new("RGBA", (W, H + 90), BG + (255,))
    glow = Image.new("RGBA", (W, H + 90), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse((-300, -200, 900, 900), fill=BLUE + (90,))
    g.ellipse((400, 1200, 1500, 2300), fill=CYAN + (45,))
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    bg.alpha_composite(glow)
    d = ImageDraw.Draw(bg)
    for x in range(0, W, 90):
        d.line((x, 0, x, H + 90), fill=(255, 255, 255, 10))
    for y in range(0, H + 90, 90):
        d.line((0, y, W, y), fill=(255, 255, 255, 10))
    return bg


def has_devanagari(text: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in text)


def estimate_words(text: str, voice_seconds: float) -> list[dict]:
    """Fallback word timings spread by word length (used if TTS gave none)."""
    words = text.split()
    total = sum(len(w) + 2 for w in words) or 1
    t, out = 0.0, []
    for w in words:
        d = voice_seconds * (len(w) + 2) / total
        out.append({"word": w, "start": t, "end": t + d * 0.9})
        t += d
    return out


def chunk_words(words: list[dict], max_words=3, max_chars=18) -> list[list[dict]]:
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or
                    len(" ".join(x["word"] for x in cur + [w])) > max_chars or
                    re.search(r"[.,!?;:]$", cur[-1]["word"])):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


class Reel:
    def __init__(self, script: dict, day: int, handle: str, words: list[dict] | None,
                 voice_seconds: float = 12.0):
        self.s, self.day, self.handle = script, day, handle
        self.bg = build_background()
        rnd = random.Random(day)
        self.hexes = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(30, 110),
                       rnd.uniform(-25, 25), rnd.uniform(-40, -15), rnd.uniform(0, 6))
                      for _ in range(14)]
        keywords = {k.lower() for k in script.get("keywords", [])}
        self.keywords = keywords

        # hook
        self.pill = self._pill(f"DAY {day}  •  KUBERNETES IN 15s")
        f, l = fit_text(script["hook"].upper(), "InterDisplay-Black.otf", 124, MAXW, 4)
        self.hook = text_layer(l, f, WHITE, 1.05, "center", MAXW, highlight=keywords)

        # header (title)
        f, l = fit_text(script["title"], "InterDisplay-Black.otf", 68, MAXW - 130, 1)
        self.title = text_layer(l, f, WHITE, 1.05)

        # big title + analogy
        f, l = fit_text(script["title"], "InterDisplay-Black.otf", 110, MAXW, 3)
        self.big_title = text_layer(l, f, WHITE, 1.05, "center", MAXW, highlight=keywords)
        self.analogy = None
        if script.get("analogy"):
            f, l = fit_text(script["analogy"], "Inter-Bold.otf", 58, MAXW - 120, 3)
            self.analogy = self._card(
                text_layer(l, f, WHITE, 1.18, "center", MAXW - 120, highlight=keywords),
                "THINK OF IT LIKE", YELLOW)

        # one card per point
        self.point_cards = []
        n = len(script["points"])
        for i, p in enumerate(script["points"]):
            f, l = fit_text(p, "InterDisplay-Black.otf", 84, MAXW - 120, 3)
            self.point_cards.append(self._card(
                text_layer(l, f, WHITE, 1.1, "center", MAXW - 120, highlight=keywords),
                f"{i + 1} / {n}", CYAN))

        self.cmd = None
        if script.get("command"):
            f, l = fit_text("$ " + script["command"], "DejaVuSansMono-Bold.ttf", 50, MAXW - 90, 1)
            self.cmd = text_layer(l, f, CYAN, 1.25)
            self.cmd_label = text_layer(["TRY IT"], font("Inter-Bold.otf", 36), YELLOW)

        # CTA
        q = script.get("question") or "Did you know this?"
        f, l = fit_text(q, "InterDisplay-Black.otf", 92, MAXW, 3)
        self.question = text_layer(l, f, WHITE, 1.06, "center", MAXW, highlight=keywords)
        self.comment = self._pill("COMMENT YOUR ANSWER", YELLOW, BG)
        self.follow = text_layer(["Follow for a new K8s concept daily"],
                                 font("Inter-Bold.otf", 44), CYAN, 1.0, "center", MAXW)
        self.brand = text_layer([handle or "Kubernetes Daily"], font("Inter-Bold.otf", 34),
                                MUTED, 1.0)

        # timeline of the middle section
        self.scenes = []  # (start, end, kind, index)
        t = T_POINTS
        for i in range(len(self.point_cards)):
            self.scenes.append((t, t + POINT_LEN, "point", i))
            t += POINT_LEN
        if self.cmd is not None:
            self.scenes.append((t, T_CTA, "cmd", 0))
        elif self.scenes:
            s0, _, k, i = self.scenes[-1]
            self.scenes[-1] = (s0, T_CTA, k, i)

        # captions
        self.captions = []
        self.cap_cache = {}
        vo = script.get("voiceover", "")
        if os.environ.get("CAPTIONS", "true").lower() != "false" and not has_devanagari(vo):
            words = words or estimate_words(vo, voice_seconds)
            for w in words:
                w["start"] += VOICE_DELAY
                w["end"] += VOICE_DELAY
            self.captions = chunk_words(words)
            self.cap_font = font("InterDisplay-Black.otf", 78)

    # ---------- building blocks ----------
    def _pill(self, text, bg=BLUE, fg=WHITE):
        f = font("Inter-Bold.otf", 34)
        tw = _MEASURE.textlength(text, font=f)
        img = Image.new("RGBA", (int(tw) + 64, 72), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, img.width - 1, 71), 36, fill=bg + (255,))
        d.text((32, 15), text, font=f, fill=fg)
        return img

    def _card(self, body: Image.Image, label: str, accent):
        lab = font("Inter-Bold.otf", 34)
        h = body.height + 150
        card = Image.new("RGBA", (MAXW, h), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, MAXW - 1, h - 1), 36, fill=CARD + (240,),
                             outline=accent + (255,), width=4)
        lw = cd.textlength(label, font=lab)
        cd.rounded_rectangle(((MAXW - lw) / 2 - 24, 28, (MAXW + lw) / 2 + 24, 82), 27,
                             fill=accent + (255,))
        cd.text(((MAXW - lw) / 2, 36), label, font=lab, fill=BG)
        card.alpha_composite(body, (int((MAXW - body.width) / 2), 112))
        return card

    def _hex_icon(self, frame, cx, cy, r, t, alpha):
        if alpha <= 0.01 or r <= 1:
            return
        layer = Image.new("RGBA", (int(r * 2.4), int(r * 2.4)), (0, 0, 0, 0))
        c = r * 1.2
        d = ImageDraw.Draw(layer)
        d.polygon(hexagon(c, c, r, t * 0.6), outline=CYAN + (255,), width=max(2, int(r / 7)))
        d.polygon(hexagon(c, c, r * 0.58, -t * 0.9), fill=BLUE + (255,))
        d.ellipse((c - r * 0.18, c - r * 0.18, c + r * 0.18, c + r * 0.18), fill=WHITE + (255,))
        paste(frame, layer, cx - c, cy - c, alpha)

    def _caption_layer(self, ci: int, wi: int):
        key = (ci, wi)
        if key not in self.cap_cache:
            chunk = self.captions[ci]
            f = self.cap_font
            words = [w["word"].upper() for w in chunk]
            space = _MEASURE.textlength(" ", font=f)
            widths = [_MEASURE.textlength(w, font=f) for w in words]
            total = sum(widths) + space * (len(words) - 1)
            if total > MAXW:  # shrink very long chunks
                f = font("InterDisplay-Black.otf", int(78 * MAXW / total))
                widths = [_MEASURE.textlength(w, font=f) for w in words]
                space = _MEASURE.textlength(" ", font=f)
                total = sum(widths) + space * (len(words) - 1)
            asc, desc = f.getmetrics()
            img = Image.new("RGBA", (int(total) + 60, asc + desc + 40), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            x = 30
            for j, w in enumerate(words):
                if j == wi:
                    d.rounded_rectangle((x - 14, 10, x + widths[j] + 14, asc + desc + 26), 18,
                                        fill=BLUE + (255,))
                kw = re.sub(r"[^\w-]", "", w).lower()
                color = WHITE if j == wi else (YELLOW if kw in self.keywords else WHITE)
                d.text((x, 16), w, font=f, fill=color, stroke_width=0 if j == wi else 6,
                       stroke_fill=(0, 0, 0))
                x += widths[j] + space
            self.cap_cache[key] = img
        return self.cap_cache[key]

    def events(self) -> list[tuple[float, str]]:
        """Sound effects synced to the animation."""
        ev = [(0.0, "boom"), (T_TITLE - 0.15, "whoosh"), (T_TITLE + 0.9, "pop")]
        for s, _, kind, _ in self.scenes:
            ev.append((s - 0.1, "whoosh"))
            ev.append((s + 0.15, "pop"))
            if kind == "cmd":
                n = len(self.s.get("command", ""))
                ev += [(s + 0.4 + 0.9 * k / max(n, 1), "tick") for k in range(0, n, 2)]
        ev += [(T_CTA - 0.1, "whoosh"), (T_CTA + 0.2, "ding")]
        return ev

    # ---------- frames ----------
    def frame(self, t: float) -> Image.Image:
        off = int((t * 24) % 90)
        fr = self.bg.crop((0, off, W, off + H))
        d = ImageDraw.Draw(fr)
        for x, y, r, vx, vy, ph in self.hexes:
            px, py = (x + vx * t) % W, (y + vy * t) % H
            d.polygon(hexagon(px, py, r, ph + t * 0.15), outline=(90, 130, 230, 38), width=3)
        paste(fr, self.brand, SAFE_L, 150, 0.9)

        # 1) HOOK: white flash + slam in with shake
        if t < T_TITLE + 0.3:
            out = 1 - ease_out((t - (T_TITLE - 0.25)) / 0.3)
            k = ease_out_back(t / 0.35)
            shake = 14 * math.sin(t * 90) * max(0, 1 - t / 0.4)
            hook_y = 860
            paste_center(fr, self.pill, W / 2, hook_y - self.hook.height / 2 - 70,
                         min(ease_out(t / 0.3), out))
            paste_center(fr, self.hook, W / 2 + shake, hook_y, min(clamp(t / 0.12), out),
                         1.35 - 0.35 * k)
            if t < 0.12:
                fr.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255,
                                                               int(255 * (1 - t / 0.12)))))

        # 2) TITLE + ANALOGY
        if T_TITLE - 0.05 <= t < T_POINTS + 0.3:
            out = 1 - ease_out((t - (T_POINTS - 0.25)) / 0.3)
            k = ease_out_back((t - T_TITLE) / 0.45)
            paste_center(fr, self.big_title, W / 2, 560, min(clamp((t - T_TITLE) / 0.15), out),
                         0.7 + 0.3 * k)
            if self.analogy is not None:
                k2 = ease_out_back((t - T_TITLE - 0.8) / 0.5)
                paste_center(fr, self.analogy, W / 2, 920 + 80 * (1 - k2),
                             min(clamp((t - T_TITLE - 0.8) / 0.2), out))

        # header during the middle section
        if T_POINTS - 0.1 <= t < T_CTA + 0.3:
            out = 1 - ease_out((t - (T_CTA - 0.2)) / 0.3)
            a = min(ease_out((t - T_POINTS) / 0.4), out)
            self._hex_icon(fr, SAFE_L + 50, SAFE_T + 80, 46, t, a)
            paste(fr, self.title, SAFE_L + 125, SAFE_T + 80 - self.title.height / 2, a)
            # progress dots
            n = len(self.scenes)
            for j, (s, e, _, _) in enumerate(self.scenes):
                active = s <= t < e
                cx = W / 2 + (j - (n - 1) / 2) * 46
                r = 11 if active else 8
                col = CYAN if t >= s else (60, 80, 130)
                d.ellipse((cx - r, SAFE_T + 175 - r, cx + r, SAFE_T + 175 + r),
                          fill=col + (int(255 * a),))

        # 3) ONE IDEA PER SCREEN
        for s, e, kind, i in self.scenes:
            if not (s - 0.05 <= t < e + 0.25):
                continue
            k = ease_out_back((t - s) / 0.4)
            a_in = clamp((t - s) / 0.15)
            a_out = 1 - ease_out((t - (e - 0.15)) / 0.25)
            slide = -140 * ease_out((t - (e - 0.15)) / 0.25)
            a = min(a_in, a_out)
            if kind == "point":
                paste_center(fr, self.point_cards[i], W / 2 + slide, 760, a, 0.6 + 0.4 * k)
            else:
                box = Image.new("RGBA", (MAXW, self.cmd.height + 150), (0, 0, 0, 0))
                bd = ImageDraw.Draw(box)
                bd.rounded_rectangle((0, 0, box.width - 1, box.height - 1), 28,
                                     fill=(4, 8, 18, 245), outline=(40, 60, 110, 255), width=3)
                for j, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
                    bd.ellipse((30 + j * 38, 26, 54 + j * 38, 50), fill=c + (255,))
                box.alpha_composite(self.cmd_label, (MAXW - self.cmd_label.width - 30, 18))
                reveal = clamp((t - s - 0.4) / 0.9)
                crop_w = max(1, int(self.cmd.width * reveal))
                box.alpha_composite(self.cmd.crop((0, 0, crop_w, self.cmd.height)), (44, 90))
                if reveal < 1 or int(t * 3) % 2 == 0:  # blinking cursor
                    cx = 44 + crop_w + 4
                    bd.rectangle((cx, 96, cx + 22, 96 + self.cmd.height * 0.7 / 1.25),
                                 fill=CYAN + (220,))
                paste_center(fr, box, W / 2 + slide, 760, a, 0.7 + 0.3 * k)

        # 4) CTA
        if t >= T_CTA:
            k = ease_out_back((t - T_CTA) / 0.5)
            a = clamp((t - T_CTA) / 0.2)
            self._hex_icon(fr, W / 2, 560, 90 * k, t, a)
            paste_center(fr, self.question, W / 2, 800, a, 0.7 + 0.3 * k)
            k2 = ease_out_back((t - T_CTA - 0.5) / 0.4)
            pulse = 1 + 0.04 * math.sin((t - T_CTA) * 8) if t > T_CTA + 0.9 else 1
            paste_center(fr, self.comment, W / 2, 800 + self.question.height / 2 + 90,
                         clamp((t - T_CTA - 0.5) / 0.2), max(0.01, k2) * pulse)
            paste_center(fr, self.follow, W / 2, 800 + self.question.height / 2 + 190,
                         clamp((t - T_CTA - 0.9) / 0.3))

        # captions (karaoke style)
        if self.captions and t < T_CTA:
            for ci, chunk in enumerate(self.captions):
                nxt = self.captions[ci + 1][0]["start"] if ci + 1 < len(self.captions) \
                    else chunk[-1]["end"] + 0.3
                if chunk[0]["start"] <= t < nxt:
                    wi = 0
                    for j, w in enumerate(chunk):
                        if t >= w["start"]:
                            wi = j
                    pop = 1 + 0.08 * (1 - ease_out((t - chunk[0]["start"]) / 0.15))
                    paste_center(fr, self._caption_layer(ci, wi), W / 2, CAPTION_Y, 1, pop)
                    break

        # progress bar
        d.rectangle((0, H - 14, int(W * min(t / DURATION, 1)), H), fill=CYAN + (255,))
        return fr


def render(script: dict, audio_path: str | None, out_path: str, day: int = 1,
           handle: str = "", words: list[dict] | None = None,
           voice_seconds: float = 12.0) -> str:
    from audio import mix

    reel = Reel(script, day, handle, words, voice_seconds)
    mixed = out_path + ".mix.wav"
    mix(audio_path, reel.events(), mixed, DURATION, day, VOICE_DELAY)

    frames = int(DURATION * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", mixed, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k",
           "-ar", "48000", "-t", str(DURATION), "-c:v", "libx264", "-preset", "medium",
           "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(frames):
        proc.stdin.write(reel.frame(i / FPS).convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    os.remove(mixed)
    return out_path
