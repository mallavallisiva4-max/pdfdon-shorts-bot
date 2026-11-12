"""Posts an already-made Short to Instagram as a Reel, from the 'video' artifact of an earlier run.
Used by the "Repost Reel" workflow when the first try failed (for example an expired token).

    python -m bot.repost out
"""
import json
import pathlib
import sys

from . import instagram


def main():
    folder = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "out")
    video = folder / "short.mp4"
    if not video.exists():
        raise SystemExit(f"No short.mp4 in {folder} - that run made a long video or its artifact expired.")
    if not instagram.configured():
        raise SystemExit("IG_ACCESS_TOKEN / IG_USER_ID secrets are missing.")
    script = json.loads((folder / "script.json").read_text(encoding="utf-8"))
    print(f"Reposting: {script['title']}")
    link = instagram.publish(video, script)
    print(f"Done: {link}")


if __name__ == "__main__":
    main()
