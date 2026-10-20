# Whiteboard story videos

The daily bot now makes 35-45 second animated "whiteboard story" videos by default
(black canvas, marker lettering, stick-figure narrator, teal diagrams).

## How it works

```
topics.txt -> story_gen.py (Gemini writes a scene plan) -> story_build.py (templates)
           -> whiteboard.py (animation) + voice.py (Edge TTS, synced per word) -> YouTube
```

Gemini only chooses scene templates and writes short text. It never places anything,
so every video stays inside the Shorts safe area. Plans are checked by
`story_gen.validate()`, and Gemini is asked to fix any problems (up to 3 tries).

| Template | What it shows |
|---|---|
| `hook_title` | Big title, icon, stick figure, a card that gets wrapped or joined (always first) |
| `analogy` | Thought bubble with cards + a real-world comparison line |
| `inside_box` | Dashed box with 1-3 cards, a badge, a two-way link, a shared bar |
| `node_rows` | A node/cluster with rows of containers; one row can fail and be replaced |
| `flow` | 2-4 boxes top to bottom joined by arrows (request paths) |
| `scale` | Pods growing from N to M (scaling, replicas) |
| `trick` | Crossed-out old way, a typing terminal, the result |
| `recap` | Title, icon, 3 pills, "follow" (always last) |

Each animation fires on a **cue word**: the exact moment that word is spoken.

## Files

- `src/story_gen.py` – Gemini prompt, validation, retries
- `src/story_build.py` – the 8 templates, `make_video()`, CLI
- `src/whiteboard.py` – animation engine
- `examples/*.json` – hand-written plans (Pod, Service, Rolling update)
- `queue/day_N.json` – a plan here (with `"scenes"`) is used instead of Gemini for that day
- `tests/test_story.py` – offline checks: plans valid, every scene renders, safe area

## Settings (GitHub → Settings → Secrets and variables → Actions → Variables)

| Variable | Meaning | Default |
|---|---|---|
| `STYLE` | `whiteboard` or `template` (the old 15 s reel) | `whiteboard` |

## Preview without posting

GitHub → Actions → **Preview whiteboard stories (no posting)** → Run workflow:
- `examples/service.json` (or any examples/queue file) renders that plan with voice
- `ai:What is a ConfigMap?` lets Gemini write a plan and renders it

Download the video, contact sheet and plan from **Artifacts**.

## Local checks (no internet needed)

```bash
python tests/test_story.py
NO_VOICE=1 python src/story_build.py examples/pod.json out.mp4 --sheet sheet.png
```
