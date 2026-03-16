import { useCallback, useEffect, useRef, useState } from "react";
import type { WSEvent, WSOutgoing, CompetitorCard, MarketPatterns, VisualAnalysis, ActivityEntry, CompetitorImage } from "../types";

function formatRelativeTime(isoTimestamp: string): string {
  const diff = Date.now() - new Date(isoTimestamp).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export interface ResearchState {
  competitors: Record<string, CompetitorCard>;
  patterns: MarketPatterns | null;
  positioning_gaps: string[];
  is_complete: boolean;
  active_tool: string | null;
  transcripts: Array<{ text: string; role: "user" | "agent" }>;
  error: string | null;
  activityLog: ActivityEntry[];
}

const INITIAL_STATE: ResearchState = {
  competitors: {},
  patterns: null,
  positioning_gaps: [],
  is_complete: false,
  active_tool: null,
  transcripts: [],
  error: null,
  activityLog: [],
};

export function useWebSocket(sessionId: string) {
  const ws = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [research, setResearch] = useState<ResearchState>(INITIAL_STATE);

  // Expose audio callback for the audio hook
  const onAudioChunk = useRef<((data: string) => void) | null>(null);
  // Expose interrupt callback for the audio hook
  const onInterrupt = useRef<(() => void) | null>(null);

  const addActivity = (
    prev: ResearchState,
    entry: Omit<ActivityEntry, "id" | "timestamp">,
  ): ResearchState => {
    const newEntry = { id: crypto.randomUUID(), timestamp: Date.now(), ...entry };
    return { ...prev, activityLog: [newEntry, ...prev.activityLog].slice(0, 30) };
  };

  const connect = useCallback(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const host = import.meta.env.VITE_WS_HOST ?? window.location.host;
    const url = `${proto}://${host}/ws/${sessionId}`;

    const socket = new WebSocket(url);
    ws.current = socket;

    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);

    socket.onmessage = (evt) => {
      let event: WSEvent;
      try {
        event = JSON.parse(evt.data) as WSEvent;
      } catch {
        return;
      }

      switch (event.type) {
        case "audio":
          onAudioChunk.current?.(event.data);
          break;

        case "interrupt":
          onInterrupt.current?.();
          break;

        case "transcript":
          setResearch((s) => {
            const last = s.transcripts[s.transcripts.length - 1];
            const isSameRole = !!last && last.role === event.role;
            const newText = isSameRole
              ? last.text + (last.text.endsWith(" ") || event.text.startsWith(" ") ? "" : " ") + event.text
              : event.text;
            const transcripts = isSameRole
              ? [...s.transcripts.slice(0, -1), { text: newText, role: event.role }]
              : [...s.transcripts, { text: newText, role: event.role }];
            const next = { ...s, transcripts };
            if (event.role === "user" && !isSameRole) {
              return addActivity(next, {
                category: "search",
                label: `You: ${event.text.slice(0, 80)}`,
              });
            }
            return next;
          });
          break;

        case "tool_start":
          setResearch((s) =>
            addActivity({ ...s, active_tool: event.tool }, {
              category: "tool",
              label: `Tool: ${event.tool}`,
              detail: event.query || undefined,
            }),
          );
          break;

        case "agent_thinking":
          setResearch((s) =>
            addActivity(s, {
              category: "thinking",
              label: "Agent thinking...",
              detail: event.text.slice(0, 120),
              rawData: event.text,
            }),
          );
          break;

        case "search_result":
          setResearch((s) =>
            addActivity(s, {
              category: "result",
              label: `Tavily: ${event.found} found for "${event.query}"`,
              detail: event.names.join(", "),
            }),
          );
          break;

        case "competitor_found":
          setResearch((s) =>
            addActivity(
              { ...s, competitors: { ...s.competitors, [event.competitor.id]: event.competitor } },
              {
                category: "info",
                label: `Discovered: ${event.competitor.name}`,
                detail: event.competitor.website,
              },
            ),
          );
          break;

        case "vision_start":
          setResearch((s) =>
            addActivity(s, {
              category: "vision",
              label: `Analyzing ${event.competitor_name}`,
              detail: event.image_url,
            }),
          );
          break;

        case "image_analyzed": {
          const { competitor_id, analysis } = event as {
            type: "image_analyzed";
            competitor_id: string;
            analysis: VisualAnalysis;
          };
          setResearch((s) => {
            const existing = s.competitors[competitor_id];
            const updated = existing
              ? {
                  ...s,
                  competitors: {
                    ...s.competitors,
                    [competitor_id]: { ...existing, analysis },
                  },
                }
              : s;
            return addActivity(updated, {
              category: "vision",
              label: `Vision done: ${competitor_id}`,
            });
          });
          break;
        }

        case "competitor_images": {
          const { competitor_id, images } = event as {
            type: "competitor_images";
            competitor_id: string;
            images: CompetitorImage[];
          };
          setResearch((s) => {
            const existing = s.competitors[competitor_id];
            const updated = existing
              ? {
                  ...s,
                  competitors: {
                    ...s.competitors,
                    [competitor_id]: { ...existing, images },
                  },
                }
              : s;
            return addActivity(updated, {
              category: "vision",
              label: "Images found",
              detail: `${images.length} images for competitor`,
            });
          });
          break;
        }

        case "extract_result":
          setResearch((s) =>
            addActivity(s, {
              category: "extract",
              label: `Extracted from ${(() => { try { return new URL(event.url).hostname; } catch { return event.url; } })()}`,
              detail: `${event.excerpt_count} excerpts`,
            }),
          );
          break;

        case "market_patterns":
          setResearch((s) =>
            addActivity({ ...s, patterns: event.patterns, active_tool: null }, {
              category: "info",
              label: "Market patterns synthesized",
            }),
          );
          break;

        case "positioning_gaps":
          setResearch((s) => ({ ...s, positioning_gaps: event.gaps }));
          break;

        case "research_complete":
          setResearch((s) =>
            addActivity({ ...s, is_complete: true, active_tool: null }, {
              category: "info",
              label: "Research complete",
            }),
          );
          break;

        case "cache_hit":
          setResearch((s) =>
            addActivity(s, {
              category: "cache",
              label: `Cached results for "${event.query}"`,
              detail: `${event.competitor_count} competitors · saved ${formatRelativeTime(event.cached_at)}`,
            }),
          );
          break;

        case "error":
          setResearch((s) =>
            addActivity({ ...s, error: event.message, active_tool: null }, {
              category: "error",
              label: `Error: ${event.message}`,
            }),
          );
          break;
      }
    };
  }, [sessionId]);

  const send = useCallback((msg: WSOutgoing) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg));
    }
  }, []);

  const disconnect = useCallback(() => {
    ws.current?.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      ws.current?.close();
    };
  }, [connect]);

  return { connected, research, send, onAudioChunk, onInterrupt, disconnect };
}
