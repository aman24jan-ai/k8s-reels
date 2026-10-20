"""Daily pipeline: topic -> story/script -> voice -> video -> YouTube Shorts (+ Instagram).

STYLE=whiteboard (default): 35-45 s animated whiteboard story (story_gen + story_build).
STYLE=template            : the original 15 s motion-graphics reel (script_gen + render).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

STATE = os.path.join(ROOT, "state.json")
TOPICS = os.path.join(ROOT, "topics.txt")
QUEUE = os.path.join(ROOT, "queue")      # optional hand-checked plans: queue/day_<N>.json
OUT = os.path.join(ROOT, "output")
SCRIPTS = os.path.join(ROOT, "scripts_log")


def flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes")


def load_state() -> dict:
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    return {"day": 0, "history": []}


def load_queued(day: int, needs: str):
    """A hand-written plan/script for this day, if it fits the current style."""
    path = os.path.join(QUEUE, f"day_{day}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if needs in data:
            print(f"Using hand-checked {path}")
            return data
    return None


def make_whiteboard(day, topic, language):
    plan = load_queued(day, "scenes")
    if plan is None:
        from story_gen import generate_plan
        plan = generate_plan(topic, language)
    plan["topic"] = topic
    with open(os.path.join(SCRIPTS, f"day_{day}.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    from story_build import make_video
    video = os.path.join(OUT, f"day_{day}.mp4")
    secs = make_video(plan, video, voice=not flag("NO_VOICE"), language=language, day=day)
    print(f"Rendered {video} ({secs:.1f}s)")
    title = plan["title"].rstrip(".")
    title = (title if len(title) <= 88 else title[:85] + "...") + " #Shorts"
    return video, title, plan.get("caption", ""), plan.get("hashtags", [])


def make_template(day, topic, language):
    import render
    script = load_queued(day, "points")
    if script is None:
        from script_gen import generate
        script = generate(topic)
    script["topic"] = topic
    with open(os.path.join(SCRIPTS, f"day_{day}.json"), "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    audio = os.path.join(OUT, f"day_{day}.mp3")
    from voice import make_voiceover
    voice_seconds, words = make_voiceover(script["voiceover"], audio, language)
    video = os.path.join(OUT, f"day_{day}.mp4")
    render.render(script, audio, video, day=day, handle=os.environ.get("CHANNEL_HANDLE", ""),
                  words=words, voice_seconds=voice_seconds)
    print(f"Rendered {video}")
    title = f"{script['hook'].rstrip('.')} | {script['title']} #Shorts"
    if len(title) > 100:
        title = f"{script['title']} | Kubernetes in 15s #Shorts"
    return video, title, script.get("caption", ""), script.get("hashtags", [])


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SCRIPTS, exist_ok=True)
    state = load_state()
    with open(TOPICS, encoding="utf-8") as f:
        topics = [t.strip() for t in f if t.strip() and not t.startswith("#")]

    day = state["day"] + 1
    topic = topics[(day - 1) % len(topics)]
    language = os.environ.get("REEL_LANGUAGE", "english")
    style = os.environ.get("STYLE", "whiteboard").strip().lower()
    print(f"Day {day}: {topic}  (style: {style})")

    if style == "template":
        video, title, caption, tags = make_template(day, topic, language)
    else:
        video, title, caption, tags = make_whiteboard(day, topic, language)

    description = f"{caption}\n\nDay {day} of Kubernetes in plain English.\n\n{' '.join(tags)}"
    result = {"day": day, "topic": topic, "style": style}

    if flag("DRY_RUN"):
        print("DRY_RUN on: skipping uploads")
    else:
        if flag("POST_YOUTUBE", "true"):
            from upload_youtube import upload as yt
            result["youtube"] = yt(video, title, description, tags)
            print("YouTube:", result["youtube"])
        if flag("POST_INSTAGRAM", "false"):
            from upload_instagram import upload as ig
            result["instagram"] = ig(video, description)
            print("Instagram media id:", result["instagram"])

    # only advance the day counter when the run did real posting
    if not flag("DRY_RUN"):
        state["day"] = day
        state["history"].append(result)
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
