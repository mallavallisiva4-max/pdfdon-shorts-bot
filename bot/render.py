"""Draws the 1080x1920 frames and the 1280x720 thumbnail as HTML (Chromium shapes Telugu
correctly, ffmpeg drawtext does not), then joins frames and voice into the final MP4 with ffmpeg."""
import base64
import html
import subprocess

from playwright.sync_api import sync_playwright

FONT = "'Noto Sans Telugu','Noto Sans','Noto Color Emoji',sans-serif"
PAD = 0.45  # seconds of silence after each narration line

BASE_CSS = f"""
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; overflow: hidden; font-family: {FONT}; }}
body {{ background: radial-gradient(circle at 70% 30%, #2a3560 0%, #141a30 60%, #0d1122 100%); color: #fff; }}
.logo {{ border-radius: 50%; border: 6px solid #fff; }}
"""


def _uri(path):
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/png;base64,{data}" if path.suffix == ".png" else f"data:image/jpeg;base64,{data}"


def _e(text):
    return html.escape(text)


def _card(logo, big, caption, sub):
    return f"""<html><head><style>{BASE_CSS}
    body {{ width:1080px; height:1920px; display:flex; flex-direction:column; align-items:center;
            justify-content:center; text-align:center; padding:0 80px; }}
    .big {{ margin-top:70px; font-size:{_big(big, (150, 124, 100))}px; font-weight:900; line-height:1.05; color:#ffd400;
            text-shadow:0 10px 0 rgba(0,0,0,.35); }}
    .cap {{ margin-top:60px; font-size:72px; font-weight:700; line-height:1.35; }}
    .sub {{ margin-top:70px; display:inline-block; background:#e2231a; padding:22px 48px;
            border-radius:24px; font-size:56px; font-weight:800; }}
    </style></head><body>
      <img class="logo" src="{logo}" width="300" height="300">
      <div class="big">{_e(big)}</div>
      <div class="cap">{_e(caption)}</div>
      <div class="sub">{_e(sub)}</div>
    </body></html>"""


def _step(logo, n, shot, caption):
    return f"""<html><head><style>{BASE_CSS}
    body {{ width:1080px; height:1920px; }}
    .top {{ height:170px; display:flex; align-items:center; gap:24px; padding:0 56px;
            background:rgba(0,0,0,.25); border-bottom:6px solid #e2231a; }}
    .top b {{ font-size:54px; }}
    .badge {{ margin-left:auto; background:#ffd400; color:#141a30; font-weight:900; font-size:46px;
              padding:10px 30px; border-radius:40px; }}
    .phone {{ position:absolute; left:50%; top:220px; width:640px; margin-left:-320px; padding:16px;
              background:#05070d; border-radius:56px; box-shadow:0 30px 70px rgba(0,0,0,.55); }}
    .phone img {{ display:block; width:100%; border-radius:42px; }}
    .cap {{ position:absolute; left:50px; right:50px; bottom:70px; background:#fff; color:#141a30;
            border-radius:36px; padding:34px 40px; text-align:center; font-size:66px; font-weight:800;
            line-height:1.3; border-bottom:14px solid #e2231a; }}
    </style></head><body>
      <div class="top"><img class="logo" src="{logo}" width="100" height="100" style="border-width:4px">
        <b>PDFDon Telugu</b><span class="badge">STEP {n}</span></div>
      <div class="phone"><img src="{shot}"></div>
      <div class="cap">{_e(caption)}</div>
    </body></html>"""


def _big(text, sizes):
    """Smaller font for longer text so it stays on two or three lines."""
    short, medium, long_ = sizes
    return short if len(text) <= 10 else medium if len(text) <= 16 else long_


def _thumb(logo, hook_text, shot, name):
    return f"""<html><head><style>{BASE_CSS}
    body {{ width:1280px; height:720px; }}
    .stripe {{ position:absolute; left:0; top:0; bottom:0; width:18px; background:#e2231a; }}
    .left {{ position:absolute; left:60px; top:50px; bottom:36px; width:780px;
             display:flex; flex-direction:column; align-items:flex-start; }}
    .hook {{ font-size:{_big(hook_text, (130, 104, 84))}px; font-weight:900; line-height:1.02;
             color:#ffd400; text-shadow:0 8px 0 rgba(0,0,0,.4); }}
    .name {{ margin-top:28px; background:#e2231a; padding:10px 28px 14px; border-radius:18px;
             font-size:44px; font-weight:800; line-height:1.25; transform:rotate(-2deg); }}
    .brand {{ margin-top:auto; display:flex; align-items:center; gap:14px; font-size:34px; font-weight:800; }}
    .brand span {{ color:#cfd6ff; font-weight:700; }}
    .phone {{ position:absolute; right:70px; top:40px; width:300px; padding:10px; background:#05070d;
              border-radius:34px; transform:rotate(4deg); box-shadow:0 20px 50px rgba(0,0,0,.5); }}
    .phone img {{ display:block; width:100%; border-radius:26px; }}
    </style></head><body>
      <div class="stripe"></div>
      <div class="left"><div class="hook">{_e(hook_text)}</div>
        <div class="name">{_e(name)}</div>
        <div class="brand"><img class="logo" src="{logo}" width="62" height="62" style="border-width:3px">
          pdfdon.com <span>• Mobile లో FREE</span></div></div>
      <div class="phone"><img src="{shot}"></div>
    </body></html>"""


def _render(page, markup, path, width, height):
    page.set_viewport_size({"width": width, "height": height})
    page.set_content(markup, wait_until="load")
    page.evaluate("document.fonts.ready.then(() => true)")
    page.screenshot(path=str(path))


def _segment(frame, voice, seconds, out):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-loop", "1", "-framerate", "30", "-i", str(frame),
         "-i", str(voice),
         "-filter_complex", f"[0:v]fade=t=in:st=0:d=0.25,format=yuv420p[v];[1:a]apad=pad_dur={PAD}[a]",
         "-map", "[v]", "-map", "[a]", "-t", f"{seconds + PAD:.2f}",
         "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-r", "30",
         "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
         str(out)],
        check=True,
    )


def build(script, shots, clips, out, assets, name):
    """Returns (video_path, thumbnail_path)."""
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    logo = _uri(assets / "logo.png")
    pick = lambda key: _uri(shots.get(key) or shots["open"])

    pages = [
        _card(logo, script["hook_text"], script["hook"]["caption"], "pdfdon.com"),
        _step(logo, 1, pick("open"), script["step1"]["caption"]),
        _step(logo, 2, pick("action"), script["step2"]["caption"]),
        _step(logo, 3, pick("result"), script["step3"]["caption"]),
        _card(logo, "FREE", script["cta"]["caption"], "Subscribe 🔔"),
    ]

    thumb = out / "thumbnail.png"
    frames = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for i, markup in enumerate(pages):
            path = frames_dir / f"{i}.png"
            _render(page, markup, path, 1080, 1920)
            frames.append(path)
        _render(page, _thumb(logo, script["hook_text"], pick("action"), name), thumb, 1280, 720)
        browser.close()

    parts = []
    for i, (frame, (voice, seconds)) in enumerate(zip(frames, clips)):
        seg = frames_dir / f"seg{i}.mp4"
        _segment(frame, voice, seconds, seg)
        parts.append(seg)

    listing = frames_dir / "list.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    video = out / "short.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(video)],
        check=True,
    )
    total = sum(s for _, s in clips) + PAD * len(clips)
    print(f"  video: {video} ({total:.1f}s)")
    return video, thumb
