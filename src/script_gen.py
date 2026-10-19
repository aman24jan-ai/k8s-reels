"""Generate a 15-second reel script for one Kubernetes topic using the free Gemini API."""
import json
import os
import re
import time

import requests

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
LANGUAGE = os.environ.get("REEL_LANGUAGE", "english")  # english | hinglish

PROMPT = """You write scripts for 15-second vertical Kubernetes explainer reels for beginners.
Topic: "{topic}"

Rules:
- Be 100% technically accurate. No made-up commands or flags.
- "voiceover": {lang_rule} 32 to 38 words total. Plain sentences, no emojis, no hashtags, no markdown.
- "hook": max 6 words, on-screen, English.
- "title": max 4 words, on-screen, English.
- "points": exactly 3 short on-screen bullet points in English, max 6 words each.
- "command": one real, safe kubectl/helm command related to the topic (max 40 chars), or "" if none fits.
- "caption": one-line social caption in English, max 15 words.
- "hashtags": 5 relevant hashtags, each starting with #.

Reply with ONLY valid JSON with keys: hook, title, points, command, voiceover, caption, hashtags."""

LANG_RULES = {
    "hinglish": "Natural spoken Hinglish written in Devanagari script, keep technical terms "
                "(Pod, Node, Deployment, kubectl, etc.) in English Latin letters.",
    "english": "Simple spoken English.",
}


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def _validate(d: dict) -> dict:
    for key in ("hook", "title", "points", "voiceover", "caption", "hashtags"):
        if key not in d or not d[key]:
            raise ValueError(f"missing {key}")
    d["points"] = [str(p) for p in d["points"]][:3]
    if len(d["points"]) < 3:
        raise ValueError("need 3 points")
    d.setdefault("command", "")
    if isinstance(d["hashtags"], str):
        d["hashtags"] = d["hashtags"].split()
    return d


def generate(topic: str) -> dict:
    """Return a script dict for the topic. Retries a few times on bad JSON or rate limits."""
    key = os.environ["GEMINI_API_KEY"]
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent")
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(
            topic=topic, lang_rule=LANG_RULES.get(LANGUAGE, LANG_RULES["english"]))}]}],
        "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"},
    }
    last_err = None
    for attempt in range(4):
        try:
            r = requests.post(url, params={"key": key}, json=body, timeout=60)
            if r.status_code in (429, 500, 503):
                raise RuntimeError(f"Gemini busy ({r.status_code})")
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return _validate(_extract_json(text))
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Script generation failed for '{topic}': {last_err}")


if __name__ == "__main__":
    import sys
    print(json.dumps(generate(sys.argv[1] if len(sys.argv) > 1 else "What is a Pod?"),
                     ensure_ascii=False, indent=2))
