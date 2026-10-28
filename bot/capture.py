"""Opens the tool on pdfdon.com in a phone-sized browser and takes three screenshots:
open (tool page), action (after upload / typing), result (after pressing the main button)."""
import re

from playwright.sync_api import sync_playwright

SITE = "https://www.pdfdon.com"
# Buttons that start the tool's work. "Download" is left out on purpose.
ACTION = re.compile(
    r"resize|compress|convert|create|generate|calculate|make|remove|apply|start|process|preview|submit|scan",
    re.I,
)
CLOSE = re.compile(r"^(close|dismiss|×|✕|x)$|close (banner|announcement|notice)", re.I)
PREVIEW ="canvas, img[src^='blob:'], img[src^='data:']"
RESULT = "a[download], button:has-text('Download'), a:has-text('Download')"


def _try(label, fn):
    """Runs one step; returns False when it failed (a missing element must not stop the video)."""
    try:
        fn()
        return True
    except Exception as e:
        print(f"  capture: {label} skipped ({type(e).__name__}: {str(e).splitlines()[0][:120]})")
        return False


def _visible(locator):
    return [el for el in locator.all() if el.is_visible()]


def capture(topic, outdir, assets):
    """Returns (shots, problems). problems lists the main steps that failed, so the video
    can be kept private for a human to check."""
    outdir.mkdir(parents=True, exist_ok=True)
    shots = {}
    problems = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="en-IN",
        )
        page = ctx.new_page()

        def shot(name):
            path = outdir / f"{name}.png"
            page.screenshot(path=str(path))
            shots[name] = path

        page.goto(SITE + topic["path"], wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)

        # Close the site's announcement banner so it does not end up in the video.
        def close_banners():
            for button in _visible(page.get_by_role("button", name=CLOSE)):
                button.click(timeout=3000)
            page.wait_for_timeout(500)
        if not _try("close banner", close_banners):
            problems.append("close banner")
        shot("open")

        if topic.get("upload"):
            def upload():
                page.locator("input[type=file]").first.set_input_files(str(assets / topic["upload"]), timeout=10000)
                page.wait_for_timeout(2500)
            if not _try("upload", upload):
                problems.append("upload")

        if topic.get("fill"):
            def fill():
                # Only the tool's own form: skip the header search box.
                area = page.locator("main").first if page.locator("main").count() else page
                boxes = _visible(area.locator(
                    "input:not([type=file]):not([type=hidden]):not([type=checkbox]):not([type=radio])"
                    ":not([type=button]):not([type=submit]):not([type=search])"
                    ":not([placeholder*=earch]):not([role=combobox]), textarea"
                ))
                if not boxes:
                    raise LookupError("no input boxes found")
                for box, value in zip(boxes, topic["fill"]):
                    box.fill(str(value))
                    box.dispatch_event("change")
                page.keyboard.press("Tab")
                page.wait_for_timeout(800)
            if not _try("fill", fill):
                problems.append("fill")

        def show_preview():
            found = _visible(page.locator(PREVIEW))
            if found:
                found[0].scroll_into_view_if_needed()
            else:
                page.mouse.wheel(0, 450)
            page.wait_for_timeout(700)
        _try("preview", show_preview)
        shot("action")

        def press_action():
            buttons = _visible(page.get_by_role("button", name=ACTION))
            if buttons:
                buttons[0].click(timeout=5000)
                page.wait_for_timeout(3000)
        _try("action button", press_action)

        def show_result():
            found = _visible(page.locator(RESULT))
            if found:
                found[0].scroll_into_view_if_needed()
                page.mouse.wheel(0, -250)
            else:
                page.mouse.wheel(0, 400)
            page.wait_for_timeout(700)
        _try("result", show_result)
        shot("result")

        browser.close()
    return shots, problems
