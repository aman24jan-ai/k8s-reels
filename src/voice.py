"""Free voiceover with Microsoft Edge TTS, fitted to the reel length, plus word timings."""
import asyncio
import json
import os
import subprocess

import edge_tts

VOICES = {
    "hinglish": os.environ.get("TTS_VOICE_HI", "hi-IN-MadhurNeural"),
    "english": os.environ.get("TTS_VOICE_EN", "en-IN-PrabhatNeural"),
}


def _duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


async def _speak(text: str, voice: str, rate: str, out: str) -> list[dict]:
    """Save the mp3 and return word timings [{word, start, end}] in seconds."""
    try:
        comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    except TypeError:  # older edge-tts sends word boundaries by default
        comm = edge_tts.Communicate(text, voice, rate=rate)
    words = []
    with open(out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words.append({"word": chunk["text"], "start": start,
                              "end": start + chunk["duration"] / 1e7})
    return words


def make_voiceover(text: str, out_path: str, language: str = "english",
                   max_seconds: float = 13.6) -> tuple[float, list[dict]]:
    """Create an mp3 voiceover no longer than max_seconds.

    Returns (duration, word_timings). Timings are relative to the start of the audio.
    """
    voice = VOICES.get(language, VOICES["english"])
    raw = out_path + ".raw.mp3"
    words = asyncio.run(_speak(text, voice, os.environ.get("TTS_RATE", "+10%"), raw))
    dur = _duration(raw)
    if dur > max_seconds:  # speed up gently so it fits the 15 s reel
        tempo = min(dur / max_seconds, 1.6)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw,
                        "-filter:a", f"atempo={tempo:.3f}", out_path], check=True)
        os.remove(raw)
        for w in words:
            w["start"] /= tempo
            w["end"] /= tempo
    else:
        os.replace(raw, out_path)
    return _duration(out_path), words
