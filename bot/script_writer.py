"""Writes the Telugu Short script (narration, captions, title, tags) with Claude."""
import json
import os

import anthropic

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


def write(topic, previous_titles):
    """Returns the script dict. Uses the topic's fixed steps when no API key is set."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set - using the fixed template script.")
        return template(topic)

    link = SITE + topic["path"]
    earlier = "\n".join(f"- {t}" for t in previous_titles) or "(none yet)"
    prompt = (
        f"Tool: {topic['te_name']}\n"
        f"Tool link: {link}\n"
        f"Tool facts: {topic['facts'].strip()}\n"
        f"Basic steps: {' / '.join(topic['steps'])}\n\n"
        f"Earlier titles for this tool:\n{earlier}\n\n"
        "Write the script for the next Short about this tool."
    )

    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIConnectionError as e:
        print(f"Could not reach the Claude API ({e}) - using the fixed template script.")
        return template(topic)
    except anthropic.APIStatusError as e:
        print(f"Claude API error {e.status_code}: {e.message} - using the fixed template script.")
        return template(topic)

    if response.stop_reason in ("refusal", "max_tokens"):
        print(f"Claude stopped with {response.stop_reason} - using the fixed template script.")
        return template(topic)

    text = next(b.text for b in response.content if b.type == "text")
    script = json.loads(text)
    if link not in script["description"]:
        script["description"] = f"🔗 Free tool: {link}\n\n" + script["description"]
    return script


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
