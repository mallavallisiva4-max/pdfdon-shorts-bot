"""Runs on the user's laptop (in India) because AP government sites block foreign servers.

Reads the APPSC recruitment list, downloads the newest notification PDFs not yet posted, takes their
text, and saves it to state/ap_inbox.json in the GitHub repo (via the GitHub API). The 6 PM
"Daily Jobs" workflow on GitHub then reads that inbox.

    python -m bot.ap_fetch --setup   # once: paste the GitHub token (input is hidden), saved for this Windows user
    python -m bot.ap_fetch           # daily (Task Scheduler, 5:30 PM)
"""
import base64
import datetime as dt
import getpass
import json
import pathlib
import sys
import urllib.request

from . import job_sources

REPO = "mallavallisiva4-max/pdfdon-shorts-bot"
TOKEN_FILE = pathlib.Path.home() / ".pdfdon_github_token"
LOG = pathlib.Path(__file__).resolve().parent.parent / "ap_fetch.log"
MAX_ITEMS = 8


def log(msg):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M} {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def gh(method, path, token, body=None):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                          "User-Agent": "pdfdon-ap-fetch"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise RuntimeError(f"GitHub {method} {path}: {e.code} {e.read()[:200]!r}") from None


def read_repo_json(path, token):
    meta = gh("GET", f"contents/{path}", token)
    if not meta:
        return None, None
    return json.loads(base64.b64decode(meta["content"]).decode("utf-8")), meta["sha"]


def setup():
    token = getpass.getpass("GitHub token paste చేసి Enter నొక్కండి (కనిపించదు): ").strip()
    if not token:
        print("Token ఇవ్వలేదు."); return
    gh("GET", "", token)  # check it works
    TOKEN_FILE.write_text(token, encoding="utf-8")
    print(f"సేవ్ అయింది: {TOKEN_FILE}  ✅")


def main():
    if "--setup" in sys.argv:
        return setup()
    if not TOKEN_FILE.exists():
        log("no token - run: python -m bot.ap_fetch --setup"); return
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    done, _ = read_repo_json("state/jobs_done.json", token)
    done = set(done or [])
    items = []
    for c in job_sources.appsc():
        key = f"{c['source']}:{c['id']}"
        if key in done:
            continue
        try:
            text = job_sources.pdf_text(c["url"])
        except Exception as e:
            log(f"PDF failed {key}: {type(e).__name__}"); continue
        if len(text) < 500:
            continue  # scanned PDF, no text
        items.append({**c, "text": text})
        if len(items) >= MAX_ITEMS:
            break
    inbox = {"updated": dt.datetime.now().isoformat(timespec="minutes"), "items": items}
    _, sha = read_repo_json("state/ap_inbox.json", token)
    body = {"message": f"AP inbox: {len(items)} notifications",
            "content": base64.b64encode(json.dumps(inbox, ensure_ascii=False, indent=1).encode("utf-8")).decode()}
    if sha:
        body["sha"] = sha
    gh("PUT", "contents/state/ap_inbox.json", token, body)
    log(f"sent {len(items)} AP notifications to GitHub")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # keep a trace in the log; the task runs hidden
        log(f"ERROR {type(e).__name__}: {e}")
        raise
