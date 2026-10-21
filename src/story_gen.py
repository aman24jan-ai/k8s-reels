"""Ask Gemini (free tier) for a whiteboard story plan for one Kubernetes topic.

Gemini only picks scene templates and writes short text + cue words; story_build.py
does all the layout. Plans are validated, and Gemini gets the errors back to fix
them (up to 3 tries).
"""
import json
import os
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.join(HERE, "..", "examples", "pod.json")

TYPES = {"hook_title", "analogy", "inside_box", "node_rows", "flow", "scale", "trick", "recap"}

GUIDE = """You write scripts for 35-45 second vertical "whiteboard story" explainer videos
about Kubernetes for beginners. Each video is a short animated story on a black canvas:
a stick-figure narrator, teal boxes for servers/pods/containers, red when something fails.

Topic: "{topic}"

Story arc (5-7 scenes): a hook (problem or surprising fact) -> how it works, shown
visually -> what goes wrong or why it matters -> the practical kubectl/YAML "trick"
-> a recap with exactly 3 pills and "follow".

Pick each scene from these templates (fields in brackets are optional):
- hook_title: heading (1-3 words, the topic), card (<=14 chars), card_cue, [card_label],
  point_cue, [wrap_label + wrap_cue: a dashed box that wraps the card],
  [card2 + card2_cue + group_label: a second card joins], [tagline + tagline_cue].
  MUST be the first scene.
- analogy: heading, cards (1-2 short labels shown in a thought bubble), line (the
  real-world comparison, <=45 chars), cue.
- inside_box: heading, cards (1-3 labels), [badge + badge_cue], [link_label + link_cue:
  two-way arrow between the first two cards], [shared + shared_cue: a shared bar under
  the cards], [note + note_cue].
- node_rows: heading, [heading_cue], box_label (e.g. NODE, WORKER NODE, CLUSTER), rows
  (2-3), row_status (e.g. RUNNING, READY), [fail_row (0-based) + fail_cue +
  fail_status], [replace_cue + replace_status], [note + note_cue].
- flow: heading, steps (2-4 objects: {{"label", "cue", optional "side" (<=12 chars),
  optional "red": true}}), [note + note_cue]. Steps go top to bottom, joined by arrows.
- scale: heading, box_label, from (1-8), to (from-8), cue (the word when it grows),
  [status], [note + note_cue].
- trick: heading, [strike + strike_cue: the old way, crossed out], terminal (1-3 lines,
  each <=34 chars, real kubectl commands or YAML fields), terminal_cue,
  [result_count (0-6) + result_cue], [status].
- recap: heading (topic), pills (exactly 3 objects {{"text" (<=22 chars), "cue"}}),
  follow_cue. MUST be the last scene.

Rules:
- 100% technically accurate. Only real kubectl commands, flags and YAML fields.
- "vo" = what the narrator says in that scene: 1-2 short, energetic, conversational
  sentences in {lang}. 95-125 words in total across all scenes.
- Every cue value must be ONE word that appears exactly in that scene's "vo"
  (it is when the animation happens). Prefer distinctive words.
- On-screen text is short and in English, UPPERCASE for labels and headings.
- Use a simple real-world comparison somewhere.
- Also return: "title" (<=70 chars, curiosity first, not "What is ..."),
  "caption" (one line ending with a question for comments), "hashtags" (5),
  "keywords" (3).

Here is a complete, correct example for a different topic:
{example}

Reply with ONLY the JSON object for "{topic}"."""

LANGS = {"english": "simple spoken English",
         "hinglish": "natural Hinglish written in Devanagari, technical terms in English"}

REQUIRED = {"hook_title": ["heading", "card"], "analogy": ["line"],
            "inside_box": ["cards"], "node_rows": ["rows"], "flow": ["steps"],
            "scale": ["from", "to"], "trick": ["terminal"], "recap": ["heading", "pills"]}
LIMITS = {"heading": 28, "card": 14, "card2": 14, "card_label": 30, "group_label": 34,
          "tagline": 34, "wrap_label": 14, "line": 48, "badge": 18, "link_label": 14,
          "shared": 22, "note": 40, "box_label": 16, "row_status": 10, "fail_status": 10,
          "replace_status": 10, "strike": 30, "status": 34}


def _norm(w):
    return re.sub(r"[^\w]", "", str(w).lower())


def validate(plan) -> list[str]:
    errs = []
    if not isinstance(plan, dict) or not isinstance(plan.get("scenes"), list):
        return ["plan must be an object with a 'scenes' list"]
    scenes = plan["scenes"]
    if not 4 <= len(scenes) <= 7:
        errs.append(f"need 4-7 scenes, got {len(scenes)}")
    for k in ("title", "caption", "hashtags"):
        if not plan.get(k):
            errs.append(f"missing '{k}'")
    total = 0
    for i, s in enumerate(scenes):
        where = f"scene {i + 1}"
        t = s.get("type")
        if t not in TYPES:
            errs.append(f"{where}: unknown type '{t}'")
            continue
        vo = s.get("vo", "")
        words = {_norm(w) for w in vo.split()}
        total += len(vo.split())
        if not 6 <= len(vo.split()) <= 40:
            errs.append(f"{where}: vo should be 6-40 words")
        for f in REQUIRED[t]:
            if not s.get(f):
                errs.append(f"{where} ({t}): missing '{f}'")
        for k, v in s.items():
            if (k == "cue" or k.endswith("_cue")) and v and _norm(v) not in words:
                errs.append(f"{where}: {k} '{v}' is not a word in its vo")
            if k in LIMITS and isinstance(v, str) and len(v) > LIMITS[k]:
                errs.append(f"{where}: '{k}' longer than {LIMITS[k]} chars")
        for key in ("pills", "steps"):
            for item in s.get(key) or []:
                if isinstance(item, dict) and item.get("cue") and _norm(item["cue"]) not in words:
                    errs.append(f"{where}: {key} cue '{item['cue']}' is not a word in its vo")
        if t == "recap" and len(s.get("pills") or []) != 3:
            errs.append(f"{where}: recap needs exactly 3 pills")
        if t == "flow" and not 2 <= len(s.get("steps") or []) <= 4:
            errs.append(f"{where}: flow needs 2-4 steps")
        if t == "trick":
            for line in s.get("terminal") or []:
                if len(str(line)) > 34:
                    errs.append(f"{where}: terminal line too long: {line}")
        for c in (s.get("cards") or []):
            if len(str(c)) > 14:
                errs.append(f"{where}: card label too long: {c}")
    if scenes and scenes[0].get("type") != "hook_title":
        errs.append("first scene must be hook_title")
    if scenes and scenes[-1].get("type") != "recap":
        errs.append("last scene must be recap")
    if not 80 <= total <= 140:
        errs.append(f"total voiceover is {total} words; aim for 95-125")
    return errs


def _ask(prompt: str) -> str:
    from script_gen import FALLBACK_MODELS, GEMINI_MODEL
    key = os.environ["GEMINI_API_KEY"]
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.6, "responseMimeType": "application/json"}}
    last = None
    timeout = int(os.environ.get("GEMINI_TIMEOUT", "180"))
    for model in [GEMINI_MODEL] + [m for m in FALLBACK_MODELS if m != GEMINI_MODEL]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(3):
            try:
                r = requests.post(url, params={"key": key}, json=body, timeout=timeout)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # slow or dropped connection: retry once, then move on to the next model
                last = f"{model}: {type(e).__name__}"
                print(f"Gemini {model} timed out/disconnected (attempt {attempt + 1})",
                      file=sys.stderr)
                if attempt >= 1:
                    break
                time.sleep(10)
                continue
            if r.status_code == 404:
                last = f"model {model} not available"
                break
            if r.status_code in (429, 500, 502, 503, 504):
                last = f"Gemini busy ({r.status_code}) on {model}"
                time.sleep(15 * (attempt + 1))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:300]}")
            try:
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError, ValueError):
                last = f"{model}: empty or blocked reply"
                time.sleep(5)
                continue
            print(f"Story written with {model}", file=sys.stderr)
            return text
    raise RuntimeError(f"Gemini unavailable after trying all models: {last}")


def _parse(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


def generate_plan(topic: str, language: str = "english") -> dict:
    with open(EXAMPLE, encoding="utf-8") as f:
        example = f.read()
    prompt = GUIDE.format(topic=topic, example=example, lang=LANGS.get(language, LANGS["english"]))
    errs = []
    for attempt in range(3):
        p = prompt
        if errs:
            p += "\n\nYour previous answer had these problems. Fix all of them:\n- " + \
                 "\n- ".join(errs)
        try:
            plan = _parse(_ask(p))
        except (ValueError, KeyError) as e:
            errs = [f"invalid JSON: {e}"]
            continue
        errs = validate(plan)
        if not errs:
            plan["topic"] = topic
            return plan
        print(f"Plan attempt {attempt + 1} had {len(errs)} problem(s); retrying", file=sys.stderr)
    raise RuntimeError(f"Could not get a valid story plan for '{topic}':\n- " + "\n- ".join(errs))


if __name__ == "__main__":
    print(json.dumps(generate_plan(sys.argv[1] if len(sys.argv) > 1 else "What is a Service?"),
                     indent=2, ensure_ascii=False))
