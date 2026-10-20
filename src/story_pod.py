"""Prototype: "What is a Pod?" as a ~40 s whiteboard story.

Run:  python src/story_pod.py            (voice via Edge TTS, needs internet)
      NO_VOICE=1 python src/story_pod.py (silent timing estimate, for layout checks)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from whiteboard import (AppCard, Arrow, Badge, Box, Containers, Hex, Pill, Scene,  # noqa: E402
                        Stick, Strike, Terminal, Text, GREY, HAND, MARKER, MONO, ORANGE,
                        TEAL, WHITE, render, time_scenes)

SCENES = [
    Scene("Kubernetes never runs your container directly. "
          "It always wraps it in something called a Pod.", 0),
    Scene("A Pod is the smallest thing Kubernetes can deploy. "
          "One or more containers, packed together.", 0),
    Scene("Containers in the same Pod share one IP address and storage. "
          "So they talk over localhost, like roommates sharing one flat.", 1600),
    Scene("But Pods are temporary. When one crashes, Kubernetes doesn't repair it. "
          "It throws it away and starts a new Pod, with a new IP.", 3200, hold=0.6),
    Scene("That's why you rarely create Pods yourself. "
          "You write a Deployment, and say how many you want.", 4800, hold=1.6),
    Scene("So, Pods: the smallest unit, a shared network, and fully disposable. "
          "Follow for more Kubernetes in plain English.", 6400, hold=1.0),
]


def build(sc):
    s1, s2, s3, s4, s5, s6 = sc
    els = []

    # 1-2 · HOOK: a container gets wrapped in a Pod
    els += [
        Text(s1.start + 0.05, 90, 330, "PODS", 120, WHITE, anchor="lm", sfx="boom"),
        Hex(s1.start + 0.4, 470, 335, 52),
        Stick(s1.start + 0.2, 230, 860, "think", scale=1.1,
              poses=[(s1.at("wraps", 0.6), "point")]),
        # the Pod outline is listed first so it is drawn behind the containers
        Box(s1.at("pod", 0.85), 430, 600, 560, 420, "dashed", label="POD", label_size=56),
        AppCard(s1.at("container", 0.3), 460, 650, 240, 300, "YOUR APP",
                slide_from=(590, 650), slide_t=s2.at("more", 0.6)),
        Text(s1.at("container", 0.3) + 0.3, 710, 1000, "container", 44, TEAL, HAND,
             t1=s2.at("more", 0.6) - 0.2),
        AppCard(s2.at("more", 0.6), 730, 650, 240, 300, "LOGGER",
                slide_from=(1150, 650), slide_t=s2.at("more", 0.6)),
        Text(s2.at("more", 0.6) + 0.6, 710, 1060, "one or more containers", 44, TEAL, HAND),
        Text(s2.at("smallest", 0.2), 540, 1340, "SMALLEST THING YOU CAN DEPLOY", 50, ORANGE),
    ]

    # 3 · INSIDE A POD: shared IP + storage, localhost
    y = s3.world_y
    els += [
        Text(s3.start + 0.1, 540, y + 330, "INSIDE A POD", 64, TEAL),
        Box(s3.start + 0.2, 110, y + 470, 860, 720, "dashed", sfx=None),
        AppCard(s3.start + 0.35, 170, y + 560, 300, 300, "APP"),
        AppCard(s3.start + 0.55, 610, y + 560, 300, 300, "LOGGER"),
        Badge(s3.at("ip", 0.35), 540, y + 470, "IP 10.1.0.7", "orange", size=38),
        Arrow(s3.at("localhost", 0.7), (480, y + 720), (600, y + 720), TEAL, both=True),
        Text(s3.at("localhost", 0.7), 540, y + 660, "localhost", 34, TEAL, HAND),
        Arrow(s3.at("storage", 0.45), (320, y + 870), (320, y + 975), TEAL),
        Arrow(s3.at("storage", 0.45) + 0.15, (760, y + 870), (760, y + 975), TEAL),
        Box(s3.at("storage", 0.45) + 0.2, 170, y + 985, 740, 110, "teal", sfx=None),
        Text(s3.at("storage", 0.45) + 0.3, 540, y + 1040, "SHARED VOLUME", 44, TEAL),
        Text(s3.at("roommates", 0.85), 540, y + 1330, "like roommates sharing one flat",
             50, WHITE, HAND),
    ]

    # 4 · PODS ARE TEMPORARY: one crashes, a new one replaces it
    y = s4.world_y
    crash, gone, new = s4.at("crashes", 0.3), s4.at("away", 0.62), s4.at("new", 0.75)
    els += [
        Text(s4.at("temporary", 0.1), 540, y + 330, "PODS ARE TEMPORARY", 66, ORANGE),
        Box(s4.start + 0.3, 90, y + 480, 900, 800, "teal", label="NODE", sfx=None),
    ]
    for i, ry in enumerate((y + 530, y + 770, y + 1010)):
        t0 = s4.start + 0.5 + i * 0.2
        if i == 1:
            els += [
                Box(t0, 130, ry, 820, 200, "dashed", crash_t=crash, t1=gone, sfx=None),
                Containers(t0 + 0.1, 175, ry + 75, 4, crash_t=crash, t1=gone),
                Badge(t0 + 0.3, 790, ry + 100, "RUNNING", "teal", t1=gone, switch_t=crash,
                      new_text="CRASHED", new_style="red"),
                Box(new, 130, ry, 820, 200, "dashed", sfx=None),
                Containers(new + 0.1, 175, ry + 75, 4),
                Badge(new + 0.3, 790, ry + 100, "NEW POD", "orange"),
            ]
        else:
            els += [
                Box(t0, 130, ry, 820, 200, "dashed", sfx=None),
                Containers(t0 + 0.1, 175, ry + 75, 4),
                Badge(t0 + 0.3, 790, ry + 100, "RUNNING", "teal"),
            ]
    els.append(Text(s4.at("ip", 0.9), 540, y + 1390, "IP 10.1.0.7  ->  10.1.0.9", 48, ORANGE,
                    HAND))

    # 5 · THE TRICK: a Deployment keeps N pods running
    y = s5.world_y
    many = s5.at("many", 0.75)
    els += [
        Text(s5.start + 0.1, 540, y + 320, "THE TRICK?", 96, ORANGE),
        Text(s5.start + 0.5, 540, y + 470, "create pods by hand", 50, GREY, HAND),
        Strike(s5.at("yourself", 0.35), 330, 750, y + 474),
        Terminal(s5.at("deployment", 0.55) - 0.4, 140, y + 560, 800,
                 ["kind: Deployment", "replicas: 3"]),
        Arrow(many, (540, y + 830), (540, y + 940)),
    ]
    for i, px in enumerate((110, 400, 690)):
        t0 = many + 0.35 + i * 0.25
        els += [Box(t0, px, y + 970, 280, 160, "dashed", label=None),
                Containers(t0 + 0.1, px + 70, y + 1025, 2, size=56)]
    els.append(Text(many + 1.3, 540, y + 1220, "3 / 3 running", 48, TEAL, MONO, sfx="ding"))

    # 6 · RECAP
    y = s6.world_y
    els += [
        Text(s6.start + 0.1, 540, y + 360, "PODS", 130, WHITE),
        Hex(s6.start + 0.4, 540, y + 560, 80),
        Pill(s6.at("smallest", 0.3), 540, y + 760, "SMALLEST UNIT"),
        Pill(s6.at("network", 0.45), 540, y + 880, "SHARED NETWORK"),
        Pill(s6.at("disposable", 0.6), 540, y + 1000, "DISPOSABLE"),
        Text(s6.at("follow", 0.75), 540, y + 1170, "follow for daily K8s", 48, TEAL, HAND,
             sfx="ding"),
    ]
    return els


def main(out="output/pod_story.mp4"):
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    voice_fn = None
    if not os.environ.get("NO_VOICE"):
        from voice import make_voiceover

        def voice_fn(text, path):
            return make_voiceover(text, path, os.environ.get("REEL_LANGUAGE", "english"),
                                  max_seconds=60)
    clips = time_scenes(SCENES, voice_fn, os.path.dirname(out) or ".")
    render(SCENES, build(SCENES), out, clips, day=3)
    total = SCENES[-1].start + SCENES[-1].dur
    print(f"Rendered {out} ({total:.1f}s)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "output/pod_story.mp4")
