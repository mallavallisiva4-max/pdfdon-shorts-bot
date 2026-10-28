"""Google Gemini (free tier) as the script and translation writer when there is no Claude key.
Get a free key at aistudio.google.com and save it as the GEMINI_API_KEY secret."""
import json
import os

from google import genai
from google.genai import errors, types

# Tried in order; a busy or retired model falls through to the next one.
MODELS = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-3.8-flash", "gemini-2.5-flash"] if m]


def configured():
    return bool(os.environ.get("GEMINI_API_KEY"))


def ask_json(system, prompt, schema):
    """Returns the parsed JSON answer, or None when Gemini is not set up or did not answer."""
    if not configured():
        return None
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_json_schema=schema,
        max_output_tokens=32000,
    )
    for model in MODELS:
        try:
            response = client.models.generate_content(model=model, contents=prompt, config=config)
            if not response.text:
                print(f"  Gemini {model} gave an empty answer")
                continue
            print(f"  written by Gemini ({model})")
            return json.loads(response.text)
        except errors.APIError as e:
            print(f"  Gemini {model} error {e.code}: {str(e.message)[:200]}")
        except json.JSONDecodeError:
            print(f"  Gemini {model} answer was not valid JSON")
    return None
