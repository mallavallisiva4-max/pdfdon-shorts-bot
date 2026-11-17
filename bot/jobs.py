"""Daily job-notification post (6 PM): a Telugu job card to Instagram and a short video to YouTube.

Facts come from Gemini with Google Search, asked to confirm each notification on the official
website. A job is used only if its last date is still ahead, its official site is a government /
public-sector domain that answers, and it was not posted before. Text is written in our own words.
News sites are never copied (Eenadu, for example, blocks AI use in robots.txt; Google honours it).

    python -m bot.jobs                 # find, make, post
    python -m bot.jobs --dry-run       # find and make only
    python -m bot.jobs --sample        # make from a built-in sample (no Gemini), for testing the look
"""
import argparse
import asyncio
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import urllib.parse
import urllib.request

import edge_tts

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
SFX = ROOT / "stories" / "sfx"
DONE = ROOT / "state" / "jobs_done.json"
OUT = ROOT / "out_jobs"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
OFFICIAL_SUFFIXES = (".gov.in", ".nic.in", ".ac.in", ".edu.in", ".res.in")
OFFICIAL_HOSTS = ("ibps.in", "sbi.co.in", "bankofbaroda.in", "eximbankindia.in", "powergrid.in", "rbi.org.in",
                  "rrbcdg.gov.in", "ssc.gov.in", "upsc.gov.in", "isro.gov.in", "drdo.gov.in", "aai.aero",
                  "licindia.in", "iocl.com", "ongcindia.com", "bel-india.in", "hal-india.co.in", "ntpc.co.in",
                  "nabard.org", "sidbi.in", "canarabank.com", "unionbankofindia.co.in", "pnbindia.in",
                  "indianbank.in", "bankofindia.co.in", "centralbankofindia.co.in", "idbibank.in", "tsrtc.telangana.gov.in")

SAMPLE = {"org": "ఆంధ్రప్రదేశ్ పబ్లిక్ సర్వీస్ కమిషన్ (APPSC)", "posts": "720", "post": "గ్రూప్-2 సర్వీసెస్ (ఎగ్జిక్యూటివ్, నాన్-ఎగ్జిక్యూటివ్)",
          "qual": "ఏదైనా డిగ్రీ", "last_date": "2026-11-30", "official_url": "https://psc.ap.gov.in", "age": "18–42 సంవత్సరాలు"}

SYSTEM = """You find NEW government job notifications useful for candidates from Andhra Pradesh and Telangana:
state jobs (APPSC, TGPSC, AP/TS police, DSC, health, courts, district recruitment) and all-India jobs
(SSC, RRB, UPSC, IBPS, SBI, RBI, public sector banks and PSUs, defence). Use Google Search.
Rules:
- Only notifications whose application LAST DATE is after {today}.
- Confirm each one on the OFFICIAL website of the recruiting body; give that official URL (a gov.in / nic.in / ac.in
  site or the organisation's own site). Never give a news, coaching or job-portal site as official_url.
- Facts only, written in your own simple Telugu words. Do not copy sentences from any news site.
- If a number or date is not confirmed, leave the job out.
Answer with ONLY a JSON array (no other text) of up to 6 objects:
{{"org": "organisation name in Telugu (short English abbreviation in brackets)", "posts": "total vacancies as digits",
 "post": "post name(s) in Telugu, short", "qual": "qualification in Telugu, short", "age": "age limit in Telugu or empty",
 "last_date": "YYYY-MM-DD", "official_url": "https://..."}}"""


def _today():
    return dt.datetime.now(IST).date()


def _host(url):
    return (urllib.parse.urlparse(url).hostname or "").lower().removeprefix("www.")


def _official(url):
    h = _host(url)
    return bool(h) and (h.endswith(OFFICIAL_SUFFIXES) or h in OFFICIAL_HOSTS or any(h.endswith("." + o) for o in OFFICIAL_HOSTS))


def _reachable(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status < 400
    except Exception as e:  # some government sites block bots or have bad certificates
        print(f"    {url} not reachable ({type(e).__name__})")
        return False


def _key(j):
    return f"{_host(j['official_url'])}|{j['posts']}|{j['last_date']}"


EXTRACT_SYSTEM = """You read an official Indian government recruitment notification (text from its PDF) and
pull out the key facts for a Telugu job card. Use ONLY what the text says; never guess.
- posts: total number of vacancies as digits (sum if the text gives a total; "" if not stated)
- last_date: last date for submitting the online application, as YYYY-MM-DD ("" if not stated)
- post: post name(s) in simple Telugu, short (keep English abbreviations in brackets)
- qual: educational qualification in simple Telugu, one short line
- age: age limit in Telugu, short ("" if not stated)
- is_recruitment: false if this is not a new recruitment notification (results, corrigendum, exam schedule, etc.)
Write the Telugu in your own words."""

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "is_recruitment": {"type": "boolean"},
        "posts": {"type": "string"},
        "last_date": {"type": "string"},
        "post": {"type": "string"},
        "qual": {"type": "string"},
        "age": {"type": "string"},
    },
    "required": ["is_recruitment", "posts", "last_date", "post", "qual", "age"],
}


def _date_in_text(iso, text):
    """The date must really be printed in the notification (dd/mm/yyyy, dd-mm-yyyy, dd.mm.yyyy)."""
    d = dt.date.fromisoformat(iso)
    pats = [f"{d.day:02d}{s}{d.month:02d}{s}{d.year}" for s in "/-."] + [f"{d.day}{s}{d.month}{s}{d.year}" for s in "/-."]
    return any(p in text for p in pats)


def find_job(done):
    """First still-open official notification (APPSC / TGPSC) not posted before, with checked facts."""
    from . import gemini, job_sources
    today = _today()
    tried = 0
    for c in job_sources.candidates():
        key = f"{c['source']}:{c['id']}"
        if key in done:
            continue
        if c["end_date"]:
            try:
                if dt.datetime.strptime(c["end_date"], "%d/%m/%Y").date() <= today:
                    continue  # closed (TGPSC gives the date in its list)
            except ValueError:
                pass
        if tried >= 6:
            break
        tried += 1
        print(f"  checking {key}: {c['title'][:90]}")
        try:
            text = c.get("text") or job_sources.pdf_text(c["url"])
        except Exception as e:
            print(f"    PDF not readable ({type(e).__name__})"); continue
        if len(text) < 500:
            print("    PDF has no text (scanned) - skipped"); continue
        facts = gemini.ask_json(EXTRACT_SYSTEM, f"Notification title: {c['title']}\n\n{text}", EXTRACT_SCHEMA)
        if not facts or not facts.get("is_recruitment"):
            print("    not a recruitment notification / no answer"); continue
        posts = str(facts.get("posts", "")).replace(",", "").strip()
        last = str(facts.get("last_date", ""))[:10]
        if not posts.isdigit() or int(posts) < 1:
            print("    vacancies not stated - skipped"); continue
        if not re.search(rf"(?<!\d){posts}(?!\d)", text.replace(",", "")):
            print(f"    {posts} not found in the PDF - skipped"); continue
        try:
            if dt.date.fromisoformat(last) <= today + dt.timedelta(days=1):
                print(f"    last date {last} passed or too close"); continue
        except ValueError:
            print("    no valid last date - skipped"); continue
        if not _date_in_text(last, text):
            print(f"    last date {last} not found in the PDF - skipped"); continue
        return {"key": key, "org": c["org"], "posts": posts, "post": facts["post"], "qual": facts["qual"],
                "age": facts.get("age", ""), "last_date": last, "official_url": c["site"], "pdf": c["url"]}
    return None


def _old_find_job(done):
    """Unused: Gemini + Google Search (needs a billed key). Kept for later."""
    from . import gemini
    today = _today()
    text, sources = gemini.ask_search(SYSTEM.format(today=today.isoformat()),
                                      f"Today is {today.isoformat()}. List the newest job notifications as JSON.")
    if not text:
        print("Gemini gave no answer")
        return None
    m = re.search(r"\[.*\]", text, re.S)
    try:
        jobs = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        print("Gemini answer was not valid JSON")
        return None
    print(f"  {len(jobs)} candidates")
    for j in jobs:
        try:
            last = dt.date.fromisoformat(str(j.get("last_date", ""))[:10])
        except ValueError:
            print(f"    skip {j.get('org')}: bad date"); continue
        if last <= today + dt.timedelta(days=1):
            print(f"    skip {j.get('org')}: last date {last} too close"); continue
        if not str(j.get("posts", "")).replace(",", "").isdigit():
            print(f"    skip {j.get('org')}: posts not a number"); continue
        url = str(j.get("official_url", ""))
        if not _official(url):
            print(f"    skip {j.get('org')}: {url} is not an official site"); continue
        if _key(j) in done:
            print(f"    skip {j.get('org')}: already posted"); continue
        if not _reachable(url):
            continue
        j["posts"] = str(j["posts"]).replace(",", "")
        return j
    return None


def _date_te(iso):
    d = dt.date.fromisoformat(iso[:10])
    return d.strftime("%d-%m-%Y")


async def _voice(text, path):
    await edge_tts.Communicate(text, voice="te-IN-MohanNeural", rate="+0%").save(str(path))


def _duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def make(job):
    from playwright.sync_api import sync_playwright
    OUT.mkdir(exist_ok=True)
    fields = {"org": job["org"], "posts": job["posts"], "post": job["post"], "qual": job["qual"],
              "date": _date_te(job["last_date"]), "site": _host(job["official_url"]), "age": job.get("age", "")}
    channel = os.environ.get("STORY_CHROME")
    with sync_playwright() as p:
        b = p.chromium.launch(channel=channel or None, headless=True)
        page = b.new_page(viewport={"width": 1080, "height": 1350})
        page.goto((CARDS / "jobcard.html").as_uri())
        page.evaluate("j => window.fill(j)", fields)
        page.wait_for_timeout(600)
        card = OUT / "job.jpg"
        page.screenshot(path=str(card), type="jpeg", quality=92)
        page = b.new_page(viewport={"width": 1080, "height": 1920})
        page.goto((CARDS / "jobshort.html").as_uri())
        page.evaluate("c => window.fill(c)", {"card": card.as_uri(), "when": _today().strftime("%d-%m-%Y")})
        page.wait_for_timeout(800)
        frame = OUT / "frame.png"
        page.screenshot(path=str(frame))
        b.close()

    say = (f"{job['org']}. {job['post']}. మొత్తం {job['posts']} పోస్టులు. అర్హత: {job['qual']}. "
           f"దరఖాస్తుకు చివరి తేదీ {_date_te(job['last_date'])}. పూర్తి వివరాలు అధికారిక వెబ్‌సైట్‌లో చూసి, అక్కడే దరఖాస్తు చేయండి. "
           "ఎవరికీ డబ్బులు కట్టకండి.")
    voice = OUT / "voice.mp3"
    asyncio.run(_voice(say, voice))
    total = round(_duration(voice) + 2.5, 2)
    video = OUT / "job.mp4"
    bed = SFX / "newsbed.mp3"
    # inputs: 0 = still frame, 1 = voice, 2 = music (if present)
    vid = "[0:v]scale=1080:1920,zoompan=z='min(zoom+0.0004,1.06)':d=1:s=1080x1920:fps=30[vid]"
    if bed.exists():
        inputs = ["-loop", "1", "-i", str(frame), "-i", str(voice), "-stream_loop", "-1", "-i", str(bed)]
        aud = (f"[1:a]adelay=600|600,apad[v];[2:a]volume=0.12,afade=t=out:st={total - 1.5:.2f}:d=1.5[m];"
               "[v][m]amix=inputs=2:normalize=0:duration=first[a]")
    else:
        inputs = ["-loop", "1", "-i", str(frame), "-i", str(voice)]
        aud = "[1:a]adelay=600|600,apad[a]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", f"{vid};{aud}",
                    "-map", "[vid]", "-map", "[a]", "-t", str(total), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "22", "-c:a", "aac", "-b:a", "160k", str(video)], check=True)
    return card, video


def texts(job):
    date = _date_te(job["last_date"])
    title = f"📢 {job['org']}: {job['posts']} ఉద్యోగాలు | చివరి తేదీ {date} #Shorts"
    desc = (f"{job['org']}\n💼 పోస్టు: {job['post']}\n👥 ఖాళీలు: {job['posts']}\n🎓 అర్హత: {job['qual']}\n"
            + (f"🎂 వయసు: {job['age']}\n" if job.get("age") else "")
            + f"⏰ చివరి తేదీ: {date}\n🌐 అధికారిక వెబ్‌సైట్: {job['official_url']}\n"
            + (f"📄 అధికారిక notification: {job['pdf']}\n" if job.get("pdf") else "") + "\n"
            "⚠️ Apply చేసే ముందు అధికారిక notification పూర్తిగా చదవండి. ఉద్యోగం కోసం ఎవరికీ డబ్బులు కట్టకండి.\n\n"
            "#TeluguJobs #GovtJobs #APJobs #TSJobs #JobNotification #Shorts")
    tags = ["telugu jobs", "govt jobs", "ap jobs", "ts jobs", "job notification", "sarkari naukri telugu"]
    return {"title": title[:100], "description": desc, "tags": tags}


def _output(key, value):
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()
    done = json.loads(DONE.read_text(encoding="utf-8")) if DONE.exists() else []
    job = SAMPLE if args.sample else find_job(done)
    if not job:
        print("No new, confirmed job today - nothing posted")
        return
    print(f"Job: {job['org']} | {job['posts']} | {job['last_date']} | {job['official_url']}")
    card, video = make(job)
    script = texts(job)
    (OUT / "post.json").write_text(json.dumps({"job": job, **script}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  made {card.name}, {video.name} ({_duration(video):.0f} s)")
    if args.dry_run or args.sample:
        print("Dry run - not posting")
        return
    from . import instagram, youtube_upload
    video_id = youtube_upload.upload(video, card, script, privacy="public")
    print(f"YouTube: https://youtube.com/shorts/{video_id}")
    done.append(job.get("key") or _key(job))
    DONE.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    _output("saved", "true")
    if instagram.configured():
        try:
            caption = script["description"].replace("#Shorts", "#Reels")
            print(f"Instagram: {instagram.publish_image(card, caption)}")
        except Exception as e:
            print(f"Instagram failed: {e}")


if __name__ == "__main__":
    main()
