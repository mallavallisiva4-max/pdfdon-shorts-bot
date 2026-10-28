"""PDFDon Telugu video bot.

topic -> Claude script -> Telugu voice -> screen recording of pdfdon.com -> MP4 -> YouTube

    python -m bot.main --kind short --dry-run     # make a Short only, no upload
    python -m bot.main --kind long --topic gst-calculator
"""
import argparse
import datetime
import json
import os
import pathlib
import shutil

import yaml

from . import captions, recorder, render, script_writer, translate, voice, youtube_upload

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "done.json"
OUT = ROOT / "out"

# Which recorded scene plays under each script part. Parts not listed are title cards.
SCENES = {
    "short": {"step1": "open", "step2": "action", "step3": "result"},
    "long": {"home": "home", "search": "search", "open": "open",
             "action": "action", "result": "result", "more": "more"},
}
PARTS = {"short": script_writer.PARTS, "long": script_writer.LONG_PARTS}
MIN_LONG_SECONDS = 180


def pick_topic(topics, done, forced):
    if forced:
        for t in topics:
            if t["id"] == forced:
                return t
        raise SystemExit(f"Unknown topic '{forced}'. Ids: {', '.join(t['id'] for t in topics)}")
    used = {t["id"]: sum(1 for d in done if d["topic"] == t["id"]) for t in topics}
    return min(topics, key=lambda t: used[t["id"]])


def github_output(**values):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            for k, v in values.items():
                f.write(f"{k}={v}\n")


def summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["short", "long"], default="short")
    ap.add_argument("--dry-run", action="store_true", help="make the video but do not upload")
    ap.add_argument("--topic", default="", help="topic id from topics.yaml")
    args = ap.parse_args()
    kind = args.kind

    topics = yaml.safe_load((ROOT / "topics.yaml").read_text(encoding="utf-8"))["topics"]
    done = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else []
    same_kind = [d for d in done if d.get("kind", "short") == kind]
    topic = pick_topic(topics, same_kind, args.topic.strip())
    print(f"{kind} video, topic: {topic['id']}")

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(exist_ok=True)

    print("1/5 script")
    earlier = [d["title"] for d in same_kind if d["topic"] == topic["id"]]
    if kind == "short":
        script = script_writer.write(topic, earlier)
    else:
        script = script_writer.write_long(topic, earlier)
        if script is None:
            msg = ("A long video needs a script writer: the GEMINI_API_KEY secret (free) or "
                   "ANTHROPIC_API_KEY. Check the log above for the error.")
            print(msg)
            summary(f"### Long video skipped\n{msg}")
            return
    (OUT / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  title: {script['title']}")

    parts = PARTS[kind]
    print("2/5 voice")
    clips = voice.synthesize([script[p]["narration"] for p in parts], OUT / "audio")

    print("3/5 screen recording")
    scene_of = SCENES[kind]
    timeline = [(scene_of[p], sec + render.PAD) for p, (_, sec) in zip(parts, clips) if p in scene_of]
    rec = recorder.record(topic, kind, timeline, OUT / "rec", ROOT / "assets")

    print("4/5 video")
    video, thumb, chapters, length = render.build(
        kind, script, parts, scene_of, clips, rec, OUT, ROOT / "assets", topic["te_name"])
    problems = list(rec["problems"])
    if kind == "long":
        script["description"] = script["description"].rstrip() + "\n\nChapters:\n" + chapters
        if length < MIN_LONG_SECONDS:
            problems.append(f"only {length:.0f} seconds long")
    (OUT / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

    # Subtitles (Telugu always, English when Claude translated it) and titles in other languages.
    narration = [script[p]["narration"] for p in parts]
    timings, at = [], 0.0
    for _, spoken in clips:
        timings.append((at, spoken))
        at += spoken + render.PAD
    subtitles = {"te": OUT / "subtitles.te.srt"}
    subtitles["te"].write_text(captions.srt(narration, timings), encoding="utf-8")
    localizations, english = translate.translate(script, narration)
    if english:
        subtitles["en"] = OUT / "subtitles.en.srt"
        subtitles["en"].write_text(captions.srt(english, timings), encoding="utf-8")
    if localizations:
        (OUT / "translations.json").write_text(json.dumps(localizations, ensure_ascii=False, indent=2),
                                               encoding="utf-8")
    print(f"  subtitles: {', '.join(subtitles)}; titles in {len(localizations or {})} more languages")

    if args.dry_run:
        print("5/5 upload skipped (dry run). Download the 'video' artifact to watch it.")
        summary(f"### Test run ({kind}): {script['title']}\nDownload the **video** artifact below to watch it.")
        return

    video_id = None
    if youtube_upload.configured():
        # Public by default; private when a main step failed, so a human looks first.
        privacy = os.environ.get("YT_PRIVACY", "public")
        if problems:
            privacy = "private"
            print(f"  problems ({', '.join(problems)}) - uploading as private")
        print(f"5/5 upload ({privacy})")
        video_id = youtube_upload.upload(video, thumb, script, privacy, localizations, subtitles)
        studio = f"https://studio.youtube.com/video/{video_id}/edit"
        if privacy == "public":
            summary(f"### Published ({kind}): {script['title']}\nhttps://youtu.be/{video_id} · Studio: {studio}")
        else:
            reason = f" ({', '.join(problems)})" if problems else ""
            summary(
                f"### Uploaded as PRIVATE{reason}: {script['title']}\n"
                f"Check it, then make it Public: {studio}"
            )
    else:
        print("5/5 YouTube secrets not set - video kept as the 'video' artifact for manual upload.")
        summary(
            f"### Ready to upload by hand: {script['title']}\n"
            "Download the **video** artifact below. Title, description and tags are in script.json."
        )

    # Remember the topic either way, so the next run moves on to a new one.
    done.append({
        "kind": kind,
        "topic": topic["id"],
        "title": script["title"],
        "video_id": video_id,
        "date": datetime.date.today().isoformat(),
    })
    STATE.write_text(json.dumps(done, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    github_output(saved="true", video_id=video_id or "manual")


if __name__ == "__main__":
    main()
