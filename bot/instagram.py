"""Posts the Short to Instagram as a Reel (Instagram API with Instagram Login).

Instagram fetches the video from a public URL, so the MP4 is put on a temporary GitHub Release of
this (public) repository and the release is deleted after Instagram has taken the file.

Secrets: IG_ACCESS_TOKEN (long-lived Instagram user token) and IG_USER_ID."""
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.instagram.com"
CAPTION_MAX = 2200


def configured():
    return bool(os.environ.get("IG_ACCESS_TOKEN") and os.environ.get("IG_USER_ID"))


def _call(method, path, **params):
    url = f"{GRAPH}/{path}"
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Instagram {path}: {e.code} {e.read().decode()[:300]}") from None


def _refresh(token):
    """Extends the long-lived token by 60 days from today, so it does not run out while the
    bot keeps posting. Returns the token to use."""
    try:
        r = _call("GET", "refresh_access_token", grant_type="ig_refresh_token", access_token=token)
        days = int(r.get("expires_in", 0)) // 86400
        print(f"  Instagram token valid for {days} more days")
        if r.get("access_token") and r["access_token"] != token:
            print("  Instagram returned a new token - put it in the IG_ACCESS_TOKEN secret (SETUP-TELUGU.md step 6)")
            return r["access_token"]
    except RuntimeError as e:
        print(f"  token refresh skipped ({e})")
    return token


def _host(video, tag):
    """Uploads the MP4 to a temporary GitHub Release and returns its public download URL."""
    repo = os.environ["GITHUB_REPOSITORY"]
    subprocess.run(["gh", "release", "create", tag, str(video), "--prerelease",
                    "--title", "Instagram upload (temporary)", "--notes", "Deleted after the Reel is posted."],
                   check=True)
    return f"https://github.com/{repo}/releases/download/{tag}/{video.name}"


def _unhost(tag):
    subprocess.run(["gh", "release", "delete", tag, "--yes", "--cleanup-tag"], check=False)


def caption(script):
    tags = "#PDFDonTelugu #Telugu #TeluguTech #Reels"
    text = f"{script['title'].replace('#Shorts', '').strip()}\n\n{script['description']}\n\n🔗 Link in bio: pdfdon.com\n{tags}"
    return text[:CAPTION_MAX]


def publish(video, script):
    """Returns the Reel's permalink. Raises RuntimeError when Instagram refuses it."""
    token = _refresh(os.environ["IG_ACCESS_TOKEN"])
    user = os.environ["IG_USER_ID"]
    tag = f"ig-{os.environ.get('GITHUB_RUN_ID', int(time.time()))}"
    url = _host(video, tag)
    try:
        container = _call("POST", f"{user}/media", media_type="REELS", video_url=url,
                          caption=caption(script), share_to_feed="true", access_token=token)["id"]
        # Instagram downloads and processes the video; check every 15 seconds for up to 10 minutes.
        for _ in range(40):
            time.sleep(15)
            status = _call("GET", container, fields="status_code,status", access_token=token)
            code = status.get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Instagram could not process the video: {status.get('status')}")
        else:
            raise RuntimeError("Instagram took longer than 10 minutes to process the video")
        media = _call("POST", f"{user}/media_publish", creation_id=container, access_token=token)["id"]
        link = _call("GET", media, fields="permalink", access_token=token).get("permalink", "")
        print(f"  Instagram Reel posted: {link}")
        return link
    finally:
        _unhost(tag)
