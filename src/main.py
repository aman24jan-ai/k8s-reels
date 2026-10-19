"""Daily pipeline: topic -> script -> voice -> reel -> YouTube Shorts + Instagram Reels."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import render  # noqa: E402

STATE = os.path.join(ROOT, "state.json")
TOPICS = os.path.join(ROOT, "topics.txt")
QUEUE = os.path.join(ROOT, "queue")      # optional hand-checked scripts: queue/day_<N>.json
OUT = os.path.join(ROOT, "output")
SCRIPTS = os.path.join(ROOT, "scripts_log")


def flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes")


def load_state() -> dict:
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    return {"day": 0, "history": []}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SCRIPTS, exist_ok=True)
    state = load_state()
    with open(TOPICS, encoding="utf-8") as f:
        topics = [t.strip() for t in f if t.strip() and not t.startswith("#")]

    day = state["day"] + 1
    topic = topics[(day - 1) % len(topics)]
    language = os.environ.get("REEL_LANGUAGE", "english")
    handle = os.environ.get("CHANNEL_HANDLE", "")
    print(f"Day {day}: {topic}")

    queued = os.path.join(QUEUE, f"day_{day}.json")
    if os.path.exists(queued):
        with open(queued, encoding="utf-8") as f:
            script = json.load(f)
        print("Using hand-checked script from queue/")
    else:
        from script_gen import generate
        script = generate(topic)
    script["topic"] = topic
    with open(os.path.join(SCRIPTS, f"day_{day}.json"), "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    audio = os.path.join(OUT, f"day_{day}.mp3")
    from voice import make_voiceover
    make_voiceover(script["voiceover"], audio, language)

    video = os.path.join(OUT, f"day_{day}.mp4")
    render.render(script, audio, video, day=day, handle=handle)
    print(f"Rendered {video}")

    tags = script.get("hashtags", [])
    caption = f"{script['caption']}\n\nDay {day} of Kubernetes in 15 seconds.\n\n{' '.join(tags)}"
    result = {"day": day, "topic": topic}

    if flag("DRY_RUN"):
        print("DRY_RUN on: skipping uploads")
    else:
        if flag("POST_YOUTUBE", "true"):
            from upload_youtube import upload as yt
            title = f"{script['title']} | Kubernetes in 15s #Shorts"
            result["youtube"] = yt(video, title, caption, tags)
            print("YouTube:", result["youtube"])
        if flag("POST_INSTAGRAM", "true"):
            from upload_instagram import upload as ig
            result["instagram"] = ig(video, caption)
            print("Instagram media id:", result["instagram"])

    # only advance the day counter when the run did real posting
    if not flag("DRY_RUN"):
        state["day"] = day
        state["history"].append(result)
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
