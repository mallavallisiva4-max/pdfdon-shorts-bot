"""Telugu text-to-speech with Microsoft Edge neural voices (free, no key)."""
import asyncio
import os
import subprocess

import edge_tts

# te-IN-MohanNeural (male) or te-IN-ShrutiNeural (female)
VOICE = os.environ.get("TTS_VOICE", "te-IN-MohanNeural")
RATE = os.environ.get("TTS_RATE", "+8%")


async def _say(text, path):
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(path))


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
    for i, text in enumerate(lines):
        path = outdir / f"{i}.mp3"
        asyncio.run(_say(text, path))
        clips.append((path, duration(path)))
        print(f"  voice {i}: {clips[-1][1]:.1f}s")
    return clips
