import os
import uuid
from tavily import AsyncTavilyClient

from models import CompetitorCard, CompetitorImage


async def search_competitors(query: str, max_results: int = 5) -> list[CompetitorCard]:
    """Search for competitors using Tavily and return CompetitorCard objects with image URLs."""
    client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])

    response = await client.search(
        query=query,
        max_results=max_results,
        include_images=True,
        search_depth="basic",
    )

    competitors: list[CompetitorCard] = []
    seen_domains: set[str] = set()

    # Build competitor cards from search results
    for result in response.get("results", []):
        url = result.get("url", "")
        domain = _extract_domain(url)

        if domain in seen_domains:
            continue
        seen_domains.add(domain)

        name = result.get("title", domain).split(" - ")[0].split(" | ")[0].strip()

        # Try to find a brand image for this result
        image_url = _find_image_for_result(url, response.get("images", []))

        competitors.append(
            CompetitorCard(
                id=str(uuid.uuid4()),
                name=name,
                website=url,
                image_url=image_url,
            )
        )

    return competitors


def _extract_domain(url: str) -> str:
    """Extract root domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        parts = parsed.netloc.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return parsed.netloc
    except Exception:
        return url


def _find_image_for_result(result_url: str, all_images: list) -> str:
    """Find the best image URL for a result, preferring same-domain images."""
    result_domain = _extract_domain(result_url)

    # First try same-domain images
    for img in all_images:
        img_url = img.get("url", img) if isinstance(img, dict) else img
        if isinstance(img_url, str) and result_domain in img_url:
            if _is_likely_brand_image(img_url):
                return img_url

    # Fall back to any image from the list
    for img in all_images:
        img_url = img.get("url", img) if isinstance(img, dict) else img
        if isinstance(img_url, str) and _is_likely_brand_image(img_url):
            return img_url

    return ""


def _is_likely_brand_image(url: str) -> bool:
    """Filter out tracking pixels, icons, and tiny images."""
    url_lower = url.lower()
    skip_patterns = [
        "favicon", "icon-", "pixel", "tracking", "analytics",
        "1x1", "spacer", "blank", "logo-white", "badge"
    ]
    return not any(p in url_lower for p in skip_patterns)


async def image_search(
    competitor_name: str,
    competitor_website: str,
    max_results: int = 5,
) -> list[CompetitorImage]:
    """Search for brand images for a specific competitor using Tavily."""
    client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = await client.search(
        query=f"{competitor_name} brand",
        include_images=True,
        include_image_descriptions=True,
        max_results=max_results,
    )

    results = response.get("results", [])
    source_url = results[0]["url"] if results else competitor_website

    images = []
    for img in response.get("images", []):
        url = img.get("url", "") if isinstance(img, dict) else img
        if not url:
            continue
        title = img.get("description") if isinstance(img, dict) else None
        images.append(CompetitorImage(image_url=url, source_url=source_url, title=title))

    return images[:max_results]
