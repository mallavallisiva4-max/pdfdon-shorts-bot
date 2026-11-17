"""'సింహం నాన్న కథలు' - animated animal story Shorts about pdfdon.com tools.

Picks the next episode from stories/episodes.json that is not in state/stories_done.json, makes the
Telugu voices (Edge TTS), plays stories/story.html in Chromium while recording it, joins the two with
ffmpeg, then uploads to YouTube (public) and Instagram.

    python -m bot.story                      # Short: make + upload the next episode
    python -m bot.story --kind long          # long: next 3 episodes joined into one 16:9 video
    python -m bot.story --dry-run            # make only
    python -m bot.story --id deer-ocr
"""
import argparse
import asyncio
import json
import os
import pathlib
import subprocess
import time

import edge_tts

ROOT = pathlib.Path(__file__).resolve().parent.parent
STORIES = ROOT / "stories"
DONE = ROOT / "state" / "stories_done.json"            # episodes already posted as Shorts
DONE_LONG = ROOT / "state" / "stories_long_done.json"  # episodes already used in a long video
OUT = ROOT / "out_story"
VOICES = {
    "father": dict(voice="te-IN-MohanNeural", rate="-8%", pitch="-6Hz"),
    "cub": dict(voice="te-IN-ShrutiNeural", rate="+5%", pitch="+30Hz"),
    "owl": dict(voice="te-IN-MohanNeural", rate="-14%", pitch="-20Hz"),        # old grandpa
    "hero-male": dict(voice="te-IN-MohanNeural", rate="+8%", pitch="+22Hz"),
    "hero-female": dict(voice="te-IN-ShrutiNeural", rate="+0%", pitch="+8Hz"),
}
GAP = 0.45
SFX = STORIES / "sfx"
# background sound for each scene: (file, volume)
BEDS = {  # kept low and clean so the voice stays clear
    "night": [("crickets", 0.10), ("lullaby", 0.07)],
    "owl": [("crickets", 0.10)],
    "hero": [("birds", 0.09)],
    "error": [],
    "tools": [("lullaby", 0.07)],
    "free": [("lullaby", 0.07)],
    "success": [("birds", 0.09)],
    "end": [("crickets", 0.10), ("lullaby", 0.09)],
}
# one-off sounds, seconds after the scene starts (these match the animations in story.html)
HITS = {
    "error": [("buzz", 1.0, 0.25)],
    "owl": [("hoot", 0.1, 0.4)],
    "tools": [("pop", 0.0, 0.35), ("pop", 1.4, 0.35), ("pop", 2.6, 0.35), ("ding", 3.8, 0.3)],
    "free": [("pop", 0.0, 0.35), ("pop", 1.4, 0.35), ("pop", 3.0, 0.35)],
    "success": [("tada", 0.1, 0.35), ("sparkle", 0.4, 0.25)],
    "end": [],
}


def _duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


async def _voices(ep):
    clips = OUT / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    lines, t = [], 0.6
    for i, (scene, who, text) in enumerate(ep["lines"]):
        f = clips / f"{i:02d}.mp3"
        voice = VOICES[f"hero-{ep.get('hero_voice', 'male')}" if who == "hero" else who]
        for attempt in range(3):
            try:
                await edge_tts.Communicate(text, **voice).save(str(f))
                break
            except Exception as e:  # Edge TTS sometimes drops a request
                print(f"  voice retry {attempt + 1}: {e}")
                time.sleep(3)
        else:
            raise RuntimeError(f"voice failed for line {i}")
        d = _duration(f)
        lines.append({"scene": scene, "who": who, "text": text, "start": round(t, 2), "end": round(t + d, 2), "file": str(f)})
        t += d + GAP
    total = round(t + 1.5, 2)
    inputs, filters = [], []
    for i, item in enumerate(lines):
        inputs += ["-i", item["file"]]
        ms = int(item["start"] * 1000)
        filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(lines)))
    filters.append(f"{mix}amix=inputs={len(lines)}:normalize=0,apad=whole_dur={total}[out]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters),
                    "-map", "[out]", "-t", str(total), str(OUT / "voice.mp3")], check=True)
    timeline = {"total": total, "lines": lines}
    _mix_sounds(timeline)
    return timeline


def _segments(timeline):
    """Scene blocks as the page shows them: a scene starts 0.3 s before its first line."""
    segs = []
    for line in timeline["lines"]:
        start = max(0.0, line["start"] - 0.3)
        if not segs or segs[-1][0] != line["scene"]:
            if segs:
                segs[-1][2] = start
            segs.append([line["scene"], start, timeline["total"]])
    return segs


def _mix_sounds(timeline):
    """voice.mp3 + scene background sounds + one-off effects -> audio.m4a (voice stays on top)."""
    if not SFX.exists():
        (OUT / "voice.mp3").replace(OUT / "audio.mp3")
        return
    inputs, filters, labels = ["-i", str(OUT / "voice.mp3")], [], ["[0:a]"]
    n = 1
    segs = _segments(timeline)
    for i, (scene, start, end) in enumerate(segs):
        dur = end - start
        for name, vol in BEDS.get(scene, []):
            inputs += ["-stream_loop", "-1", "-i", str(SFX / f"{name}.mp3")]
            ms = int(start * 1000)
            filters.append(f"[{n}:a]atrim=0:{dur:.2f},asetpts=PTS-STARTPTS,volume={vol},"
                           f"afade=t=in:d=0.4,afade=t=out:st={max(0, dur - 0.5):.2f}:d=0.5,adelay={ms}|{ms}[b{n}]")
            labels.append(f"[b{n}]"); n += 1
        for name, at, vol in HITS.get(scene, []):
            if at < dur:
                inputs += ["-i", str(SFX / f"{name}.mp3")]
                ms = int((start + at) * 1000)
                filters.append(f"[{n}:a]volume={vol},adelay={ms}|{ms}[h{n}]")
                labels.append(f"[h{n}]"); n += 1
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first,alimiter=limit=0.95[out]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters),
                    "-map", "[out]", "-t", str(timeline["total"]), "-c:a", "libmp3lame", "-b:a", "192k",
                    str(OUT / "audio.mp3")], check=True)


def _record(timeline, ep):
    from playwright.sync_api import sync_playwright
    raw = OUT / "raw"
    raw.mkdir(exist_ok=True)
    for f in raw.glob("*.webm"):
        f.unlink()
    channel = os.environ.get("STORY_CHROME")  # "chrome" on a PC with Chrome; empty = Playwright's Chromium
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel or None, headless=True)
        t_ctx = time.time()
        ctx = browser.new_context(viewport={"width": 720, "height": 1280}, record_video_dir=str(raw),
                                  record_video_size={"width": 720, "height": 1280})
        page = ctx.new_page()
        page.goto((STORIES / "story.html").as_uri())
        page.wait_for_timeout(1200)
        offset = time.time() - t_ctx
        page.evaluate("([t, e]) => window.start(t, e)", [timeline, ep])
        page.wait_for_timeout(int(timeline["total"] * 1000) + 300)
        ctx.close()
        browser.close()
    video = OUT / "short.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{offset:.2f}", "-i", str(next(raw.glob("*.webm"))),
                    "-i", str(OUT / "audio.mp3"), "-vf", "scale=1080:1920:flags=lanczos,fps=30",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
                    "-t", str(timeline["total"]), str(video)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "3", "-i", str(video), "-frames:v", "1",
                    "-vf", "scale=720:1280", str(OUT / "thumb.png")], check=True)
    return video


def _script(ep):
    title = f"{ep['emoji']} {ep['title']} | సింహం నాన్న కథలు #Shorts"
    desc = (f"నాన్న సింహం పిల్ల సింహానికి చెప్పిన కథ 🦁🌙 ఈ రోజు: {ep['hero_name']} {ep['emoji']}\n\n"
            f"{ep['tool_line']}\n💸 అంతా ఫ్రీ • యాప్ install అక్కర్లేదు • ఫైల్స్ మీ ఫోన్‌లోనే\n\n"
            f"👉 https://pdfdon.com\n\n#PDFDonTelugu #TeluguStory #TeluguKathalu #pdfdon #Shorts")
    tags = ["pdfdon", "pdfdon telugu", "telugu story", "telugu kathalu", "animal story telugu",
            "simham kathalu", "kids story telugu", "telugu tech", ep["hero_name"]]
    return {"title": title[:100], "description": desc, "tags": tags}


def _episodes():
    return json.loads((STORIES / "episodes.json").read_text(encoding="utf-8"))


def _load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _output(key, value):
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def _build(ep, out):
    """Makes one episode's vertical video in folder `out`; returns the mp4 path."""
    global OUT
    OUT = out
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Episode: {ep['id']} - {ep['title']}")
    timeline = asyncio.run(_voices(ep))
    print(f"  voice: {timeline['total']} s")
    return _record(timeline, ep)


def _stamp(sec):
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def _make_long(eps, videos, out):
    """Joins the episodes into one 16:9 video: the vertical story in the middle on a blurred copy of itself."""
    parts = []
    for i, v in enumerate(videos):
        wide = out / f"wide{i}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(v), "-filter_complex",
                        "[0:v]scale=1920:-2,crop=1920:1080,boxblur=30:3,eq=brightness=-0.12[bg];"
                        "[0:v]scale=-2:1080[fg];[bg][fg]overlay=(W-w)/2:0,fps=30[v]",
                        "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21",
                        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", str(wide)], check=True)
        parts.append(wide)
    inputs = sum((["-i", str(p)] for p in parts), [])
    joined = "".join(f"[{i}:v][{i}:a]" for i in range(len(parts)))
    video = out / "long.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex",
                    f"{joined}concat=n={len(parts)}:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21", "-c:a", "aac", "-b:a", "160k", str(video)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "3", "-i", str(video), "-frames:v", "1",
                    "-vf", "scale=1280:720", str(out / "thumb.png")], check=True)
    chapters, t = [], 0.0
    for ep, v in zip(eps, videos):
        chapters.append(f"{_stamp(t)} {ep['emoji']} {ep['title']}")
        t += _duration(v)
    names = ", ".join(e["hero_name"] for e in eps)
    script = {
        "title": f"🦁 సింహం నాన్న కథలు: {names} | pdfdon.com"[:100],
        "description": ("నాన్న సింహం పిల్ల సింహానికి చెప్పిన కథలు 🦁🌙 ప్రతి కథలో ఒక ఫ్రీ pdfdon.com టూల్!\n\n"
                        + "\n".join(chapters) + "\n\n"
                        + "\n\n".join(f"{e['emoji']} {e['hero_name']}:\n{e['tool_line']}" for e in eps)
                        + "\n\n💸 అంతా ఫ్రీ • యాప్ install అక్కర్లేదు • ఫైల్స్ మీ ఫోన్‌లోనే\n👉 https://pdfdon.com\n\n"
                        "#PDFDonTelugu #TeluguStory #TeluguKathalu #pdfdon"),
        "tags": ["pdfdon", "pdfdon telugu", "telugu stories", "telugu kathalu", "animal stories telugu",
                 "simham kathalu", "kids stories telugu", "telugu moral stories", "telugu tech"],
    }
    return video, script


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["short", "long"], default="short")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--id", default="")
    args = ap.parse_args()
    episodes = _episodes()

    if args.kind == "short":
        done = _load(DONE)
        ep = next((e for e in episodes if e["id"] == args.id), None) if args.id else \
            next((e for e in episodes if e["id"] not in done), None)
        if not ep:
            print("All story episodes are used - add more to stories/episodes.json")
            return
        out = ROOT / "out_story"
        video = _build(ep, out)
        script = _script(ep)
    else:
        done = _load(DONE_LONG)
        eps = [e for e in episodes if e["id"] not in done][:3]
        if len(eps) < 2:
            print("Not enough unused episodes for a long video - add more to stories/episodes.json")
            return
        out = ROOT / "out_story"
        videos = [_build(e, out / f"ep{i}") for i, e in enumerate(eps)]
        video, script = _make_long(eps, videos, out)
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  video: {video} ({_duration(video):.0f} s)")
    if args.dry_run:
        print("Dry run - not uploading")
        return

    from . import instagram, youtube_upload
    thumb = (out / "thumb.png") if args.kind == "long" else (OUT / "thumb.png")
    video_id = youtube_upload.upload(video, thumb, script, privacy="public")
    print(f"YouTube: https://youtu.be/{video_id}")
    ids = [ep["id"]] if args.kind == "short" else [e["id"] for e in eps]
    done += [i for i in ids if i not in done]
    (DONE if args.kind == "short" else DONE_LONG).write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    _output("saved", "true")
    _output("video_id", video_id)
    if args.kind == "short" and instagram.configured():
        try:
            print(f"Instagram: {instagram.publish(video, script)}")
        except Exception as e:  # YouTube is already done; do not fail the run over the Reel
            print(f"Instagram failed: {e}")


if __name__ == "__main__":
    main()
