"""Generate a 15-second reel script for one Kubernetes topic using the free Gemini API."""
import json
import os
import re
import time

import requests

GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-flash-latest"
FALLBACK_MODELS = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-3.6-flash",
                   "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
LANGUAGE = os.environ.get("REEL_LANGUAGE", "english")  # english | hinglish

PROMPT = """You write scripts for viral 15-second vertical Kubernetes explainer reels for beginners.
Topic: "{topic}"

The viewer decides in 1 second whether to keep watching, so the opening must create curiosity.

Rules:
- Be 100% technically accurate. No made-up commands or flags.
- "hook": max 6 words, on-screen, English. A bold claim, surprising fact, common mistake or
  direct question. Never start with "What is" or "Let's learn". Good examples:
  "Your app crashed. Kubernetes didn't care.", "Stop running containers like this",
  "90% of beginners get this wrong".
- "title": max 4 words, on-screen, English.
- "analogy": max 9 words, on-screen, English. A simple real-world comparison,
  e.g. "A Pod is a lunchbox holding your containers".
- "points": exactly 3 punchy on-screen points in English, max 6 words each.
- "command": one real, safe kubectl/helm command related to the topic (max 40 chars), or "" if none fits.
- "question": max 8 words, on-screen. A quick question viewers can answer in the comments,
  e.g. "Which one do you use: Deployment or StatefulSet?".
- "keywords": 2-3 single important words that appear in the hook, title or points, to highlight.
- "voiceover": {lang_rule} 32 to 38 words total. Structure: say the hook, then the analogy,
  then the 3 points, in a fast, energetic, conversational tone. Short sentences.
  No emojis, no hashtags, no markdown, no "in this video".
- "caption": one-line social caption in English, max 15 words, ending with the question.
- "hashtags": 5 relevant hashtags, each starting with #.

Reply with ONLY valid JSON with keys: hook, title, analogy, points, command, question,
keywords, voiceover, caption, hashtags."""

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
    d.setdefault("analogy", "")
    d.setdefault("question", "")
    kw = d.get("keywords") or []
    if isinstance(kw, str):
        kw = kw.replace(",", " ").split()
    d["keywords"] = [str(k).strip("#").lower() for k in kw][:3]
    if isinstance(d["hashtags"], str):
        d["hashtags"] = d["hashtags"].split()
    return d


def generate(topic: str) -> dict:
    """Return a script dict for the topic. Retries a few times on bad JSON or rate limits."""
    key = os.environ["GEMINI_API_KEY"]
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(
            topic=topic, lang_rule=LANG_RULES.get(LANGUAGE, LANG_RULES["english"]))}]}],
        "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"},
    }
    # Google retires model names often; if one 404s, fall back to the next.
    models = [GEMINI_MODEL] + [m for m in FALLBACK_MODELS if m != GEMINI_MODEL]
    last_err = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(4):
            try:
                r = requests.post(url, params={"key": key}, json=body, timeout=60)
                if r.status_code == 404:
                    last_err = RuntimeError(f"model '{model}' not available (404)")
                    print(f"Gemini model '{model}' not available, trying next")
                    break  # try the next model
                if r.status_code in (429, 500, 503):
                    raise RuntimeError(f"Gemini busy ({r.status_code}) on {model}")
                if r.status_code >= 400:
                    # 400/403 usually means a bad or restricted API key: don't hammer it
                    raise PermissionError(f"Gemini error {r.status_code}: {r.text[:300]}")
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                print(f"Script written with {model}")
                return _validate(_extract_json(text))
            except PermissionError:
                raise
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Script generation failed for '{topic}': {last_err}")


if __name__ == "__main__":
    import sys
    print(json.dumps(generate(sys.argv[1] if len(sys.argv) > 1 else "What is a Pod?"),
                     ensure_ascii=False, indent=2))
