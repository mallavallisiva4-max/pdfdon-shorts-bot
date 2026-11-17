"""Checks which official job sites can be reached from GitHub's servers (prints status and size)."""
import socket
from .job_sources import fetch

URLS = [
    "https://portal-psc.ap.gov.in/HomePages/RecruitmentNotifications.aspx",
    "https://psc.ap.gov.in/",
    "https://psc.ap.gov.in/Documents/NotificationDocuments/",
    "https://slprb.ap.gov.in/",
    "https://hmfw.ap.gov.in/",
    "https://apdsc.apcfss.in/",
    "https://guntur.ap.gov.in/notice_category/recruitment/",
    "https://krishna.ap.gov.in/notice_category/recruitment/",
    "https://visakhapatnam.ap.gov.in/notice_category/recruitment/",
    "https://www.ap.gov.in/",
    "https://upsc.gov.in/recruitment/recruitment-advertisement",
    "https://ssc.gov.in/",
]

for u in URLS:
    host = u.split("/")[2]
    try:
        ip = socket.gethostbyname(host)
    except OSError as e:
        print(f"DNS FAIL  {u}  ({e})")
        continue
    try:
        data = fetch(u, limit=2_000_000)
        print(f"OK {len(data):>8}  {u}  [{ip}]")
    except Exception as e:
        print(f"FAIL      {u}  [{ip}] {type(e).__name__}: {str(e)[:80]}")
