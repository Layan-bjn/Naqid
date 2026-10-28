import os
import json
import re
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types
from backend.schemas import DOMSignals, Issue, SuggestedFix

load_dotenv()

SYSTEM_PROMPT = """You are a senior QA engineer and UX/UI auditor.
Look at the full-page screenshot and the collected DOM signals.
Detect all real design, functional, layout, accessibility, and responsiveness problems:
- Layout breakage and overlapping elements (e.g. badges overlapping headings)
- Clipped or overflowing text (e.g. buttons with overflow hidden clipping Arabic text)
- Broken images or 404 assets
- Poor color contrast (e.g. light gray text on white background)
- Tiny tap targets (<44x44px on mobile)
- Misaligned elements and inconsistent spacing in card grids
- Missing form labels or placeholders
- Missing alt attributes on images
- Responsive issues and horizontal scrollbars (scrollWidth > clientWidth)
- Console errors and broken/inactive JavaScript handlers

IMPORTANT: Check both the visual screenshot AND the DOM signals thoroughly. If the DOM signals report console_errors, broken_images, overflow, clipped elements, small touch targets, missing alts, or missing form labels, include them as distinct issues.
Do NOT invent issues that are not visible in the screenshot or supported by the DOM signals.
All textual fields in the output (title, description, location, suggested_fix.explanation, summary) MUST be in professional, clear Arabic.
The suggested_fix.code should be practical, production-ready code (CSS, HTML, or JS).
The test_scenario must be a concise, valid Playwright (Python) snippet that programmatically verifies the issue is resolved.

Output ONLY valid, parseable JSON matching this schema:
{
 "issues": [
  {
   "title": "short Arabic title",
   "category": "layout | visual | ux | accessibility | functional | responsive",
   "severity": "critical | high | medium | low",
   "viewport": "desktop | mobile",
   "description": "Arabic explanation of what is wrong and why it matters",
   "location": "where on the page, in Arabic",
   "suggested_fix": {
     "language": "css | html | js",
     "code": "the fix code",
     "explanation": "Arabic explanation of the fix"
   },
   "test_scenario": "a Playwright (Python) snippet that would verify this issue is fixed"
  }
 ],
 "summary": "2-3 sentence Arabic summary",
 "score": 0-100
}
"""

def extract_json(raw_text: str) -> Dict[str, Any]:
    """
    Robustly extract and parse JSON from model response text, stripping markdown fences if present.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()

    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        text = match.group(1)

    return json.loads(text)

def list_available_gemini_models(api_key: Optional[str] = None) -> List[str]:
    """
    List available Gemini models for the provided API key.
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        return []
    try:
        client = genai.Client(api_key=key)
        return [m.name for m in client.models.list() if "gemini" in m.name]
    except Exception as e:
        print(f"Error listing Gemini models: {e}")
        return []

async def analyze_viewport_screenshot(
    image_path: str,
    viewport_name: str,
    signals: DOMSignals,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send the viewport screenshot and DOM signals to Google Gemini Vision model.
    Retries once on JSON parse or API generation error.
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    model = model_name or os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

    # Read image bytes
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")

    signals_dict = signals.model_dump()
    user_prompt = f"""Audit this web page for the '{viewport_name}' viewport.

Collected DOM Signals:
{json.dumps(signals_dict, ensure_ascii=False, indent=2)}

Please inspect the provided screenshot alongside these DOM signals, find all visual, layout, responsiveness, accessibility, and functional bugs, and return the strict JSON report."""

    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        temperature=0.1,
    )

    last_error = None
    # First attempt
    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=[image_part, user_prompt],
            config=config,
        )
        return extract_json(response.text)
    except Exception as err:
        last_error = err
        print(f"First attempt with Gemini ({model}) encountered error: {err}. Retrying once...")

    # Retry attempt with explicit instruction
    try:
        retry_prompt = f"{user_prompt}\n\nIMPORTANT: Return ONLY raw, valid JSON conforming exactly to the requested schema. No surrounding text or invalid characters."
        response = await client.aio.models.generate_content(
            model=model,
            contents=[image_part, retry_prompt],
            config=config,
        )
        return extract_json(response.text)
    except Exception as err:
        # Check if model name failed
        available = list_available_gemini_models(key)
        raise RuntimeError(
            f"Gemini API analysis failed on model '{model}': {err}. "
            f"Available models: {available}"
        ) from last_error
