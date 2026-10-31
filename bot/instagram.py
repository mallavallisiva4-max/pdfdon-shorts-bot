"""Posts the Short to Instagram as a Reel.

Works with either kind of token in IG_ACCESS_TOKEN (IG_USER_ID is the Instagram account's id):
- Facebook Page token ("EAA..."), from the Instagram API with Facebook Login: calls go to
  graph.facebook.com and the MP4 is uploaded directly (resumable upload). Page tokens made from a
  long-lived user token do not expire.
- Instagram user token ("IG..."), from the Instagram API with Instagram Login: calls go to
  graph.instagram.com, and Instagram fetches the MP4 from a temporary GitHub Release of this public
  repository, deleted after the Reel is posted. The token is refreshed on every run."""
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = os.environ.get("IG_API_VERSION", "v26.0")
CAPTION_MAX = 2200


def configured():
    return bool(os.environ.get("IG_ACCESS_TOKEN") and os.environ.get("IG_USER_ID"))


def _instagram_login(token):
    return token.startswith("IG")


def _graph(token):
    host = "graph.instagram.com" if _instagram_login(token) else "graph.facebook.com"
    return f"https://{host}/{API_VERSION}"


def _send(req):
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Instagram {req.full_url.split('?')[0]}: {e.code} {e.read().decode()[:300]}") from None


def _call(token, method, path, **params):
    params["access_token"] = token
    url = f"{_graph(token)}/{path}"
    data = urllib.parse.urlencode(params)
    if method == "GET":
        return _send(urllib.request.Request(f"{url}?{data}"))
    return _send(urllib.request.Request(url, data=data.encode(), method="POST"))


def _refresh(token):
    """Instagram Login tokens last 60 days; refreshing extends them. Page tokens need nothing."""
    if not _instagram_login(token):
        return token
    try:
        r = _send(urllib.request.Request(
            "https://graph.instagram.com/refresh_access_token?"
            + urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": token})))
        print(f"  Instagram token valid for {int(r.get('expires_in', 0)) // 86400} more days")
        if r.get("access_token") and r["access_token"] != token:
            print("  Instagram returned a new token - put it in the IG_ACCESS_TOKEN secret (SETUP-TELUGU.md step 6)")
            return r["access_token"]
    except RuntimeError as e:
        print(f"  token refresh skipped ({e})")
    return token


def caption(script):
    tags = "#PDFDonTelugu #Telugu #TeluguTech #Reels"
    text = f"{script['title'].replace('#Shorts', '').strip()}\n\n{script['description']}\n\n🔗 Link in bio: pdfdon.com\n{tags}"
    return text[:CAPTION_MAX]


def _container_direct(token, user, video, text):
    """Facebook Login: create the container, then send the file bytes to rupload.facebook.com."""
    container = _call(token, "POST", f"{user}/media", media_type="REELS", upload_type="resumable",
                      caption=text, share_to_feed="true")["id"]
    body = video.read_bytes()
    req = urllib.request.Request(
        f"https://rupload.facebook.com/ig-api-upload/{API_VERSION}/{container}", data=body, method="POST",
        headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(body))})
    _send(req)
    return container, None


def _container_hosted(token, user, video, text):
    """Instagram Login: Instagram fetches the file from a temporary GitHub Release."""
    repo = os.environ["GITHUB_REPOSITORY"]
    tag = f"ig-{os.environ.get('GITHUB_RUN_ID', int(time.time()))}"
    subprocess.run(["gh", "release", "create", tag, str(video), "--prerelease",
                    "--title", "Instagram upload (temporary)", "--notes", "Deleted after the Reel is posted."],
                   check=True)
    url = f"https://github.com/{repo}/releases/download/{tag}/{video.name}"
    try:
        container = _call(token, "POST", f"{user}/media", media_type="REELS", video_url=url,
                          caption=text, share_to_feed="true")["id"]
    except Exception:
        _unhost(tag)
        raise
    return container, tag


def _unhost(tag):
    if tag:
        subprocess.run(["gh", "release", "delete", tag, "--yes", "--cleanup-tag"], check=False)


def publish(video, script):
    """Returns the Reel's permalink. Raises RuntimeError when Instagram refuses it."""
    token = _refresh(os.environ["IG_ACCESS_TOKEN"])
    user = os.environ["IG_USER_ID"]
    make = _container_hosted if _instagram_login(token) else _container_direct
    container, tag = make(token, user, video, caption(script))
    try:
        # Instagram processes the video; check every 15 seconds for up to 10 minutes.
        for _ in range(40):
            time.sleep(15)
            status = _call(token, "GET", container, fields="status_code,status")
            code = status.get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Instagram could not process the video: {status.get('status')}")
        else:
            raise RuntimeError("Instagram took longer than 10 minutes to process the video")
        media = _call(token, "POST", f"{user}/media_publish", creation_id=container)["id"]
        link = _call(token, "GET", media, fields="permalink").get("permalink", "")
        print(f"  Instagram Reel posted: {link}")
        return link
    finally:
        _unhost(tag)
