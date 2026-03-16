import os
import httpx


async def extract_competitor_details(url: str, competitor_name: str) -> dict:
    """
    Use Parallel AI Extract to get brand positioning text from a competitor URL.
    Returns a dict with title, excerpts, and any extracted brand content.
    """
    api_key = os.environ["PARALLEL_API_KEY"]

    payload = {
        "urls": [url],
        "objective": (
            f"Extract {competitor_name}'s brand identity: their mission, target audience, "
            "brand values, product positioning, and any language describing their visual or "
            "aesthetic approach. Include pricing tier signals if present."
        ),
        "excerpts": True,
        "full_content": False,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.parallel.ai/v1beta/extract",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    results = data.get("results", [])
    if not results:
        return {"url": url, "name": competitor_name, "content": "", "excerpts": []}

    first = results[0]
    return {
        "url": url,
        "name": competitor_name,
        "title": first.get("title", competitor_name),
        "content": first.get("full_content", ""),
        "excerpts": first.get("excerpts", []),
    }




