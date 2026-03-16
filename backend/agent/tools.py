"""
Tool implementations called by the Gemini Live session when the agent
requests function execution. Each tool emits structured WebSocket events
and returns data back to the Live session.

Deep research (image search, vision analysis, text extraction) and synthesis
run automatically in the background after search_competitors completes —
Gemini does not need to call any further tools.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

from datetime import datetime, timezone

from models import (
    CacheHitEvent,
    CompetitorCard,
    CompetitorFoundEvent,
    CompetitorImagesEvent,
    ExtractResultEvent,
    ImageAnalyzedEvent,
    MarketPatterns,
    MarketPatternsEvent,
    PositioningGapsEvent,
    ResearchCompleteEvent,
    SearchResultEvent,
    ToolStartEvent,
    VisionStartEvent,
)
from services import tavily, parallel, vision

# Type alias for the WebSocket emit callable
WsEmit = Callable[[dict], Awaitable[None]]


async def handle_search_competitors(
    args: dict,
    session_id: str,
    ws_emit: WsEmit,
    session_state: dict,
    push_inject=None,
) -> dict:
    """
    Tavily text search → emit competitor_found events → fire background deep research.
    Returns summary of discovered competitors for Gemini to narrate immediately.
    """
    session_state["search_count"] = session_state.get("search_count", 0) + 1
    query = args.get("query", "")
    max_results = int(args.get("max_results", 5))

    await ws_emit(ToolStartEvent(tool="search_competitors", query=query).model_dump())

    # ── Cache check ───────────────────────────────────────────────────────────
    competitors: list[CompetitorCard] = []
    cache_hit = False
    cached_at_str: str | None = None

    try:
        from services import firestore_client
        cached = await firestore_client.get_cached_search(query)
        if cached is not None:
            competitors = [CompetitorCard(**c) for c in cached]
            cache_hit = True
            # Retrieve cached_at from one of the stored docs (stored at cache level)
            # We'll read it properly below; for now use a fallback
            cached_at_str = datetime.now(timezone.utc).isoformat()
            try:
                import hashlib
                from google.cloud import firestore as _fs
                db = firestore_client._get_db()
                doc = await db.collection("search_cache").document(
                    hashlib.md5(query.strip().lower().encode()).hexdigest()
                ).get()
                if doc.exists:
                    cached_at_str = doc.to_dict().get("cached_at", cached_at_str)
            except Exception:
                pass
    except Exception as e:
        logger.debug("Cache lookup skipped: %s", e)

    if not cache_hit:
        competitors = await tavily.search_competitors(query, max_results)

    # ── Emit competitors ──────────────────────────────────────────────────────
    for competitor in competitors:
        await ws_emit(CompetitorFoundEvent(competitor=competitor).model_dump())
        session_state.setdefault("competitors", {})[competitor.id] = competitor

    await ws_emit(SearchResultEvent(
        query=query, found=len(competitors), names=[c.name for c in competitors]
    ).model_dump())

    if cache_hit and cached_at_str:
        await ws_emit(CacheHitEvent(
            query=query,
            competitor_count=len(competitors),
            cached_at=cached_at_str,
        ).model_dump())
    elif not cache_hit:
        # Persist to cache after a fresh Tavily search
        try:
            from services import firestore_client
            now = datetime.now(timezone.utc).isoformat()
            await firestore_client.cache_search(
                query,
                [c.model_dump() for c in competitors],
                now,
            )
        except Exception as e:
            logger.debug("Cache write skipped: %s", e)

    # Fire deep research for all competitors in the background — don't await
    task = asyncio.create_task(
        _deep_research_all(competitors, ws_emit, session_state, session_id, push_inject)
    )
    session_state.setdefault("_research_tasks", []).append(task)

    # Inject a narration cue so Gemini always introduces the primary results.
    # Small delay ensures the tool response reaches Gemini first, then this cue
    # enriches its context for the next turn.
    if push_inject:
        names = [c.name for c in competitors]
        cue = (
            f"[Found {len(competitors)} competitors: {', '.join(names)}. "
            f"Competitor cards are now visible in the UI. "
            f"Please naturally introduce these brands and mention that visual and text analysis "
            f"is running in the background. Keep the user engaged — ask what angle matters most.]"
        )

        async def _delayed_narration_inject(msg: str = cue) -> None:
            await asyncio.sleep(0.1)
            await push_inject(msg)

        asyncio.create_task(_delayed_narration_inject())

    return {
        "found": len(competitors),
        "competitors": [
            {"id": c.id, "name": c.name, "website": c.website}
            for c in competitors
        ],
        "deep_research_started": True,
        "cache_hit": cache_hit,
    }


async def _deep_research_all(
    competitors: list[CompetitorCard],
    ws_emit: WsEmit,
    session_state: dict,
    session_id: str,
    push_inject=None,
) -> None:
    """Run deep research on all competitors in parallel, then auto-synthesize."""
    vision_sem = asyncio.Semaphore(2)  # at most 2 concurrent vision calls
    tasks = [
        _deep_research_competitor(c, ws_emit, session_state, vision_sem)
        for c in competitors
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Auto-synthesize once all deep research is done
    analyzed_count = sum(
        1 for c in session_state.get("competitors", {}).values() if c.analysis
    )
    if analyzed_count >= 2:
        await handle_synthesize_market_analysis(
            {"market_description": ""},
            session_id,
            ws_emit,
            session_state,
            push_inject,
        )


async def _deep_research_competitor(
    competitor: CompetitorCard,
    ws_emit: WsEmit,
    session_state: dict,
    vision_sem: asyncio.Semaphore,
) -> None:
    """Run image search + text extraction in parallel for a single competitor, then vision-analyze."""
    images_result, extract_result = await asyncio.gather(
        tavily.image_search(competitor.name, competitor.website, max_results=5),
        parallel.extract_competitor_details(competitor.website, competitor.name),
        return_exceptions=True,
    )

    # Handle images
    if isinstance(images_result, list) and images_result:
        session_state["competitors"][competitor.id].images = images_result
        await ws_emit(
            CompetitorImagesEvent(
                competitor_id=competitor.id, images=images_result
            ).model_dump()
        )

        # Vision-analyze the first valid image
        for img in images_result:
            await ws_emit(VisionStartEvent(
                competitor_name=competitor.name, image_url=img.image_url
            ).model_dump())
            async with vision_sem:
                analysis = await vision.analyze_brand_image(img.image_url, competitor.name)
            if analysis:
                session_state["competitors"][competitor.id].analysis = analysis
                await ws_emit(
                    ImageAnalyzedEvent(
                        competitor_id=competitor.id, analysis=analysis
                    ).model_dump()
                )
                break  # one analysis per competitor is enough
    elif competitor.image_url:
        # Fall back to the image_url from the original search
        await ws_emit(VisionStartEvent(
            competitor_name=competitor.name, image_url=competitor.image_url
        ).model_dump())
        async with vision_sem:
            analysis = await vision.analyze_brand_image(competitor.image_url, competitor.name)
        if analysis:
            session_state["competitors"][competitor.id].analysis = analysis
            await ws_emit(
                ImageAnalyzedEvent(
                    competitor_id=competitor.id, analysis=analysis
                ).model_dump()
            )

    # Handle text extraction result
    if isinstance(extract_result, dict):
        excerpts = extract_result.get("excerpts", [])
        if excerpts:
            session_state["competitors"][competitor.id].excerpts = excerpts
        await ws_emit(ExtractResultEvent(
            url=competitor.website,
            success=True,
            excerpt_count=len(excerpts),
        ).model_dump())


async def handle_synthesize_market_analysis(
    args: dict,
    session_id: str,
    ws_emit: WsEmit,
    session_state: dict,
    push_inject=None,
) -> dict:
    """
    Synthesize all collected visual analyses into market patterns + positioning gaps.
    Uses Gemini Flash (non-live) to reason over structured analysis data.
    """
    import os
    from google import genai
    from google.genai import types as gtypes

    market_description = args.get("market_description", "this market")

    await ws_emit(
        ToolStartEvent(tool="synthesize_market_analysis", query=market_description).model_dump()
    )

    # Collect all completed visual analyses
    competitors_with_analysis: list[CompetitorCard] = [
        c for c in session_state.get("competitors", {}).values()
        if c.analysis is not None
    ]

    if len(competitors_with_analysis) < 2:
        return {
            "success": False,
            "reason": "Need at least 2 analyzed competitors to synthesize patterns",
        }

    # Build a structured prompt with all analyses (visual + text extraction)
    analyses_text = "\n\n".join(
        f"**{c.name}** ({c.website})\n"
        f"- Colors: {', '.join(c.analysis.dominant_colors)}\n"
        f"- Typography: {c.analysis.typography_style}\n"
        f"- Photography: {c.analysis.photography_approach}\n"
        f"- Mood: {c.analysis.mood}\n"
        f"- Demographic: {c.analysis.target_demographic}\n"
        f"- Positioning: {c.analysis.positioning_summary}"
        + (
            f"\n- Brand copy: {' | '.join(c.excerpts[:3])}"
            if c.excerpts else ""
        )
        for c in competitors_with_analysis
    )

    synthesis_prompt = f"""You are analyzing the visual competitive landscape for: {market_description}

Here are the visual analyses of {len(competitors_with_analysis)} competitors:

{analyses_text}

Based on these analyses, provide:

1. **dominant_color_families**: List the 3-5 most common color families across brands (e.g. "earth tones", "crisp whites", "forest greens")
2. **common_visual_styles**: List 2-4 visual approaches that appear frequently
3. **market_mood**: One phrase describing the dominant emotional register of this market
4. **overrepresented_approaches**: What is everyone doing that creates visual sameness?
5. **positioning_gaps**: List 3-5 specific, actionable visual opportunities — what is NO ONE doing that a new entrant could own?

Return a JSON object with keys: dominant_color_families, common_visual_styles, market_mood, overrepresented_approaches (all arrays of strings), and positioning_gaps (array of strings)."""

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=synthesis_prompt,
        config=gtypes.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )

    raw = response.text
    if not raw:
        return {"success": False, "reason": "No synthesis generated"}

    data = json.loads(raw)

    patterns = MarketPatterns(
        dominant_color_families=data.get("dominant_color_families", []),
        common_visual_styles=data.get("common_visual_styles", []),
        market_mood=data.get("market_mood", ""),
        overrepresented_approaches=data.get("overrepresented_approaches", []),
    )
    gaps: list[str] = data.get("positioning_gaps", [])

    # Emit to frontend
    await ws_emit(MarketPatternsEvent(patterns=patterns).model_dump())
    await ws_emit(PositioningGapsEvent(gaps=gaps).model_dump())
    await ws_emit(ResearchCompleteEvent(session_id=session_id).model_dump())

    if push_inject:
        names = [c.name for c in competitors_with_analysis]
        gaps_preview = "; ".join(gaps[:3]) if gaps else "none identified"
        overrep_preview = "; ".join(patterns.overrepresented_approaches[:2]) if patterns.overrepresented_approaches else "none"
        summary = (
            f"[Research complete. "
            f"Analyzed {len(names)} competitors: {', '.join(names)}. "
            f"Market mood: {patterns.market_mood}. "
            f"Dominant color families: {', '.join(patterns.dominant_color_families[:3])}. "
            f"What everyone is doing (visual sameness): {overrep_preview}. "
            f"Top positioning gaps (white space): {gaps_preview}. "
            f"Please now speak a warm, natural spoken summary of these findings — "
            f"how the market looks visually, what the dominant aesthetic is, "
            f"and the clearest opportunities for differentiation. Be specific and opinionated.]"
        )
        await push_inject(summary)

    return {
        "success": True,
        "patterns": patterns.model_dump(),
        "positioning_gaps": gaps,
    }


# ── Dispatch table ────────────────────────────────────────────────────────────

TOOL_HANDLERS: dict[str, Any] = {
    "search_competitors": handle_search_competitors,
}


async def dispatch(
    tool_name: str,
    tool_args: dict,
    session_id: str,
    ws_emit: WsEmit,
    session_state: dict,
    push_inject=None,
) -> dict:
    """Route a Gemini function call to the correct handler."""
    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        return await handler(tool_args, session_id, ws_emit, session_state, push_inject)
    except Exception as e:
        return {"error": str(e), "tool": tool_name}
