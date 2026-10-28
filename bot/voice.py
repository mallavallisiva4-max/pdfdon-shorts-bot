"""Telugu text-to-speech. Microsoft Edge neural voice first (free, no key); if that service
refuses (it sometimes does from GitHub's servers), Google Translate's Telugu voice (gTTS)."""
import asyncio
import os
import subprocess
import time

import edge_tts
from gtts import gTTS

# te-IN-MohanNeural (male) or te-IN-ShrutiNeural (female)
VOICE = os.environ.get("TTS_VOICE", "te-IN-MohanNeural")
RATE = os.environ.get("TTS_RATE", "+8%")
TRIES = 3


async def _edge(text, path):
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(path))


def _say(text, path):
    for attempt in range(1, TRIES + 1):
        try:
            asyncio.run(_edge(text, path))
            if path.exists() and path.stat().st_size > 0:
                return "edge"
        except Exception as e:
            print(f"  edge voice attempt {attempt} failed: {type(e).__name__}")
        time.sleep(3 * attempt)
    gTTS(text=text, lang="te").save(str(path))
    return "google"


def duration(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)]
    )
    return float(out.decode().strip())


def synthesize(lines, outdir):
    """Returns [(mp3_path, seconds), ...], one per line."""
    outdir.mkdir(parents=True, exist_ok=True)
    clips = []
    engine = None
    for i, text in enumerate(lines):
        path = outdir / f"{i}.mp3"
        # Keep one voice for the whole Short: once Edge fails, use Google for the rest.
        if engine == "google":
            gTTS(text=text, lang="te").save(str(path))
        else:
            engine = _say(text, path)
            if engine == "google" and i > 0:
                print("  switching the earlier lines to the Google voice too")
                for j in range(i):
                    gTTS(text=lines[j], lang="te").save(str(outdir / f"{j}.mp3"))
                    clips[j] = (outdir / f"{j}.mp3", duration(outdir / f"{j}.mp3"))
        clips.append((path, duration(path)))
        print(f"  voice {i} ({engine}): {clips[-1][1]:.1f}s")
    return clips
