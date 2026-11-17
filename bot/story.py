"""'సింహం నాన్న కథలు' - animated animal story Shorts about pdfdon.com tools.

Picks the next episode from stories/episodes.json that is not in state/stories_done.json, makes the
Telugu voices (Edge TTS), plays stories/story.html in Chromium while recording it, joins the two with
ffmpeg, then uploads to YouTube (public) and Instagram.

    python -m bot.story            # make + upload the next episode
    python -m bot.story --dry-run  # make only
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
DONE = ROOT / "state" / "stories_done.json"
OUT = ROOT / "out_story"
VOICES = {
    "father": dict(voice="te-IN-MohanNeural", rate="-8%", pitch="-6Hz"),
    "cub": dict(voice="te-IN-ShrutiNeural", rate="+5%", pitch="+30Hz"),
}
GAP = 0.45


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
        for attempt in range(3):
            try:
                await edge_tts.Communicate(text, **VOICES[who]).save(str(f))
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
    return {"total": total, "lines": lines}


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
                    "-i", str(OUT / "voice.mp3"), "-vf", "scale=1080:1920:flags=lanczos,fps=30",
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


def _pick(wanted):
    episodes = json.loads((STORIES / "episodes.json").read_text(encoding="utf-8"))
    done = json.loads(DONE.read_text(encoding="utf-8")) if DONE.exists() else []
    if wanted:
        return next(e for e in episodes if e["id"] == wanted), done
    for e in episodes:
        if e["id"] not in done:
            return e, done
    return None, done


def _output(key, value):
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--id", default="")
    args = ap.parse_args()

    ep, done = _pick(args.id)
    if not ep:
        print("All story episodes are used - add more to stories/episodes.json")
        return
    print(f"Episode: {ep['id']} - {ep['title']}")
    OUT.mkdir(exist_ok=True)
    timeline = asyncio.run(_voices(ep))
    print(f"  voice: {timeline['total']} s")
    video = _record(timeline, ep)
    script = _script(ep)
    (OUT / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  video: {video}")
    if args.dry_run:
        print("Dry run - not uploading")
        return

    from . import instagram, youtube_upload
    video_id = youtube_upload.upload(video, OUT / "thumb.png", script, privacy="public")
    print(f"YouTube: https://youtube.com/shorts/{video_id}")
    if ep["id"] not in done:
        done.append(ep["id"])
    DONE.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    _output("saved", "true")
    _output("video_id", video_id)
    if instagram.configured():
        try:
            print(f"Instagram: {instagram.publish(video, script)}")
        except Exception as e:  # YouTube is already done; do not fail the run over the Reel
            print(f"Instagram failed: {e}")


if __name__ == "__main__":
    main()
