"""Readers for official recruitment pages (public lists of notifications with PDF links).

Each reader returns newest-first dicts: {source, id, title, url (PDF), site, org, end_date (or "")}.
Government sites often have broken TLS chains, so certificates are not checked here; these are
public read-only pages and nothing is sent to them.
"""
import datetime as dt
import io
import re
import ssl
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130 PDFDonTeluguJobsBot"}
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def fetch(url, limit=15_000_000):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60, context=_CTX) as r:
        return r.read(limit)


def _clean(s):
    return re.sub(r"<[^>]+>|&nbsp;|\s+", " ", s).replace("&amp;", "&").strip()


def appsc():
    base = "https://portal-psc.ap.gov.in/HomePages/RecruitmentNotifications.aspx"
    html = fetch(base).decode("utf-8", "ignore")
    out = []
    for href, text in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', html, re.S | re.I):
        text = _clean(text)
        m = re.match(r"Notification No\.?\s*(\d+/\d{4})\s*,?\s*Dated\s*:?\s*(\d{2}/\d{2}/\d{4})", text, re.I)
        if not m:
            continue
        dated = dt.datetime.strptime(m.group(2), "%d/%m/%Y").date()
        if (dt.date.today() - dated).days > 60:
            continue  # old notification; its last date has long passed
        out.append({"source": "APPSC", "id": f"{m.group(1)}@{m.group(2)}", "title": text, "url": urllib.parse.urljoin(base, href),
                    "site": "https://psc.ap.gov.in", "org": "ఆంధ్రప్రదేశ్ పబ్లిక్ సర్వీస్ కమిషన్ (APPSC)", "end_date": "",
                    "dated": dated})
    out.sort(key=lambda d: d["dated"], reverse=True)
    for d in out:
        d.pop("dated")
    return out


def tgpsc():
    base = "https://websitenew.tgpsc.gov.in/directRecruitment"
    html = fetch(base).decode("utf-8", "ignore")
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        text = _clean(row)
        m = re.search(r"(\d{2}/[A-Z]{1,3}/[A-Z]{1,3}/\d{4})\s*-\s*(.+?)(?:Start Date|$)", text)
        pdf = re.search(r'href="(/preview/[^"]+)"', row)
        if not m or not pdf:
            continue
        end = re.search(r"End Date\s*(\d{2}/\d{2}/\d{4})", text)
        out.append({"source": "TGPSC", "id": m.group(1), "title": m.group(2).strip(), "url": urllib.parse.urljoin(base, pdf.group(1)),
                    "site": "https://www.tgpsc.gov.in", "org": "తెలంగాణ పబ్లిక్ సర్వీస్ కమిషన్ (TGPSC)",
                    "end_date": end.group(1) if end else ""})
    return out


def ap_inbox():
    """APPSC notifications sent by the user's laptop (AP sites block foreign servers). Text is included."""
    import json
    import pathlib
    path = pathlib.Path(__file__).resolve().parent.parent / "state" / "ap_inbox.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("items", [])


def appsc_any():
    """Direct read when the site answers (e.g. on the laptop), else the laptop's inbox."""
    try:
        return appsc()
    except Exception as e:
        print(f"  appsc direct read failed ({type(e).__name__}) - using the laptop inbox")
        return ap_inbox()


READERS = [appsc_any, tgpsc]


def candidates():
    """All sources, interleaved newest-first, so AP and TS take turns."""
    lists = []
    for read in READERS:
        try:
            items = read()
            print(f"  {read.__name__}: {len(items)} notifications")
            lists.append(items)
        except Exception as e:  # one broken site must not stop the others
            print(f"  {read.__name__} failed: {type(e).__name__}: {str(e)[:120]}")
    out = []
    for i in range(max((len(x) for x in lists), default=0)):
        out += [x[i] for x in lists if i < len(x)]
    return out


def pdf_text(url, pages=8, chars=14000):
    from pypdf import PdfReader
    data = fetch(url)
    if not data.startswith(b"%PDF"):
        return ""
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((p.extract_text() or "") for p in reader.pages[:pages])
    return re.sub(r"[ \t]+", " ", text)[:chars]
