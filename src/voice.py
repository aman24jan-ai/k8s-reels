"""Free voiceover with Microsoft Edge TTS, fitted to the reel length."""
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


async def _speak(text: str, voice: str, rate: str, out: str):
    await edge_tts.Communicate(text, voice, rate=rate).save(out)


def make_voiceover(text: str, out_path: str, language: str = "english",
                   max_seconds: float = 14.3) -> float:
    """Create an mp3 voiceover no longer than max_seconds. Returns its duration."""
    voice = VOICES.get(language, VOICES["english"])
    raw = out_path + ".raw.mp3"
    asyncio.run(_speak(text, voice, os.environ.get("TTS_RATE", "+8%"), raw))
    dur = _duration(raw)
    if dur > max_seconds:  # speed up gently so it fits the 15 s reel
        tempo = min(dur / max_seconds, 1.6)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw,
                        "-filter:a", f"atempo={tempo:.3f}", out_path], check=True)
        os.remove(raw)
    else:
        os.replace(raw, out_path)
    return _duration(out_path)
