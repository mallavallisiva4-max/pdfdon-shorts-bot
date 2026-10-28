"""Uploads the video to YouTube (public by default; see bot/main.py for when it stays private), with
translated titles/descriptions and subtitle tracks."""
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SECRETS = ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")
EDUCATION = "27"
SUBTITLE_NAMES = {"te": "తెలుగు", "en": "English"}


def configured():
    return all(os.environ.get(k) for k in SECRETS)


def _client():
    # No scopes here: the token keeps whatever was granted in the OAuth Playground
    # (youtube.upload, plus youtube.force-ssl for subtitles).
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _insert(youtube, video, body, parts):
    request = youtube.videos().insert(
        part=parts,
        body=body,
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", chunksize=-1, resumable=True),
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]


def upload(video, thumbnail, script, privacy="private", localizations=None, subtitles=None):
    """Returns the new video id. privacy is "public", "unlisted" or "private".
    localizations: {lang: {title, description}}; subtitles: {lang: srt_path}."""
    youtube = _client()
    body = {
        "snippet": {
            "title": script["title"][:100],
            "description": script["description"][:4900],
            "tags": script["tags"][:20],
            "categoryId": EDUCATION,
            "defaultLanguage": "te",
            "defaultAudioLanguage": "te",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    if localizations:
        try:
            video_id = _insert(youtube, video, {**body, "localizations": localizations},
                               "snippet,status,localizations")
            print(f"  titles in {len(localizations)} more languages")
        except HttpError as e:
            if e.status_code != 400:
                raise
            print(f"  translated titles refused by YouTube ({e.reason}) - uploading without them")
            video_id = _insert(youtube, video, body, "snippet,status")
    else:
        video_id = _insert(youtube, video, body, "snippet,status")
    print(f"  uploaded ({privacy}): https://youtu.be/{video_id}")

    try:
        youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail))).execute()
    except HttpError as e:  # needs a phone-verified channel; the video is fine without it
        print(f"  thumbnail not set ({e.status_code}) - verify the channel at youtube.com/verify")

    for lang, path in (subtitles or {}).items():
        try:
            youtube.captions().insert(
                part="snippet",
                body={"snippet": {"videoId": video_id, "language": lang,
                                  "name": SUBTITLE_NAMES.get(lang, lang), "isDraft": False}},
                media_body=MediaFileUpload(str(path), mimetype="application/octet-stream"),
            ).execute()
            print(f"  subtitles added: {lang}")
        except HttpError as e:
            # 403 means the token was made without the youtube.force-ssl scope (SETUP-TELUGU.md, step 5)
            print(f"  subtitles {lang} not added ({e.status_code}) - see SETUP-TELUGU.md step 5")
    return video_id
