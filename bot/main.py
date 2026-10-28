"""PDFDon Telugu Shorts bot.

topic -> Claude script -> Telugu voice -> pdfdon.com screenshots -> MP4 -> YouTube (private)

    python -m bot.main --dry-run            # make the video only, no upload
    python -m bot.main --topic gst-calculator
"""
import argparse
import datetime
import json
import os
import pathlib
import shutil

import yaml

from . import capture, render, script_writer, voice, youtube_upload

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "done.json"
OUT = ROOT / "out"


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
    ap.add_argument("--dry-run", action="store_true", help="make the video but do not upload")
    ap.add_argument("--topic", default="", help="topic id from topics.yaml")
    args = ap.parse_args()

    topics = yaml.safe_load((ROOT / "topics.yaml").read_text(encoding="utf-8"))["topics"]
    done = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else []
    topic = pick_topic(topics, done, args.topic.strip())
    print(f"Topic: {topic['id']}")

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir()

    print("1/5 script")
    earlier = [d["title"] for d in done if d["topic"] == topic["id"]]
    script = script_writer.write(topic, earlier)
    (OUT / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  title: {script['title']}")

    print("2/5 voice")
    clips = voice.synthesize([script[p]["narration"] for p in script_writer.PARTS], OUT / "audio")

    print("3/5 screenshots")
    shots, problems = capture.capture(topic, OUT / "shots", ROOT / "assets")

    print("4/5 video")
    video, thumb = render.build(script, shots, clips, OUT, ROOT / "assets", topic["te_name"])

    if args.dry_run:
        print("5/5 upload skipped (dry run). Download the 'short' artifact to watch it.")
        summary(f"### Test run: {script['title']}\nDownload the **short** artifact below to watch the video.")
        return

    video_id = None
    if youtube_upload.configured():
        # Public by default; private when a main step on the site failed, so a human looks first.
        privacy = os.environ.get("YT_PRIVACY", "public")
        if problems:
            privacy = "private"
            print(f"  steps failed on the site ({', '.join(problems)}) - uploading as private")
        print(f"5/5 upload ({privacy})")
        video_id = youtube_upload.upload(video, thumb, script, privacy)
        studio = f"https://studio.youtube.com/video/{video_id}/edit"
        if privacy == "public":
            summary(f"### Published: {script['title']}\nhttps://youtu.be/{video_id} · Studio: {studio}")
        else:
            reason = f" (failed steps: {', '.join(problems)})" if problems else ""
            summary(
                f"### Uploaded as PRIVATE{reason}: {script['title']}\n"
                f"Check it, then make it Public: {studio}"
            )
    else:
        print("5/5 YouTube secrets not set - video kept as the 'short' artifact for manual upload.")
        summary(
            f"### Ready to upload by hand: {script['title']}\n"
            "Download the **short** artifact below. Title, description and tags are in script.json."
        )

    # Remember the topic either way, so the next run moves on to a new one.
    done.append({
        "topic": topic["id"],
        "title": script["title"],
        "video_id": video_id,
        "date": datetime.date.today().isoformat(),
    })
    STATE.write_text(json.dumps(done, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    github_output(saved="true", video_id=video_id or "manual")


if __name__ == "__main__":
    main()
