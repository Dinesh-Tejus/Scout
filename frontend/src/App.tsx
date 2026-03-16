import { useMemo, useRef, useState } from "react";
import { useWebSocket } from "./hooks/useWebSocket";
import { useAudio } from "./hooks/useAudio";
import { VoiceInterface } from "./components/VoiceInterface";
import { ResearchFeed } from "./components/ResearchFeed";
import { MarketPatterns } from "./components/MarketPatterns";
import { PositioningGaps } from "./components/PositioningGaps";
import { ActivityStream } from "./components/ActivityStream";
import "./App.css";

function getSessionId(): string {
  const stored = sessionStorage.getItem("scout_session_id");
  if (stored) return stored;
  const id = `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  sessionStorage.setItem("scout_session_id", id);
  return id;
}

export default function App() {
  const sessionId = useMemo(getSessionId, []);
  const { connected, research, send, onAudioChunk, onInterrupt } = useWebSocket(sessionId);
  const { isRecording, isMuted, startRecording, stopRecording, toggleMute, analyserNode } = useAudio({
    send,
    onAudioChunk,
    onInterrupt,
  });
  const [, setIsDrawerOpen] = useState(false);
  const [topHeight, setTopHeight] = useState(30); // percent
  const [leftWidth, setLeftWidth] = useState(50); // percent
  const [hDragging, setHDragging] = useState(false);
  const [vDragging, setVDragging] = useState(false);
  const mainColRef = useRef<HTMLElement>(null);
  const bottomPanelRef = useRef<HTMLDivElement>(null);

  function startHResize(e: React.MouseEvent) {
    e.preventDefault();
    setHDragging(true);
    document.body.style.userSelect = "none";
    function onMove(ev: MouseEvent) {
      if (!mainColRef.current) return;
      const rect = mainColRef.current.getBoundingClientRect();
      const pct = ((ev.clientY - rect.top) / rect.height) * 100;
      setTopHeight(Math.max(15, Math.min(80, pct)));
    }
    function onUp() {
      setHDragging(false);
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  function startVResize(e: React.MouseEvent) {
    e.preventDefault();
    setVDragging(true);
    document.body.style.userSelect = "none";
    function onMove(ev: MouseEvent) {
      if (!bottomPanelRef.current) return;
      const rect = bottomPanelRef.current.getBoundingClientRect();
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setLeftWidth(Math.max(15, Math.min(80, pct)));
    }
    function onUp() {
      setVDragging(false);
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Scout</h1>
        <p className="tagline">Voice-powered brand research</p>
      </header>

      <div className="content-area">
        <aside className="left-col">
          <VoiceInterface
            isRecording={isRecording}
            isMuted={isMuted}
            connected={connected}
            transcripts={research.transcripts}
            activeTool={research.active_tool}
            onStart={startRecording}
            onStop={stopRecording}
            onMute={toggleMute}
            analyserNode={analyserNode}
            onTextSubmit={(text) => send({ type: "text_input", text })}
            onAbortResearch={() => send({ type: "control", action: "abort_research" })}
          />
        </aside>

        <main className="main-col" ref={mainColRef}>
          <section className="images-panel" style={{ height: `${topHeight}%`, flexShrink: 0 }}>
            <ResearchFeed
              competitors={research.competitors}
              activeTool={research.active_tool}
              researchAborted={research.research_aborted}
            />
          </section>
          <div
            className={`resize-handle-h${hDragging ? " dragging" : ""}`}
            onMouseDown={startHResize}
          />
          <div className="bottom-panel" ref={bottomPanelRef} style={{ flex: 1, minHeight: 0 }}>
            <section className="market-panel" style={{ width: `${leftWidth}%`, flexShrink: 0 }}>
              {research.patterns ? (
                <MarketPatterns patterns={research.patterns} />
              ) : !research.is_complete && !research.error ? (
                <div className="panel-empty">
                  <div className="panel-empty-icon">◈</div>
                  <div className="panel-empty-title">Market Patterns</div>
                  <p className="panel-empty-sub">Visual patterns synthesize after competitors are analyzed</p>
                </div>
              ) : null}
              {research.is_complete && (
                <div className="complete-banner">✓ Research complete</div>
              )}
              {research.error && (
                <div className="error-banner">⚠ {research.error}</div>
              )}
            </section>
            <div
              className={`resize-handle-v${vDragging ? " dragging" : ""}`}
              onMouseDown={startVResize}
            />
            <section className="gaps-panel" style={{ flex: 1, minWidth: 0 }}>
              {research.positioning_gaps.length > 0 ? (
                <PositioningGaps gaps={research.positioning_gaps} />
              ) : (
                <div className="panel-empty">
                  <div className="panel-empty-icon">◎</div>
                  <div className="panel-empty-title">Positioning Gaps</div>
                  <p className="panel-empty-sub">White space opportunities appear here after research completes</p>
                </div>
              )}
            </section>
          </div>
        </main>
      </div>

      <ActivityStream activityLog={research.activityLog} onOpenChange={setIsDrawerOpen} />
    </div>
  );
}
