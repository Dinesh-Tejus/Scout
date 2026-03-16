import logging
import os
import httpx
from google import genai
from google.genai import types

from models import VisualAnalysis

logger = logging.getLogger(__name__)

_VISION_MODEL = "gemini-2.5-flash"
_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB

_ANALYSIS_PROMPT = """Analyze this brand image and return a structured visual analysis.

Be specific and opinionated — avoid generic descriptions. Look for:
- Dominant colors: list up to 5 hex codes from most to least prominent
- Typography style: one of "serif/premium", "sans/modern", "script/handcrafted", "display/bold", "mixed"
- Photography approach: one of "lifestyle", "product-only", "flat-lay", "editorial", "illustration", "graphic/abstract"
- Mood: one of "luxurious", "playful", "clinical/minimal", "earthy/natural", "bold/energetic", "nostalgic", "technical"
- Target demographic: a specific description, e.g. "health-conscious urban women 25-35" or "premium tea enthusiasts 40+"
- Positioning summary: 1-2 sentences on how this brand positions itself visually in the market

Return ONLY a JSON object matching the schema. No extra text."""


async def fetch_image_bytes(image_url: str) -> tuple[bytes, str] | None:
    """Fetch image bytes from URL. Returns (bytes, mime_type) or None on failure."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(image_url, headers=headers)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            if not content_type.startswith("image/"):
                return None

            image_bytes = response.content
            if len(image_bytes) > _MAX_IMAGE_BYTES:
                return None

            return image_bytes, content_type
    except Exception:
        return None


async def analyze_brand_image(image_url: str, competitor_name: str) -> VisualAnalysis | None:
    """
    Fetch an image from image_url and analyze it with Gemini Flash vision.
    Returns a structured VisualAnalysis or None if the image can't be processed.
    """
    fetched = await fetch_image_bytes(image_url)
    if fetched is None:
        return None

    image_bytes, mime_type = fetched

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    try:
        response = await client.aio.models.generate_content(
            model=_VISION_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                f"Brand: {competitor_name}\n\n{_ANALYSIS_PROMPT}",
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VisualAnalysis,
                temperature=0.2,
            ),
        )

        raw = response.text
        if not raw:
            return None

        return VisualAnalysis.model_validate_json(raw)

    except Exception as exc:
        exc_str = str(exc).lower()
        if "429" in exc_str or "resource exhausted" in exc_str or "quota" in exc_str:
            logger.warning("Vision API rate limited for %s, skipping", competitor_name)
        return None
