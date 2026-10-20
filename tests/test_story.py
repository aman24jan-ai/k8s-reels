"""Offline checks for whiteboard stories: plans validate, every scene renders,
and nothing is drawn outside the safe area. Run: python tests/test_story.py"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PIL import Image, ImageChops, ImageDraw  # noqa: E402

import story_build  # noqa: E402
from story_gen import validate  # noqa: E402
from whiteboard import BG, H, W, camera, time_scenes  # noqa: E402

PLANS = sorted(glob.glob(os.path.join(ROOT, "examples", "*.json")) +
               [p for p in glob.glob(os.path.join(ROOT, "queue", "*.json"))
                if "scenes" in json.load(open(p, encoding="utf-8"))])


def frame(scenes, els, t):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    cam = camera(scenes, t)
    for e in els:
        e.draw(d, t, cam)
    return img


def check(path):
    plan = json.load(open(path, encoding="utf-8"))
    errs = validate(plan)
    assert not errs, f"{path}: {errs}"
    scenes = story_build.make_scenes(plan)
    time_scenes(scenes)
    els = story_build.build_elements(plan, scenes)
    for i, sc in enumerate(scenes):
        img = frame(scenes, els, sc.start + sc.dur - 0.45)  # before the camera pans
        diff = ImageChops.difference(img, Image.new("RGB", (W, H), BG)).convert("L")
        box = diff.point(lambda v: 255 if v > 12 else 0).getbbox()
        assert box, f"{path} scene {i + 1}: nothing drawn"
        x0, y0, x1, y1 = box
        assert x0 >= 50 and x1 <= W - 50, f"{path} scene {i + 1}: drawn outside x safe area {box}"
        assert y0 >= 180 and y1 <= 1560, f"{path} scene {i + 1}: drawn outside y safe area {box}"
    total = scenes[-1].start + scenes[-1].dur
    return total


if __name__ == "__main__":
    for p in PLANS:
        print(f"ok  {os.path.relpath(p, ROOT)}  (~{check(p):.0f}s)")
    print(f"{len(PLANS)} plans passed")
