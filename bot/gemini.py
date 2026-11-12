"""Google Gemini (free tier) as the script and translation writer when there is no Claude key.
Get a free key at aistudio.google.com and save it as the GEMINI_API_KEY secret."""
import json
import os
import time

from google import genai
from google.genai import errors, types

# Free-tier models, tried in order; a busy or retired model falls through to the next one.
MODELS = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-3.8-flash", "gemini-3.6-flash",
                      "gemini-3.5-flash-lite"] if m]
BUSY = (429, 500, 503, 504)  # worth waiting for: rate limit, "high demand", timeout
TRIES = 3
ROUNDS = 3          # when every model is busy, wait and go through the list again
ROUND_WAIT = 150    # seconds between rounds


def configured():
    return bool(os.environ.get("GEMINI_API_KEY"))


def ask_json(system, prompt, schema):
    """Returns the parsed JSON answer, or None when Gemini is not set up or did not answer."""
    if not configured():
        return None
    # Give up on a call after 3 minutes instead of waiting forever.
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                          http_options=types.HttpOptions(timeout=180_000))
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_json_schema=schema,
        max_output_tokens=32000,
    )
    for round_ in range(1, ROUNDS + 1):
        busy = False
        for model in MODELS:
            for attempt in range(1, TRIES + 1):
                try:
                    response = client.models.generate_content(model=model, contents=prompt, config=config)
                    if not response.text:
                        print(f"  Gemini {model} gave an empty answer")
                        break
                    print(f"  written by Gemini ({model})")
                    return json.loads(response.text)
                except errors.APIError as e:
                    print(f"  Gemini {model} error {e.code} (try {attempt}): {str(e.message)[:160]}")
                    if e.code not in BUSY:
                        break  # retired or bad request: next model
                    busy = True
                    if attempt == TRIES:
                        break
                    time.sleep(20 * attempt)
                except json.JSONDecodeError:
                    print(f"  Gemini {model} answer was not valid JSON")
                    break
        if not busy or round_ == ROUNDS:
            break
        print(f"  all Gemini models busy - waiting {ROUND_WAIT}s (round {round_} of {ROUNDS})")
        time.sleep(ROUND_WAIT)
    return None
