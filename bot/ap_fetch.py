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
import urllib.error
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
    print("Token paste చేయడానికి window లోపల MOUSE RIGHT-CLICK చేయండి (Ctrl+V పనిచేయదు). Token కనిపించదు.")
    raw = getpass.getpass("GitHub token paste చేసి Enter నొక్కండి: ")
    token = "".join(ch for ch in raw if ch.isprintable()).strip()
    if not token.startswith(("github_pat_", "ghp_")):
        print(f"❌ ఇది token లా లేదు ({len(token)} అక్షరాలు వచ్చాయి). github_pat_ తో మొదలయ్యే token ని right-click తో paste చేయండి.")
        return
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}", headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "pdfdon-ap-fetch"})
    try:
        urllib.request.urlopen(req, timeout=30).close()
    except urllib.error.HTTPError as e:
        print(f"❌ GitHub ఈ token ని ఒప్పుకోలేదు ({e.code}). Token పూర్తిగా copy అయిందో, pdfdon-shorts-bot repo ఎంచుకున్నారో చూడండి.")
        return
    TOKEN_FILE.write_text(token, encoding="utf-8")
    print(f"సేవ్ అయింది ✅  (token పనిచేస్తోంది)")


def main():
    if "--setup" in sys.argv:
        return setup()
    if not TOKEN_FILE.exists():
        log("no token - run: python -m bot.ap_fetch --setup"); return
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    done, _ = read_repo_json("state/jobs_done.json", token)
    done = set(done or [])
    items = []
    today = dt.date.today()
    found = []
    for read in (job_sources.appsc, job_sources.tgpsc):  # TGPSC too: it sometimes blocks GitHub as well
        try:
            found.append(read())
        except Exception as e:
            log(f"{read.__name__} failed: {type(e).__name__}")
    mixed = [x[i] for i in range(max((len(x) for x in found), default=0)) for x in found if i < len(x)]
    for c in mixed:
        key = f"{c['source']}:{c['id']}"
        if key in done:
            continue
        if c.get("end_date"):
            try:
                if dt.datetime.strptime(c["end_date"], "%d/%m/%Y").date() <= today:
                    continue
            except ValueError:
                pass
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
    log(f"sent {len(items)} AP/TS notifications to GitHub")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # keep a trace in the log; the task runs hidden
        log(f"ERROR {type(e).__name__}: {e}")
        raise
