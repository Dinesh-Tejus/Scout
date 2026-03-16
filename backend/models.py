from pydantic import BaseModel


class VisualAnalysis(BaseModel):
    dominant_colors: list[str]  # hex codes e.g. ["#1a1a1a", "#f5f0e8"]
    typography_style: str       # e.g. "serif/premium", "sans/modern", "script/handcrafted"
    photography_approach: str   # e.g. "lifestyle", "product-only", "flat-lay", "editorial"
    mood: str                   # e.g. "playful", "luxurious", "clinical", "earthy"
    target_demographic: str     # e.g. "health-conscious millennials", "luxury buyers 35-55"
    positioning_summary: str    # 1-2 sentence brand positioning summary


class CompetitorImage(BaseModel):
    image_url: str
    source_url: str           # page where the image was found
    title: str | None = None  # description from Tavily, if available


class CompetitorCard(BaseModel):
    id: str
    name: str
    website: str
    image_url: str
    images: list[CompetitorImage] = []
    analysis: VisualAnalysis | None = None
    excerpts: list[str] = []  # brand positioning text from parallel extraction


class MarketPatterns(BaseModel):
    dominant_color_families: list[str]
    common_visual_styles: list[str]
    market_mood: str
    overrepresented_approaches: list[str]


# ── WebSocket event payloads ──────────────────────────────────────────────────

class AudioEvent(BaseModel):
    type: str = "audio"
    data: str  # base64-encoded PCM 24kHz


class TranscriptEvent(BaseModel):
    type: str = "transcript"
    text: str
    role: str  # "user" or "agent"


class ToolStartEvent(BaseModel):
    type: str = "tool_start"
    tool: str
    query: str = ""


class CompetitorFoundEvent(BaseModel):
    type: str = "competitor_found"
    competitor: CompetitorCard


class CompetitorImagesEvent(BaseModel):
    type: str = "competitor_images"
    competitor_id: str
    images: list[CompetitorImage]


class ImageAnalyzedEvent(BaseModel):
    type: str = "image_analyzed"
    competitor_id: str
    analysis: VisualAnalysis


class MarketPatternsEvent(BaseModel):
    type: str = "market_patterns"
    patterns: MarketPatterns


class PositioningGapsEvent(BaseModel):
    type: str = "positioning_gaps"
    gaps: list[str]


class ResearchCompleteEvent(BaseModel):
    type: str = "research_complete"
    session_id: str


class AgentThinkingEvent(BaseModel):
    type: str = "agent_thinking"
    text: str


class SearchResultEvent(BaseModel):
    type: str = "search_result"
    query: str
    found: int
    names: list[str]


class VisionStartEvent(BaseModel):
    type: str = "vision_start"
    competitor_name: str
    image_url: str


class ExtractResultEvent(BaseModel):
    type: str = "extract_result"
    url: str
    success: bool
    excerpt_count: int = 0


class InterruptEvent(BaseModel):
    type: str = "interrupt"


class ErrorEvent(BaseModel):
    type: str = "error"
    message: str


# ── Incoming browser messages ─────────────────────────────────────────────────

class IncomingAudio(BaseModel):
    type: str  # "audio"
    data: str  # base64 PCM 16kHz


class IncomingControl(BaseModel):
    type: str   # "control"
    action: str  # "start" | "stop" | "interrupt"
