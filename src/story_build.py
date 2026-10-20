"""Turn a JSON story plan into a whiteboard video.

A plan looks like examples/pod.json:
  {"title", "caption", "hashtags", "keywords",
   "scenes": [{"type": "hook_title", "vo": "...", ...fields...}, ...]}

Gemini (story_gen.py) only chooses scene types and fills in short text + cue words.
All positions come from the fixed templates below, so every video stays inside the
safe area (x 90-990, y 250-1450 of each 1920 px screen).

CLI (silent, estimated timing - for checking layouts):
  NO_VOICE=1 python src/story_build.py examples/pod.json out.mp4 [--sheet out.png]
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from whiteboard import (AppCard, Arrow, Badge, Box, Containers, Hex, Pill, Scene,  # noqa: E402
                        Stick, Strike, Terminal, Text, Thought, GREY, HAND, MARKER, MONO,
                        ORANGE, TEAL, WHITE, font, render, time_scenes)

SCENE_GAP = 1600
SAFE_W = 900  # usable width (x 90..990)
HOLD = {"hook_title": 0.3, "analogy": 0.4, "inside_box": 0.5, "node_rows": 0.7, "flow": 0.8,
        "scale": 1.3, "trick": 1.5, "recap": 1.2}
TEMPLATES = {}


def template(name):
    def deco(fn):
        TEMPLATES[name] = fn
        return fn
    return deco


def fit(text, fnt, size, max_w, min_size=24):
    """Largest font size <= size that fits text in max_w."""
    while size > min_size and font(fnt, size).getlength(text) > max_w:
        size -= 2
    return size


def cue(sc, p, key, fallback):
    w = p.get(key)
    return sc.at(w, fallback) if w else sc.frac(fallback)


def heading(sc, y, text, color=ORANGE, size=84, t=None):
    return Text(sc.start + 0.1 if t is None else t, 540, y + 330, text,
                fit(text, MARKER, size, SAFE_W), color)


def note(sc, p, y, yy=1390, key="note", cue_key="note_cue", fallback=0.85, color=WHITE,
         fnt=HAND, size=50):
    if not p.get(key):
        return []
    return [Text(cue(sc, p, cue_key, fallback), 540, y + yy, p[key],
                 fit(p[key], fnt, size, SAFE_W), color, fnt)]


# ------------------------------------------------------------------ templates
@template("hook_title")
def t_hook_title(sc, p, y):
    """Big title + icon + stick figure + a card that may get wrapped / joined."""
    title = p.get("heading", "")
    size = fit(title, MARKER, 120, 740)
    tw = font(MARKER, size).getlength(title)
    hex_x = min(90 + tw + 70, 930)
    two = bool(p.get("card2"))
    t_two = cue(sc, p, "card2_cue", 0.65)
    els = [
        Text(sc.start + 0.05, 90, y + 330, title, size, WHITE, anchor="lm", sfx="boom"),
        Hex(sc.start + 0.4, hex_x, y + 335, 52),
        Stick(sc.start + 0.2, 230, y + 860, "think", scale=1.1,
              poses=[(cue(sc, p, "point_cue", 0.3), "point")]),
    ]
    if p.get("wrap_label"):  # drawn first so it sits behind the cards
        els.append(Box(cue(sc, p, "wrap_cue", 0.4), 430, y + 600, 560, 420, "dashed",
                       label=p["wrap_label"], label_size=fit(p["wrap_label"], MARKER, 56, 540)))
    els.append(AppCard(cue(sc, p, "card_cue", 0.2), 460 if two else 590, y + 650, 240, 300,
                       p.get("card", "YOUR APP"),
                       slide_from=(590, y + 650) if two else None,
                       slide_t=t_two if two else None))
    if p.get("card_label"):
        ly = y + 1065 if p.get("wrap_label") else y + 1000
        els.append(Text(cue(sc, p, "card_cue", 0.2) + 0.3, 710, ly, p["card_label"],
                        fit(p["card_label"], HAND, 44, 520), TEAL, HAND,
                        t1=t_two - 0.2 if two else None))
    if two:
        els.append(AppCard(t_two, 730, y + 650, 240, 300, p["card2"],
                           slide_from=(1150, y + 650), slide_t=t_two))
        if p.get("group_label"):
            els.append(Text(t_two + 0.6, 710, y + 1060, p["group_label"],
                            fit(p["group_label"], HAND, 44, 540), TEAL, HAND))
    els += note(sc, p, y, 1340, "tagline", "tagline_cue", 0.85, ORANGE, MARKER, 50)
    return els


@template("analogy")
def t_analogy(sc, p, y):
    """A thought bubble holding 1-2 cards + the real-world comparison line."""
    cards = (p.get("cards") or ["APP"])[:2]
    els = [heading(sc, y, p.get("heading", "THINK OF IT LIKE")),
           Stick(sc.start + 0.2, 170, y + 1020, "think", scale=0.85),
           Thought(sc.start + 0.4, 600, y + 700, 360, 270,
                   [(300, y + 935, 16), (255, y + 975, 11)])]
    xs = [480] if len(cards) == 1 else [350, 610]
    for i, (c, x) in enumerate(zip(cards, xs)):
        els.append(AppCard(sc.start + 0.7 + i * 0.3, x, y + 570, 240, 260, c))
    els += note(sc, p, y, 1400, "line", "cue", 0.6, WHITE, HAND, 54)
    return els


@template("inside_box")
def t_inside_box(sc, p, y):
    """Dashed box with 2-3 cards, a badge on its edge, a link and a shared bar."""
    cards = (p.get("cards") or ["APP", "SIDECAR"])[:3]
    els = [heading(sc, y, p.get("heading", ""), TEAL, 66),
           Box(sc.start + 0.2, 110, y + 470, 860, 720, "dashed", sfx=None)]
    if len(cards) == 3:
        xs, w = [170, 425, 680], 230
    elif len(cards) == 2:
        xs, w = [170, 610], 300
    else:
        xs, w = [390], 300
    for i, (c, x) in enumerate(zip(cards, xs)):
        els.append(AppCard(sc.start + 0.35 + i * 0.2, x, y + 560, w, 300, c))
    if p.get("badge"):
        els.append(Badge(cue(sc, p, "badge_cue", 0.35), 540, y + 470, p["badge"], "orange",
                         size=38))
    if p.get("link_label") and len(cards) >= 2:
        x1, x2 = xs[0] + w + 10, xs[1] - 10
        t = cue(sc, p, "link_cue", 0.65)
        els += [Arrow(t, (x1, y + 720), (x2, y + 720), TEAL, both=True),
                Text(t, (x1 + x2) / 2, y + 660, p["link_label"],
                     fit(p["link_label"], HAND, 34, max(120, x2 - x1 + 40)), TEAL, HAND)]
    if p.get("shared"):
        t = cue(sc, p, "shared_cue", 0.5)
        for i, x in enumerate(xs):
            els.append(Arrow(t + i * 0.12, (x + w / 2, y + 870), (x + w / 2, y + 975), TEAL))
        els += [Box(t + 0.2, 170, y + 985, 740, 110, "teal", sfx=None),
                Text(t + 0.3, 540, y + 1040, p["shared"], fit(p["shared"], MARKER, 44, 700),
                     TEAL)]
    els += note(sc, p, y, 1330)
    return els


@template("node_rows")
def t_node_rows(sc, p, y):
    """A node/cluster box with rows of containers; one row can fail and be replaced."""
    rows = max(2, min(3, int(p.get("rows", 3))))
    fail = p.get("fail_row")
    status = p.get("row_status", "RUNNING")
    els = [heading(sc, y, p.get("heading", ""), ORANGE, 66, t=cue(sc, p, "heading_cue", 0.05)),
           Box(sc.start + 0.3, 90, y + 480, 900, rows * 240 + 80, "teal",
               label=p.get("box_label", "NODE"), sfx=None)]
    crash = cue(sc, p, "fail_cue", 0.3)
    gone = crash + 0.9
    new = max(gone + 0.4, cue(sc, p, "replace_cue", 0.75))
    for i in range(rows):
        ry = y + 530 + i * 240
        t0 = sc.start + 0.5 + i * 0.2
        if fail is not None and int(fail) == i:
            els += [
                Box(t0, 130, ry, 820, 200, "dashed", crash_t=crash, t1=gone, sfx=None),
                Containers(t0 + 0.1, 175, ry + 75, 4, crash_t=crash, t1=gone),
                Badge(t0 + 0.3, 790, ry + 100, status, "teal", t1=gone, switch_t=crash,
                      new_text=p.get("fail_status", "CRASHED"), new_style="red"),
            ]
            if p.get("replace_status"):
                els += [Box(new, 130, ry, 820, 200, "dashed", sfx=None),
                        Containers(new + 0.1, 175, ry + 75, 4),
                        Badge(new + 0.3, 790, ry + 100, p["replace_status"], "orange")]
        else:
            els += [Box(t0, 130, ry, 820, 200, "dashed", sfx=None),
                    Containers(t0 + 0.1, 175, ry + 75, 4),
                    Badge(t0 + 0.3, 790, ry + 100, status, "teal")]
    els += note(sc, p, y, 480 + rows * 240 + 80 + 110, color=ORANGE)
    return els


@template("flow")
def t_flow(sc, p, y):
    """2-4 labelled boxes top-to-bottom joined by dashed arrows (request paths etc.)."""
    steps = (p.get("steps") or [])[:4]
    n = max(1, len(steps))
    els = [heading(sc, y, p.get("heading", ""), TEAL, 66)]
    top, box_h, gap = y + 470, 130, 100 if n == 4 else 130
    for i, st in enumerate(steps):
        label = st.get("label", "") if isinstance(st, dict) else str(st)
        t = sc.at(st["cue"], 0.15 + 0.7 * i / n) if isinstance(st, dict) and st.get("cue") \
            else sc.frac(0.15 + 0.7 * i / n)
        by = top + i * (box_h + gap)
        style = "red" if isinstance(st, dict) and st.get("red") else "teal"
        if i:
            els.append(Arrow(t - 0.35, (540, by - gap + 10), (540, by - 12),
                             TEAL if style == "teal" else ORANGE))
        els += [Box(t, 280, by, 520, box_h, style, sfx="pop"),
                Text(t + 0.05, 540, by + box_h / 2, label, fit(label, MARKER, 48, 470),
                     TEAL if style == "teal" else ORANGE)]
        if isinstance(st, dict) and st.get("side"):
            els.append(Text(t + 0.3, 900, by + box_h / 2, st["side"],
                            fit(st["side"], HAND, 36, 170), GREY, HAND))
    els += note(sc, p, y, 1400)
    return els


@template("scale")
def t_scale(sc, p, y):
    """A box of pods that grows from `from` to `to` on a cue word (scaling)."""
    a = max(1, min(8, int(p.get("from", 2))))
    b = max(a, min(8, int(p.get("to", 6))))
    rows = 1 if b <= 4 else 2
    els = [heading(sc, y, p.get("heading", ""), ORANGE, 70),
           Box(sc.start + 0.3, 90, y + 480, 900, rows * 190 + 90, "teal",
               label=p.get("box_label", "DEPLOYMENT"), sfx=None)]
    grow = cue(sc, p, "cue", 0.5)
    for i in range(b):
        r, c = divmod(i, 4)
        px, py = 130 + c * 205, y + 530 + r * 190
        t0 = sc.start + 0.5 + i * 0.15 if i < a else grow + (i - a) * 0.2
        els += [Box(t0, px, py, 180, 150, "dashed", sfx=None),
                Containers(t0 + 0.05, px + 40, py + 50, 2, size=44)]
    if p.get("status"):
        els.append(Text(grow + (b - a) * 0.2 + 0.4, 540, y + 480 + rows * 190 + 90 + 90,
                        p["status"], fit(p["status"], MONO, 48, SAFE_W), TEAL, MONO,
                        sfx="ding"))
    els += note(sc, p, y, 1400)
    return els


@template("trick")
def t_trick(sc, p, y):
    """Orange question, struck 'old way', a terminal, and the result it produces."""
    lines = [str(x) for x in (p.get("terminal") or [])][:3]
    els = [Text(sc.start + 0.1, 540, y + 320, p.get("heading", "THE TRICK?"),
                fit(p.get("heading", "THE TRICK?"), MARKER, 96, SAFE_W), ORANGE)]
    top = y + 430
    if p.get("strike"):
        size = fit(p["strike"], HAND, 50, 800)
        sw = font(HAND, size).getlength(p["strike"])
        els += [Text(sc.start + 0.5, 540, y + 470, p["strike"], size, GREY, HAND),
                Strike(cue(sc, p, "strike_cue", 0.3), 540 - sw / 2 - 10, 540 + sw / 2 + 10,
                       y + 474)]
        top = y + 560
    term_t = cue(sc, p, "terminal_cue", 0.45) - 0.4
    term = Terminal(term_t, 140, top, 800, lines or ["kubectl get pods"], size=44)
    els.append(term)
    bottom = top + term.h
    n = max(0, min(6, int(p.get("result_count", 0))))
    t_res = max(term_t + 0.4 + sum(len(l) for l in lines) / 14 + 0.3,
                cue(sc, p, "result_cue", 0.75))
    if n:
        els.append(Arrow(t_res, (540, bottom + 30), (540, bottom + 130)))
        for i in range(n):
            r, c = divmod(i, 3)
            px, py = 110 + c * 290, bottom + 160 + r * 190
            t0 = t_res + 0.35 + i * 0.22
            els += [Box(t0, px, py, 280, 160, "dashed"),
                    Containers(t0 + 0.1, px + 70, py + 52, 2, size=56)]
        res_bottom = bottom + 160 + ((n - 1) // 3 + 1) * 190
    else:
        res_bottom = bottom + 40
    if p.get("status"):
        typed = term_t + 0.4 + sum(len(l) for l in lines) / 14 + 0.2 * len(lines)
        t_status = t_res + 0.35 + n * 0.22 + 0.4 if n else typed + 0.3
        els.append(Text(t_status, 540, res_bottom + 50, p["status"],
                        fit(p["status"], MONO, 48, SAFE_W), TEAL, MONO, sfx="ding"))
    return els


@template("recap")
def t_recap(sc, p, y):
    pills = (p.get("pills") or [])[:3]
    els = [Text(sc.start + 0.1, 540, y + 360, p.get("heading", ""),
                fit(p.get("heading", ""), MARKER, 130, SAFE_W), WHITE),
           Hex(sc.start + 0.4, 540, y + 560, 80)]
    for i, pl in enumerate(pills):
        text = pl.get("text", "") if isinstance(pl, dict) else str(pl)
        t = sc.at(pl["cue"], 0.3 + 0.15 * i) if isinstance(pl, dict) and pl.get("cue") \
            else sc.frac(0.3 + 0.15 * i)
        els.append(Pill(t, 540, y + 760 + i * 120, text, w=640))
    els.append(Text(cue(sc, p, "follow_cue", 0.8), 540, y + 1170,
                    p.get("follow", "follow for daily K8s"), 48, TEAL, HAND, sfx="ding"))
    return els


# ------------------------------------------------------------------ build + render
def make_scenes(plan):
    return [Scene(s["vo"], i * SCENE_GAP, HOLD.get(s["type"], 0.5) + float(s.get("hold", 0)))
            for i, s in enumerate(plan["scenes"])]


def build_elements(plan, scenes):
    els = []
    for sc, p in zip(scenes, plan["scenes"]):
        els += TEMPLATES[p["type"]](sc, p, sc.world_y)
    return els


def make_video(plan, out_path, voice=True, language="english", day=0):
    scenes = make_scenes(plan)
    voice_fn = None
    if voice:
        from voice import make_voiceover

        def voice_fn(text, path):
            return make_voiceover(text, path, language, max_seconds=60)
    clips = time_scenes(scenes, voice_fn, os.path.dirname(os.path.abspath(out_path)))
    render(scenes, build_elements(plan, scenes), out_path, clips, day=day)
    for _, path in clips:
        if os.path.exists(path):
            os.remove(path)
    return scenes[-1].start + scenes[-1].dur


def contact_sheet(video, png, every=1.5):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf",
                    f"fps=1/{every},scale=216:-1,tile=10x4", "-frames:v", "1", png], check=True)


if __name__ == "__main__":
    argv = sys.argv[1:]
    sheet = None
    if "--sheet" in argv:
        i = argv.index("--sheet")
        sheet = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    args = argv
    src, out = args[0], args[1] if len(args) > 1 else "output/story.mp4"
    with open(src, encoding="utf-8") as f:
        plan = json.load(f)
    from story_gen import validate
    errs = validate(plan)
    if errs:
        sys.exit("Plan problems:\n- " + "\n- ".join(errs))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    secs = make_video(plan, out, voice=not os.environ.get("NO_VOICE"),
                      language=os.environ.get("REEL_LANGUAGE", "english"))
    print(f"Rendered {out} ({secs:.1f}s)")
    if sheet:
        contact_sheet(out, sheet)
        print(f"Contact sheet {sheet}")
