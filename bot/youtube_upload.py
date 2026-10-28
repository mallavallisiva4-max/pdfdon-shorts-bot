"""Uploads the Short to YouTube as PRIVATE. You check it in YouTube Studio and make it Public."""
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
SECRETS = ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")
EDUCATION = "27"


def configured():
    return all(os.environ.get(k) for k in SECRETS)


def _client():
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(video, thumbnail, script):
    """Returns the new video id."""
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
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
        },
    }
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", chunksize=-1, resumable=True),
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    video_id = response["id"]
    print(f"  uploaded (private): https://youtu.be/{video_id}")

    try:
        youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail))).execute()
    except HttpError as e:  # needs a phone-verified channel; the video is fine without it
        print(f"  thumbnail not set ({e.status_code}) - verify the channel at youtube.com/verify")
    return video_id
