"""Translations with Claude: the title and description in other languages (YouTube shows each viewer
the one for their language), and the narration in English for an English subtitle track."""
import json
import os

import anthropic

from .script_writer import MODEL

LANGUAGES = {
    "en": "English", "hi": "Hindi", "ta": "Tamil", "kn": "Kannada", "ml": "Malayalam",
    "mr": "Marathi", "bn": "Bengali", "gu": "Gujarati",
}

_TEXT = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "description": {"type": "string"}},
    "required": ["title", "description"],
    "additionalProperties": False,
}

SCHEMA = {
    "type": "object",
    "properties": {
        "localizations": {
            "type": "object",
            "properties": {code: _TEXT for code in LANGUAGES},
            "required": list(LANGUAGES),
            "additionalProperties": False,
        },
        "english_narration": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["localizations", "english_narration"],
    "additionalProperties": False,
}

SYSTEM = """You translate YouTube metadata and subtitles for "PDFDon Telugu", a channel of Telugu tutorials
about the free tools on pdfdon.com.

- localizations: translate the Telugu title and description into each listed language, natural and
  simple, the way people of that language search for it. Keep brand names (PDFDon, pdfdon.com), links,
  hashtags, numbers and the "0:00" chapter timestamps exactly as they are; translate the chapter names.
  Keep "#Shorts" in the title when the original has it. Titles must stay under 100 characters.
- english_narration: translate each narration part into plain English for subtitles, one item per part,
  in the same order and the same number of items as given."""


def translate(script, narration):
    """Returns (localizations, english_narration), or (None, None) when Claude is not available."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, None
    payload = {
        "title": script["title"],
        "description": script["description"],
        "narration_parts": narration,
        "languages": LANGUAGES,
    }
    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=32000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            system=SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
    except anthropic.APIConnectionError as e:
        print(f"  translation skipped: could not reach the Claude API ({e})")
        return None, None
    except anthropic.APIStatusError as e:
        print(f"  translation skipped: Claude API error {e.status_code}: {e.message}")
        return None, None
    if response.stop_reason in ("refusal", "max_tokens"):
        print(f"  translation skipped: Claude stopped with {response.stop_reason}")
        return None, None

    data = json.loads(next(b.text for b in response.content if b.type == "text"))
    english = data["english_narration"]
    if len(english) != len(narration):
        print("  English subtitles skipped: the translation has a different number of parts")
        english = None
    localizations = {code: {"title": t["title"][:100], "description": t["description"][:4900]}
                     for code, t in data["localizations"].items()}
    return localizations, english
