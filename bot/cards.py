"""Daily Way2News-style Instagram card: screenshot of a pdfdon.com tool on top, Telugu text below (1080x1350).

Picks the next tip from cards/tips.json that is not in state/cards_done.json.

    python -m bot.cards            # make + post the next card
    python -m bot.cards --dry-run  # make only (out_cards/card.jpg)
    python -m bot.cards --id compress-pdf
"""
import argparse
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
DONE = ROOT / "state" / "cards_done.json"
OUT = ROOT / "out_cards"
TAG = "💡 ఫ్రీ టూల్ టిప్"
HASHTAGS = "#PDFDonTelugu #Telugu #TeluguTech #FreeTools #pdfdon"


def _render(tip, out):
    from playwright.sync_api import sync_playwright
    channel = os.environ.get("STORY_CHROME")  # "chrome" on a PC; empty = Playwright's Chromium
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel or None, headless=True)
        page = browser.new_page(viewport={"width": 540, "height": 380}, device_scale_factor=2)
        page.goto(f"https://pdfdon.com/tools/{tip['id']}/", wait_until="networkidle", timeout=60000)
        # hide the sticky site header so it does not cover the tool, then start the picture at the breadcrumbs
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('body *')) {
                const s = getComputedStyle(el);
                if ((s.position === 'sticky' || s.position === 'fixed') && el.getBoundingClientRect().top < 5) el.style.display = 'none';
            }
            const h = document.querySelector('h1');
            if (h) window.scrollTo(0, h.getBoundingClientRect().top + scrollY - 50);
        }""")
        page.wait_for_timeout(1200)
        shot = out / "shot.png"
        page.screenshot(path=str(shot))
        card = browser.new_page(viewport={"width": 1080, "height": 1350})
        card.goto((CARDS / "card.html").as_uri())
        card.evaluate("c => window.fill(c)", {"tag": TAG, "title": tip["title"], "text": tip["text"], "image": shot.as_uri()})
        card.wait_for_timeout(800)
        jpg = out / "card.jpg"
        card.screenshot(path=str(jpg), type="jpeg", quality=92)
        browser.close()
    return jpg


def _caption(tip):
    return (f"{tip['title']}\n\n{tip['text']}\n\n"
            f"👉 pdfdon.com/tools/{tip['id']} (link in bio)\n"
            "రోజూ ఒక ఉపయోగపడే ఫ్రీ టూల్. Save చేసుకోండి, అవసరమైన వాళ్ళకి share చేయండి 🙏\n\n" + HASHTAGS)


def _output(key, value):
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--id", default="")
    args = ap.parse_args()
    tips = json.loads((CARDS / "tips.json").read_text(encoding="utf-8"))
    done = json.loads(DONE.read_text(encoding="utf-8")) if DONE.exists() else []
    if args.id:
        tip = next(t for t in tips if t["id"] == args.id)
    else:
        tip = next((t for t in tips if t["id"] not in done), None)
        if not tip:  # all used: start the round again
            done, tip = [], tips[0]
    OUT.mkdir(exist_ok=True)
    print(f"Card: {tip['id']} - {tip['title']}")
    jpg = _render(tip, OUT)
    (OUT / "caption.txt").write_text(_caption(tip), encoding="utf-8")
    print(f"  made {jpg}")
    if args.dry_run:
        print("Dry run - not posting")
        return
    from . import instagram
    instagram.publish_image(jpg, _caption(tip))
    done.append(tip["id"])
    DONE.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    _output("saved", "true")


if __name__ == "__main__":
    main()
