"""Turns the screen recording and the voice into the final MP4.

Titles, captions and logos are drawn as HTML (Chromium shapes Telugu correctly, ffmpeg drawtext
does not) and laid over the recording with ffmpeg:
- Short: 1080x1920. Title cards, and the phone recording inside a frame with a caption.
- Long: 1920x1080. Title cards, and the full-screen recording with a chapter name and logo."""
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
body.clear {{ background: transparent; }}
.logo {{ border-radius: 50%; border: 6px solid #fff; }}
"""

# Where the phone recording sits inside the Short frame.
PHONE_X, PHONE_Y, PHONE_W = 236, 236, 608


def _uri(path):
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/png;base64,{data}" if path.suffix == ".png" else f"data:image/jpeg;base64,{data}"


def _e(text):
    return html.escape(text)


def _big(text, sizes):
    """Smaller font for longer text so it stays on two or three lines."""
    short, medium, long_ = sizes
    return short if len(text) <= 10 else medium if len(text) <= 16 else long_


# ---------------------------------------------------------------- Short layers

def _card(logo, big, caption, sub):
    return f"""<html><head><style>{BASE_CSS}
    body {{ width:1080px; height:1920px; display:flex; flex-direction:column; align-items:center;
            justify-content:center; text-align:center; padding:0 80px; }}
    .big {{ margin-top:70px; font-size:{_big(big, (150, 124, 100))}px; font-weight:900; line-height:1.05;
            color:#ffd400; text-shadow:0 10px 0 rgba(0,0,0,.35); }}
    .cap {{ margin-top:60px; font-size:72px; font-weight:700; line-height:1.35; }}
    .sub {{ margin-top:70px; display:inline-block; background:#e2231a; padding:22px 48px;
            border-radius:24px; font-size:56px; font-weight:800; }}
    </style></head><body>
      <img class="logo" src="{logo}" width="300" height="300">
      <div class="big">{_e(big)}</div>
      <div class="cap">{_e(caption)}</div>
      <div class="sub">{_e(sub)}</div>
    </body></html>"""


def _phone_frame(logo, n, phone_h):
    """Background of a Short step: header, step badge and the phone the recording goes into."""
    return f"""<html><head><style>{BASE_CSS}
    body {{ width:1080px; height:1920px; }}
    .top {{ height:170px; display:flex; align-items:center; gap:24px; padding:0 56px;
            background:rgba(0,0,0,.25); border-bottom:6px solid #e2231a; }}
    .top b {{ font-size:54px; }}
    .badge {{ margin-left:auto; background:#ffd400; color:#141a30; font-weight:900; font-size:46px;
              padding:10px 30px; border-radius:40px; }}
    .phone {{ position:absolute; left:{PHONE_X - 16}px; top:{PHONE_Y - 16}px; width:{PHONE_W + 32}px;
              height:{phone_h + 32}px; background:#05070d; border-radius:30px;
              box-shadow:0 30px 70px rgba(0,0,0,.55); }}
    </style></head><body>
      <div class="top"><img class="logo" src="{logo}" width="100" height="100" style="border-width:4px">
        <b>PDFDon Telugu</b><span class="badge">STEP {n}</span></div>
      <div class="phone"></div>
    </body></html>"""


def _phone_caption(caption):
    """Top layer of a Short step: the caption box, drawn over the recording."""
    return f"""<html><head><style>{BASE_CSS}
    body {{ width:1080px; height:1920px; }}
    .cap {{ position:absolute; left:50px; right:50px; bottom:70px; background:#fff; color:#141a30;
            border-radius:36px; padding:30px 40px; text-align:center; font-size:62px; font-weight:800;
            line-height:1.3; border-bottom:14px solid #e2231a; box-shadow:0 -10px 40px rgba(0,0,0,.35); }}
    </style></head><body class="clear"><div class="cap">{_e(caption)}</div></body></html>"""


# ---------------------------------------------------------------- long video layers

def _wide_card(logo, big, caption, sub):
    return f"""<html><head><style>{BASE_CSS}
    body {{ width:1920px; height:1080px; display:flex; align-items:center; gap:90px; padding:0 140px; }}
    .text {{ flex:1; }}
    .big {{ font-size:{_big(big, (150, 120, 96))}px; font-weight:900; line-height:1.05; color:#ffd400;
            text-shadow:0 10px 0 rgba(0,0,0,.35); }}
    .cap {{ margin-top:40px; font-size:64px; font-weight:700; line-height:1.3; }}
    .sub {{ margin-top:50px; display:inline-block; background:#e2231a; padding:18px 44px;
            border-radius:22px; font-size:50px; font-weight:800; }}
    </style></head><body>
      <img class="logo" src="{logo}" width="380" height="380" style="border-width:8px">
      <div class="text"><div class="big">{_e(big)}</div><div class="cap">{_e(caption)}</div>
        <div class="sub">{_e(sub)}</div></div>
    </body></html>"""


def _lower_third(logo, heading):
    """Top layer of a long-video chapter: channel badge and the chapter name."""
    return f"""<html><head><style>{BASE_CSS}
    body {{ width:1920px; height:1080px; }}
    .badge {{ position:absolute; right:36px; top:30px; display:flex; align-items:center; gap:14px;
              background:rgba(13,17,34,.82); padding:10px 26px 10px 10px; border-radius:50px;
              font-size:32px; font-weight:800; }}
    .chapter {{ position:absolute; left:40px; bottom:40px; display:flex; align-items:stretch;
                box-shadow:0 10px 30px rgba(0,0,0,.4); border-radius:16px; overflow:hidden; }}
    .chapter i {{ width:16px; background:#e2231a; }}
    .chapter b {{ background:rgba(13,17,34,.9); padding:16px 34px; font-size:46px; font-weight:800; }}
    .site {{ position:absolute; right:40px; bottom:48px; background:#e2231a; padding:10px 24px;
             border-radius:14px; font-size:34px; font-weight:800; }}
    </style></head><body class="clear">
      <div class="badge"><img class="logo" src="{logo}" width="64" height="64" style="border-width:3px">PDFDon Telugu</div>
      <div class="chapter"><i></i><b>{_e(heading)}</b></div>
      <div class="site">pdfdon.com</div>
    </body></html>"""


def _thumb(logo, hook_text, shot, name, wide):
    """1280x720 thumbnail. A phone screenshot for Shorts, a laptop screenshot for long videos."""
    screen = (
        ".screen {{ position:absolute; right:40px; top:150px; width:560px; padding:10px; background:#05070d;"
        " border-radius:18px; transform:rotate(3deg); box-shadow:0 20px 50px rgba(0,0,0,.5); }}"
        if wide else
        ".screen {{ position:absolute; right:70px; top:40px; width:300px; padding:10px; background:#05070d;"
        " border-radius:34px; transform:rotate(4deg); box-shadow:0 20px 50px rgba(0,0,0,.5); }}"
    ).format()
    left_w = 640 if wide else 780
    return f"""<html><head><style>{BASE_CSS}
    body {{ width:1280px; height:720px; }}
    .stripe {{ position:absolute; left:0; top:0; bottom:0; width:18px; background:#e2231a; }}
    .left {{ position:absolute; left:60px; top:50px; bottom:36px; width:{left_w}px;
             display:flex; flex-direction:column; align-items:flex-start; }}
    .hook {{ font-size:{_big(hook_text, (124, 100, 80))}px; font-weight:900; line-height:1.02;
             color:#ffd400; text-shadow:0 8px 0 rgba(0,0,0,.4); }}
    .name {{ margin-top:28px; background:#e2231a; padding:10px 28px 14px; border-radius:18px;
             font-size:42px; font-weight:800; line-height:1.25; transform:rotate(-2deg); }}
    .brand {{ margin-top:auto; display:flex; align-items:center; gap:14px; font-size:34px; font-weight:800; }}
    .brand span {{ color:#cfd6ff; font-weight:700; }}
    {screen}
    .screen img {{ display:block; width:100%; border-radius:{10 if wide else 26}px; }}
    </style></head><body>
      <div class="stripe"></div>
      <div class="left"><div class="hook">{_e(hook_text)}</div>
        <div class="name">{_e(name)}</div>
        <div class="brand"><img class="logo" src="{logo}" width="62" height="62" style="border-width:3px">
          pdfdon.com <span>• FREE</span></div></div>
      <div class="screen"><img src="{shot}"></div>
    </body></html>"""


# ---------------------------------------------------------------- ffmpeg

def _render(page, markup, path, width, height, clear=False):
    page.set_viewport_size({"width": width, "height": height})
    page.set_content(markup, wait_until="load")
    page.evaluate("document.fonts.ready.then(() => true)")
    page.screenshot(path=str(path), omit_background=clear)


ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-r", "30", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2"]


def _still(frame, voice, seconds, out):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-loop", "1", "-framerate", "30", "-i", str(frame), "-i", str(voice),
         "-filter_complex", f"[0:v]fade=t=in:st=0:d=0.25,format=yuv420p[v];[1:a]apad=pad_dur={PAD}[a]",
         "-map", "[v]", "-map", "[a]", "-t", f"{seconds:.2f}", *ENCODE, str(out)],
        check=True,
    )


def _recorded(recording, start, seconds, voice, top, out, size, base=None, place=(0, 0), clip_w=None):
    """A slice of the recording, laid on `base` (or nothing), with `top` drawn over it."""
    w, h = size
    inputs = (["-loop", "1", "-framerate", "30", "-i", str(base)] if base
              else ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30"])
    scale = f"scale={clip_w}:-2:flags=lanczos" if clip_w else f"scale={w}:{h}:flags=lanczos"
    graph = (
        f"[1:v]{scale},setpts=PTS-STARTPTS,fps=30,tpad=stop_mode=clone:stop_duration={seconds:.2f}[clip];"
        f"[0:v][clip]overlay={place[0]}:{place[1]}[base];"
        f"[base][2:v]overlay=0:0,fade=t=in:st=0:d=0.2,format=yuv420p[v];"
        f"[3:a]apad=pad_dur={PAD}[a]"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs,
         "-ss", f"{start:.2f}", "-t", f"{seconds:.2f}", "-i", str(recording),
         "-loop", "1", "-framerate", "30", "-i", str(top),
         "-i", str(voice),
         "-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-t", f"{seconds:.2f}",
         *ENCODE, str(out)],
        check=True,
    )


def _clock(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def build(kind, script, parts, scene_of, clips, rec, out, assets, name):
    """Returns (video_path, thumbnail_path, chapters_text).

    parts: the script parts in order; scene_of: part -> recorded scene (cards are not in it);
    clips: [(voice_mp3, seconds), ...] one per part; rec: what recorder.record returned."""
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    logo = _uri(assets / "logo.png")
    shots = rec["shots"]
    shot = _uri(shots.get("action") or shots.get("result") or shots["open"])
    wide = kind == "long"
    size = (1920, 1080) if wide else (1080, 1920)
    phone_h = round(PHONE_W * 844 / 390)

    # Draw every layer first (one browser), then cut the video (ffmpeg).
    layers = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def draw(key, markup, clear=False, w=size[0], h=size[1]):
            path = frames_dir / f"{key}.png"
            _render(page, markup, path, w, h, clear)
            layers[key] = path

        for i, part in enumerate(parts):
            if wide:
                heading = script[part]["heading"]
                if part == "intro":
                    draw(f"{i}", _wide_card(logo, script["hook_text"], heading, "pdfdon.com"))
                elif part == "outro":
                    draw(f"{i}", _wide_card(logo, "Subscribe 🔔", heading, "pdfdon.com"))
                else:
                    draw(f"{i}top", _lower_third(logo, heading), clear=True)
            else:
                caption = script[part]["caption"]
                if part == "hook":
                    draw(f"{i}", _card(logo, script["hook_text"], caption, "pdfdon.com"))
                elif part == "cta":
                    draw(f"{i}", _card(logo, "FREE", caption, "Subscribe 🔔"))
                else:
                    step = parts.index(part)  # step1 is the 2nd part
                    draw(f"{i}base", _phone_frame(logo, step, phone_h))
                    draw(f"{i}top", _phone_caption(caption), clear=True)

        thumb = out / "thumbnail.png"
        _render(page, _thumb(logo, script["hook_text"], shot, name, wide), thumb, 1280, 720)
        browser.close()

    segments, chapters, at = [], [], 0.0
    for i, (part, (voice, spoken)) in enumerate(zip(parts, clips)):
        seconds = spoken + PAD
        seg = frames_dir / f"seg{i}.mp4"
        if part in scene_of:
            start = rec["marks"][scene_of[part]]
            if wide:
                _recorded(rec["video"], start, seconds, voice, layers[f"{i}top"], seg, size)
            else:
                _recorded(rec["video"], start, seconds, voice, layers[f"{i}top"], seg, size,
                          base=layers[f"{i}base"], place=(PHONE_X, PHONE_Y), clip_w=PHONE_W)
        else:
            _still(layers[f"{i}"], voice, seconds, seg)
        segments.append(seg)
        if wide:
            chapters.append(f"{_clock(at)} {script[part]['heading']}")
        at += seconds

    listing = frames_dir / "list.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in segments), encoding="utf-8")
    video = out / ("long.mp4" if wide else "short.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(video)],
        check=True,
    )
    print(f"  video: {video} ({_clock(at)})")
    return video, thumb, "\n".join(chapters), at
