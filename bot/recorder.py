"""Screen-records pdfdon.com in a real browser while the bot uses the tool like a person:
a visible cursor moves and taps, text is typed letter by letter, the page scrolls.

Each scene runs for as long as its narration, so the recording lines up with the voice.
Returns the recording, the second at which each scene starts, a few screenshots (for the
thumbnail) and the main steps that failed (so the video can be kept private)."""
import random
import re
import time

from playwright.sync_api import sync_playwright

SITE = "https://www.pdfdon.com"
# Buttons that start the tool's work. "Download" is left out on purpose.
ACTION = re.compile(
    r"resize|compress|convert|create|generate|calculate|make|remove|apply|start|process|preview|submit|scan",
    re.I,
)
CHOOSE = re.compile(r"choose|select|upload|browse|add (photo|image|file)", re.I)
CLOSE = re.compile(r"^(close|dismiss|×|✕|x)$|close (banner|announcement|notice)", re.I)
PREVIEW = "canvas, img[src^='blob:'], img[src^='data:']"
RESULT = "a[download], button:has-text('Download'), a:has-text('Download')"
SEARCH = "input[type=search], input[placeholder*=earch]"
FORM_INPUTS = (
    "input:not([type=file]):not([type=hidden]):not([type=checkbox]):not([type=radio])"
    ":not([type=button]):not([type=submit]):not([type=search])"
    ":not([placeholder*=earch]):not([role=combobox]), textarea"
)

LAYOUTS = {
    # Shorts: a phone. Long videos: a 1280x720 laptop screen.
    # Chromium records at the page's CSS size whatever the device scale, so the video size is the
    # viewport and render.py scales it up; the device scale only sharpens the thumbnail screenshots.
    "short": dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True,
                  has_touch=True, record_video_size={"width": 390, "height": 844}),
    "long": dict(viewport={"width": 1280, "height": 720}, device_scale_factor=1.5,
                 record_video_size={"width": 1280, "height": 720}),
}

# A round "finger" cursor drawn into every page, since a recording shows no mouse pointer.
CURSOR_JS = """
(() => {
  const add = () => {
    if (!document.body || document.getElementById('__cur')) return;
    const c = document.createElement('div');
    c.id = '__cur';
    c.style.cssText = 'position:fixed;left:0;top:0;width:28px;height:28px;margin:-14px 0 0 -14px;' +
      'border-radius:50%;background:rgba(226,35,26,.5);border:3px solid #fff;' +
      'box-shadow:0 2px 10px rgba(0,0,0,.45);z-index:2147483647;pointer-events:none;' +
      'transition:transform .7s cubic-bezier(.4,0,.2,1);transform:translate(50vw,55vh)';
    document.body.appendChild(c);
  };
  window.__cursorTo = (x, y) => { add(); const c = document.getElementById('__cur');
    if (c) c.style.transform = `translate(${x}px,${y}px)`; };
  window.__tap = () => { add(); const c = document.getElementById('__cur');
    if (c) c.animate([{boxShadow: '0 0 0 0 rgba(226,35,26,.8)'},
                      {boxShadow: '0 0 0 30px rgba(226,35,26,0)'}], {duration: 650}); };
  document.addEventListener('DOMContentLoaded', add);
  window.addEventListener('load', add);
})();
"""

# Visible things worth pointing at while the narration explains them.
POINTABLE_JS = """
() => [...document.querySelectorAll('main button, main input, main select, main label, main h2, main h3, main a, main table')]
  .map(e => e.getBoundingClientRect())
  .filter(r => r.width > 20 && r.height > 12 && r.top > 60 && r.bottom < innerHeight - 20)
  .map(r => [r.left + r.width / 2, r.top + r.height / 2])
"""


class Session:
    def __init__(self, page, topic, assets, shots_dir):
        self.page = page
        self.topic = topic
        self.assets = assets
        self.shots_dir = shots_dir
        self.t0 = time.monotonic()
        self.problems = []
        self.shots = {}
        self.rand = random.Random(topic["id"])

    def now(self):
        return time.monotonic() - self.t0

    def wait(self, seconds):
        self.page.wait_for_timeout(int(seconds * 1000))

    def attempt(self, label, fn, important=False):
        try:
            fn()
            return True
        except Exception as e:  # a missing element must not stop the video
            print(f"  record: {label} skipped ({type(e).__name__}: {str(e).splitlines()[0][:120]})")
            if important:
                self.problems.append(label)
            return False

    def visible(self, locator):
        return [el for el in locator.all() if el.is_visible()]

    def cursor_to(self, locator):
        locator.scroll_into_view_if_needed(timeout=5000)
        box = locator.bounding_box()
        if box:
            self.page.evaluate(f"window.__cursorTo({box['x'] + box['width'] / 2}, {box['y'] + box['height'] / 2})")
            self.wait(0.8)

    def tap(self, locator):
        self.cursor_to(locator)
        self.page.evaluate("window.__tap()")
        locator.click(timeout=5000)

    def scroll(self, dy, seconds=1.0):
        self.page.evaluate(f"window.scrollBy({{top: {dy}, behavior: 'smooth'}})")
        self.wait(seconds)

    def smooth_into_view(self, selector):
        self.page.evaluate(
            "(s) => { const e = document.querySelector(s); if (e) e.scrollIntoView({behavior: 'smooth', block: 'center'}); }",
            selector,
        )
        self.wait(1.2)

    def idle(self, until):
        """Keeps the screen alive until `until`: points at things, small scrolls."""
        while self.now() < until - 0.3:
            left = until - self.now()
            points = self.page.evaluate(POINTABLE_JS)
            if points and self.rand.random() < 0.7:
                x, y = self.rand.choice(points)
                self.page.evaluate(f"window.__cursorTo({x}, {y})")
                self.wait(min(left, self.rand.uniform(1.4, 2.4)))
            else:
                self.scroll(self.rand.choice([-180, 160, 220]), min(left, 1.5))

    def goto(self, url):
        self.page.goto(url, wait_until="networkidle", timeout=60000)
        self.wait(1.0)

        def close_banners():
            for button in self.visible(self.page.get_by_role("button", name=CLOSE)):
                button.click(timeout=3000)
            self.wait(0.4)
        self.attempt("close banner", close_banners, important=True)

    def shot(self, name):
        path = self.shots_dir / f"{name}.png"
        self.page.screenshot(path=str(path))
        self.shots[name] = path


# ---------------------------------------------------------------- scenes

def scene_home(s, end):
    s.page.evaluate("window.__cursorTo(innerWidth / 2, innerHeight / 3)")
    while s.now() < end - 2.5:
        s.scroll(300, min(2.2, end - s.now()))
    s.page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    s.wait(max(0, end - s.now()))


def scene_search(s, end):
    link = s.page.locator(f"a[href*='{s.topic['path'].rstrip('/')}']")
    # Type the tool's name exactly as the site writes it, so the search finds it.
    term = s.topic["path"].strip("/").split("/")[-1].replace("-", " ")
    if link.count():
        words = link.first.inner_text().split()
        if words and words[0].isupper() and len(words[0]) <= 4:
            words = words[1:]  # the icon label, e.g. "KB"
        term = " ".join(words[:3]) or term

    def search():
        # The sidebar "Find a tool" filter: wide, and it narrows the list to the one tool. The
        # header box is only ~100px wide on a laptop screen, so it is just the fallback.
        box = (s.visible(s.page.locator("input[placeholder^='Find a tool']"))
               or s.visible(s.page.locator(SEARCH)))[0]
        s.tap(box)
        box.press_sequentially(term, delay=120)
        s.wait(1.2)
        found = s.visible(s.page.locator(f"a[href*='{s.topic['path'].rstrip('/')}']"))
        if not found:
            return
        s.cursor_to(found[0])
        # Point at the result while the narration talks, then open it like a person would.
        s.wait(max(0, end - s.now() - 2.0))
        s.tap(found[0])
        s.page.wait_for_load_state("networkidle", timeout=20000)
    s.attempt("search", search)
    s.wait(max(0, end - s.now()))


def scene_open(s, end):
    if s.topic["path"].rstrip("/") not in s.page.url:
        s.goto(SITE + s.topic["path"])
    else:
        # Opened from the search result: close the banner here too.
        s.attempt("close banner", lambda: [b.click(timeout=3000) for b in
                                           s.visible(s.page.get_by_role("button", name=CLOSE))],
                  important=True)
    s.page.evaluate("window.__cursorTo(innerWidth / 2, innerHeight / 3)")
    s.wait(1.5)
    s.shot("open")
    s.attempt("show form", lambda: s.smooth_into_view(
        "main input[type=file], main form, main input, main textarea"))
    s.idle(end)


def scene_action(s, end):
    topic = s.topic
    if topic.get("upload"):
        file = str(s.assets / topic["upload"])

        def upload():
            buttons = s.visible(s.page.get_by_role("button", name=CHOOSE))
            if buttons:
                try:
                    with s.page.expect_file_chooser(timeout=5000) as chooser:
                        s.tap(buttons[0])
                    chooser.value.set_files(file)
                except Exception:
                    s.page.locator("input[type=file]").first.set_input_files(file, timeout=10000)
            else:
                s.page.locator("input[type=file]").first.set_input_files(file, timeout=10000)
            s.wait(2.5)
            s.attempt("preview", lambda: s.smooth_into_view(PREVIEW))
        s.attempt("upload", upload, important=True)

    if topic.get("fill"):
        def fill():
            area = s.page.locator("main").first if s.page.locator("main").count() else s.page
            boxes = s.visible(area.locator(FORM_INPUTS))
            if not boxes:
                raise LookupError("no input boxes found")
            for box, value in zip(boxes, topic["fill"]):
                s.tap(box)
                box.fill("")
                box.press_sequentially(str(value), delay=110)
                s.wait(0.4)
            s.page.keyboard.press("Tab")
            s.wait(0.8)
        s.attempt("fill", fill, important=True)

    s.shot("action")
    s.idle(end)


def scene_result(s, end):
    def press():
        buttons = s.visible(s.page.get_by_role("button", name=ACTION))
        if buttons:
            s.tap(buttons[0])
            s.wait(3.0)
    s.attempt("action button", press)

    def show():
        found = s.visible(s.page.locator(RESULT))
        if found:
            s.cursor_to(found[0])
        else:
            s.scroll(350, 1.2)
    s.attempt("result", show)
    s.shot("result")
    s.idle(end)


def scene_more(s, end):
    while s.now() < end - 3:
        s.scroll(320, min(2.6, end - s.now()))
    s.page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    s.wait(max(0, end - s.now()))


SCENES = {"home": scene_home, "search": scene_search, "open": scene_open,
          "action": scene_action, "result": scene_result, "more": scene_more}


def record(topic, layout, timeline, outdir, assets):
    """timeline: [(scene, seconds), ...] in order. Returns a dict with video, marks
    (scene -> start second in the video), shots and problems."""
    outdir.mkdir(parents=True, exist_ok=True)
    shots_dir = outdir / "shots"
    shots_dir.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(record_video_dir=str(outdir), locale="en-IN", **LAYOUTS[layout])
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        s = Session(page, topic, assets, shots_dir)

        # Load the first page before the timeline starts, so no blank loading screen is used.
        first = SITE + "/" if timeline[0][0] == "home" else SITE + topic["path"]
        s.goto(first)

        marks = {}
        for scene, seconds in timeline:
            start = s.now()
            marks[scene] = start
            SCENES[scene](s, start + seconds)
            print(f"  scene {scene}: {start:.1f}s -> {s.now():.1f}s (wanted {seconds:.1f}s)")

        video = page.video
        ctx.close()
        path = video.path()
        browser.close()

    return {"video": path, "marks": marks, "shots": s.shots, "problems": s.problems}
