// Shared TypeScript types for WebSocket events

export interface VisualAnalysis {
  dominant_colors: string[];
  typography_style: string;
  photography_approach: string;
  mood: string;
  target_demographic: string;
  positioning_summary: string;
}

export interface CompetitorImage {
  image_url: string;
  source_url: string;
  title?: string;
}

export interface CompetitorCard {
  id: string;
  name: string;
  website: string;
  image_url: string;
  images: CompetitorImage[];
  analysis: VisualAnalysis | null;
}

export interface MarketPatterns {
  dominant_color_families: string[];
  common_visual_styles: string[];
  market_mood: string;
  overrepresented_approaches: string[];
}

// WebSocket events — Backend → Browser
export type WSEvent =
  | { type: "audio"; data: string }
  | { type: "interrupt" }
  | { type: "transcript"; text: string; role: "user" | "agent" }
  | { type: "tool_start"; tool: string; query: string }
  | { type: "competitor_found"; competitor: CompetitorCard }
  | { type: "image_analyzed"; competitor_id: string; analysis: VisualAnalysis }
  | { type: "market_patterns"; patterns: MarketPatterns }
  | { type: "positioning_gaps"; gaps: string[] }
  | { type: "research_complete"; session_id: string }
  | { type: "error"; message: string }
  | { type: "agent_thinking"; text: string }
  | { type: "search_result"; query: string; found: number; names: string[] }
  | { type: "vision_start"; competitor_name: string; image_url: string }
  | { type: "extract_result"; url: string; success: boolean; excerpt_count: number }
  | { type: "competitor_images"; competitor_id: string; images: CompetitorImage[] }
  | { type: "cache_hit"; query: string; competitor_count: number; cached_at: string }
  | { type: "research_aborted" };

// WebSocket messages — Browser → Backend
export type WSOutgoing =
  | { type: "audio"; data: string }
  | { type: "control"; action: "start" | "stop" | "interrupt" | "abort_research" }
  | { type: "text_input"; text: string };

export interface ActivityEntry {
  id: string;
  timestamp: number;
  category: "thinking" | "search" | "result" | "vision" | "extract" | "tool" | "info" | "error" | "cache";
  label: string;
  detail?: string;
  rawData?: unknown;
}
