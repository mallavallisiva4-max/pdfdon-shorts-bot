"""Writes the Telugu video scripts (narration, captions, title, tags) with Claude, or Gemini's
free tier when there is no Claude key."""
import json
import os

import anthropic

from . import gemini

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
SITE = "https://www.pdfdon.com"

# The video always has these five parts, in this order.
PARTS = ["hook", "step1", "step2", "step3", "cta"]

_PART = {
    "type": "object",
    "properties": {
        "narration": {"type": "string"},
        "caption": {"type": "string"},
    },
    "required": ["narration", "caption"],
    "additionalProperties": False,
}

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "hook_text": {"type": "string"},
        **{part: _PART for part in PARTS},
    },
    "required": ["title", "description", "tags", "hook_text", *PARTS],
    "additionalProperties": False,
}

SYSTEM = """You write scripts for "PDFDon Telugu", a YouTube Shorts channel that shows people in
Andhra Pradesh and Telangana how to do everyday document and photo jobs on their phone with the
free tools on pdfdon.com. Viewers are students filling exam and job forms, shop owners, and
ordinary phone users. Many are not comfortable with technology.

Write in simple spoken Telugu, the way a friendly elder brother explains on the phone. Keep common
English tech words in English script (Photo, PDF, KB, Upload, Download, Resize, Form). A Telugu
text-to-speech voice reads the narration, so write full words, no emojis or symbols in narration,
and spell numbers the way they should be read (for example "ఇరవై KB").

The Short has five parts, each shown on its own screen:
- hook: the viewer's problem in one line, so they keep watching (about 3 seconds).
- step1: opening the tool on pdfdon.com.
- step2: what to select or type.
- step3: the result and downloading it.
- cta: free, no login, no watermark; tell them to subscribe and comment which tool they want next.

Rules:
- narration: one or two short sentences, at most 22 words per part. The whole Short must stay under
  45 seconds.
- caption: the on-screen text for that part, at most 6 words, Telugu or English.
- Only describe what the tool facts say. Never invent buttons, options, limits or prices.
- title: under 80 characters, Telugu and English mixed, with the main search words people type
  (for example "photo resize 20kb telugu"). No clickbait that the video does not deliver.
- description: first line is the tool link exactly as given. Then 2 to 4 short lines in Telugu,
  then 3 to 5 hashtags including #Shorts and #PDFDonTelugu.
- tags: 10 to 15 search phrases in English and Telugu, lowercase.
- hook_text: 2 to 4 big words for the thumbnail, for example "PHOTO 20KB".
- When earlier titles for this tool are listed, choose a different angle (a different exam, a
  different problem, a different use) so the new Short is not a repeat."""


def _prompt(topic, previous_titles, ask):
    earlier = "\n".join(f"- {t}" for t in previous_titles) or "(none yet)"
    return (
        f"Tool: {topic['te_name']}\n"
        f"Tool link: {SITE + topic['path']}\n"
        f"Tool facts: {topic['facts'].strip()}\n"
        f"Basic steps: {' / '.join(topic['steps'])}\n\n"
        f"Earlier titles for this tool:\n{earlier}\n\n"
        f"{ask}"
    )


def _ask(system, prompt, schema, link):
    """One structured call: Claude when ANTHROPIC_API_KEY is set, otherwise Gemini's free tier
    (GEMINI_API_KEY). Returns the script dict, or None when neither worked."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if not gemini.configured():
            print("Neither ANTHROPIC_API_KEY nor GEMINI_API_KEY is set.")
            return None
        script = gemini.ask_json(system, prompt, schema)
        if script is not None and link not in script["description"]:
            script["description"] = f"🔗 Free tool: {link}\n\n" + script["description"]
        return script
    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=32000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": schema},
            },
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIConnectionError as e:
        print(f"Could not reach the Claude API ({e}).")
        return None
    except anthropic.APIStatusError as e:
        print(f"Claude API error {e.status_code}: {e.message}")
        return None

    if response.stop_reason in ("refusal", "max_tokens"):
        print(f"Claude stopped with {response.stop_reason}.")
        return None

    text = next(b.text for b in response.content if b.type == "text")
    script = json.loads(text)
    if link not in script["description"]:
        script["description"] = f"🔗 Free tool: {link}\n\n" + script["description"]
    return script


def write(topic, previous_titles):
    """Short script. Falls back to the topic's fixed steps when Claude is not available."""
    link = SITE + topic["path"]
    script = _ask(SYSTEM, _prompt(topic, previous_titles, "Write the script for the next Short about this tool."),
                  SCHEMA, link)
    if script is None:
        print("  using the fixed template script.")
        return template(topic)
    return script


# ---------------------------------------------------------------- long videos

# Order of the long video. intro and outro are title cards; the rest is screen recording.
LONG_PARTS = ["intro", "home", "search", "open", "action", "result", "more", "outro"]

_LONG_PART = {
    "type": "object",
    "properties": {
        "heading": {"type": "string"},
        "narration": {"type": "string"},
    },
    "required": ["heading", "narration"],
    "additionalProperties": False,
}

LONG_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "hook_text": {"type": "string"},
        **{part: _LONG_PART for part in LONG_PARTS},
    },
    "required": ["title", "description", "tags", "hook_text", *LONG_PARTS],
    "additionalProperties": False,
}

LONG_SYSTEM = """You write full tutorial videos (about 5 minutes) for "PDFDon Telugu", a YouTube channel
that shows people in Andhra Pradesh and Telangana how to do everyday document and photo jobs with the
free tools on pdfdon.com. Viewers are students filling exam and job forms, shop owners, and ordinary
phone and computer users. Many are not comfortable with technology, so explain slowly and clearly.

Write in simple spoken Telugu, like a friendly teacher sitting next to the viewer. Keep common English
tech words in English script (Photo, PDF, KB, Upload, Download, Resize, Form, Website, Search). A Telugu
text-to-speech voice reads the narration: write full words, no emojis, symbols, bullet points or
markdown, and spell numbers the way they should be read.

The screen recording shows these parts in this order. Write the narration for what is on screen:
- intro (title card, about 20 seconds, 40-50 words): the problem this tool solves and what the viewer
  will learn. Ask them to watch till the end.
- home (about 30 seconds, 60-70 words): the pdfdon.com home page being scrolled. Free, no login, no
  watermark, works on mobile and computer, files stay on your device.
- search (about 20 seconds, 40-50 words): typing the tool name in the website's search box.
- open (about 50 seconds, 100-120 words): the tool page opens. Explain when people need this tool and
  what to keep ready (for example the exam notification with the required size).
- action (about 90 seconds, 180-220 words): selecting the file or typing the details, step by step.
  Explain each setting the facts mention and why it matters.
- result (about 70 seconds, 140-160 words): pressing the main button, checking the result and
  downloading it. How to check the result is right before using it.
- more (about 70 seconds, 140-160 words): the rest of the page is scrolled. Common mistakes people
  make and simple tips to avoid them.
- outro (title card, about 25 seconds, 50-60 words): short recap; like, share with friends who need
  it, subscribe, and comment which tool to explain next.

Rules:
- heading: the chapter name shown on screen and in the YouTube chapters, 2 to 5 words, Telugu or
  English.
- Only state what the tool facts say. Never invent buttons, options, limits, prices, or the exact
  size rules of a particular exam; tell viewers to check their own notification for the numbers.
- title: under 90 characters, Telugu and English mixed, with the words people search for. Not a
  Short, so no #Shorts. No clickbait that the video does not deliver.
- description: first line is the tool link exactly as given, then 4 to 6 short lines in Telugu about
  what the video teaches, then 3 to 5 hashtags including #PDFDonTelugu. Chapters are added
  automatically, so do not write timestamps.
- tags: 12 to 18 search phrases in English and Telugu, lowercase.
- hook_text: 2 to 4 big words for the thumbnail.
- When earlier titles for this tool are listed, choose a different angle so the video is not a
  repeat."""


def write_long(topic, previous_titles):
    """Long tutorial script, or None: a long video needs Claude (there is no fixed template)."""
    return _ask(LONG_SYSTEM,
                _prompt(topic, previous_titles, "Write the script for the next full tutorial video about this tool."),
                LONG_SCHEMA, SITE + topic["path"])


def template(topic):
    link = SITE + topic["path"]
    s1, s2, s3 = topic["steps"]
    name = topic["te_name"]
    return {
        "title": f"{name} | Mobile లో FREE గా | Telugu #Shorts",
        "description": (
            f"🔗 Free tool: {link}\n\n"
            f"{name} ఇప్పుడు mobile లోనే, FREE గా.\n"
            "No login • No watermark • No limit\n\n"
            "#Shorts #PDFDonTelugu #Telugu"
        ),
        "tags": ["pdfdon", "pdfdon telugu", "telugu tech", name.lower(), "mobile tips telugu"],
        "hook_text": topic["hook"],
        "hook": {"narration": f"{name} mobile లోనే free గా ఎలా చేయాలో చూద్దాం.", "caption": "Mobile లో FREE గా"},
        "step1": {"narration": s1, "caption": s1},
        "step2": {"narration": s2, "caption": s2},
        "step3": {"narration": s3, "caption": s3},
        "cta": {
            "narration": "అంతా free, login అవసరం లేదు. ఇలాంటి tips కోసం subscribe చేయండి.",
            "caption": "pdfdon.com",
        },
    }
