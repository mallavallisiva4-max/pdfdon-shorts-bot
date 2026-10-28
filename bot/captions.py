"""Subtitle files (.srt) from the narration.

The voice is made one script part at a time, so each part's start and length in the video is known.
Inside a part, lines are timed by their share of the text, which is close enough for subtitles.
Once a Telugu track is on YouTube, viewers can switch on YouTube's auto-translate to any language."""
import re

MAX_WORDS = 10  # per subtitle line


def _lines(text):
    sentences = [s.strip() for s in re.split(r"(?<=[.!?।])\s+", text.strip()) if s.strip()]
    for sentence in sentences:
        words = sentence.split()
        for i in range(0, len(words), MAX_WORDS):
            yield " ".join(words[i:i + MAX_WORDS])


def _stamp(seconds):
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def srt(texts, timings):
    """texts: narration per part; timings: [(start, spoken_seconds), ...] per part."""
    cues = []
    for text, (start, spoken) in zip(texts, timings):
        lines = list(_lines(text))
        total = sum(len(l) for l in lines) or 1
        at = start
        for line in lines:
            length = spoken * len(line) / total
            cues.append((at, at + length, line))
            at += length
    return "".join(f"{i}\n{_stamp(a)} --> {_stamp(b)}\n{line}\n\n" for i, (a, b, line) in enumerate(cues, 1))
