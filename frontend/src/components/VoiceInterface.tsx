import { useEffect, useRef, useState } from "react";

interface Props {
  isRecording: boolean;
  isMuted: boolean;
  connected: boolean;
  transcripts: Array<{ text: string; role: "user" | "agent" }>;
  activeTool: string | null;
  onStart: () => void;
  onStop: () => void;
  onMute: () => void;
  analyserNode: AnalyserNode | null;
  onTextSubmit: (text: string) => void;
}

export function VoiceInterface({
  isRecording,
  isMuted,
  connected,
  transcripts,
  activeTool,
  onStart,
  onStop,
  onMute,
  analyserNode,
  onTextSubmit,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [textDraft, setTextDraft] = useState("");

  // Audio visualizer
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !analyserNode) return;

    const ctx = canvas.getContext("2d")!;
    const bufferLength = analyserNode.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      rafRef.current = requestAnimationFrame(draw);
      analyserNode.getByteFrequencyData(dataArray);

      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const barWidth = (canvas.width / bufferLength) * 2.5;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255) * canvas.height;
        const alpha = 0.4 + (dataArray[i] / 255) * 0.6;
        ctx.fillStyle = `rgba(99, 102, 241, ${alpha})`;
        ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
        x += barWidth + 1;
      }
    };
    draw();

    return () => cancelAnimationFrame(rafRef.current);
  }, [analyserNode]);

  // Auto-scroll transcript to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcripts]);

  // Clear canvas when not recording
  useEffect(() => {
    if (!isRecording && canvasRef.current) {
      const ctx = canvasRef.current.getContext("2d")!;
      ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
    }
  }, [isRecording]);

  const handleTextSubmit = () => {
    const trimmed = textDraft.trim();
    if (!trimmed || !connected) return;
    onTextSubmit(trimmed);
    setTextDraft("");
  };

  const handleToggle = () => {
    if (isRecording) {
      onStop();
    } else {
      onStart();
    }
  };

  return (
    <div className="voice-interface">
      <div className="connection-status">
        <span className={`dot ${connected ? "connected" : "disconnected"}`} />
        <span>{connected ? "Connected" : "Connecting…"}</span>
        {activeTool && (
          <span className="active-tool">
            ⚡ {activeTool.replace(/_/g, " ")}
          </span>
        )}
      </div>

      <canvas
        ref={canvasRef}
        className="visualizer"
        width={300}
        height={60}
      />

      <div className="mic-controls">
        <button
          className={`mic-btn ${isRecording ? "recording" : ""}`}
          onClick={handleToggle}
          disabled={!connected}
          aria-label={isRecording ? "Stop recording" : "Start recording"}
        >
          {isRecording ? "⏹ Stop" : "🎙 Talk to Scout"}
        </button>
        {isRecording && (
          <button
            className={`mute-btn ${isMuted ? "muted" : ""}`}
            onClick={onMute}
            aria-label={isMuted ? "Unmute microphone" : "Mute microphone"}
          >
            {isMuted ? "🔇 Unmute" : "🔈 Mute"}
          </button>
        )}
      </div>

      <div className="text-input-row">
        <input
          className="text-cmd-input"
          placeholder="Type a command…"
          value={textDraft}
          onChange={(e) => setTextDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleTextSubmit()}
          disabled={!connected}
        />
        <button
          className="text-send-btn"
          onClick={handleTextSubmit}
          disabled={!connected || !textDraft.trim()}
          aria-label="Send"
        >▶</button>
      </div>

      <div className="transcript-feed">
        {transcripts.map((t, i) => (
          <div key={i} className={`transcript-line ${t.role}`}>
            <span className="role-label">{t.role === "user" ? "You" : "Scout"}</span>
            <span className="transcript-text">{t.text}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
