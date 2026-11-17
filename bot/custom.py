"""Uploads a hand-made video (not made by the bot) to YouTube and Instagram.

The folder must hold short.mp4, script.json (title, description, tags) and optionally thumb.png.

    python -m bot.custom custom/lion-story
"""
import json
import pathlib
import sys

from . import instagram, youtube_upload


def main():
    folder = pathlib.Path(sys.argv[1])
    video = folder / "short.mp4"
    script = json.loads((folder / "script.json").read_text(encoding="utf-8"))
    thumb = folder / "thumb.png"
    print(f"Uploading: {script['title']}")

    if youtube_upload.configured():
        video_id = youtube_upload.upload(video, thumb if thumb.exists() else video, script, privacy="public")
        print(f"YouTube: https://youtube.com/shorts/{video_id}")
    else:
        print("YouTube secrets missing - skipped")

    if instagram.configured():
        print(f"Instagram: {instagram.publish(video, script)}")
    else:
        print("Instagram secrets missing - skipped")


if __name__ == "__main__":
    main()
