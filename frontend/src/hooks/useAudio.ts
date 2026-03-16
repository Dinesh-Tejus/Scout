import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import type { WSOutgoing } from "../types";

const CAPTURE_SAMPLE_RATE = 16000;
const PLAYBACK_SAMPLE_RATE = 24000;
const BUFFER_SIZE = 4096;

interface UseAudioOptions {
  send: (msg: WSOutgoing) => void;
  onAudioChunk: RefObject<((data: string) => void) | null>;
  onInterrupt: RefObject<(() => void) | null>;
}

export function useAudio({ send, onAudioChunk, onInterrupt }: UseAudioOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [analyserNode, setAnalyserNode] = useState<AnalyserNode | null>(null);

  const captureCtx = useRef<AudioContext | null>(null);
  const playbackCtx = useRef<AudioContext | null>(null);
  const processorNode = useRef<ScriptProcessorNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const isMutedRef = useRef(false);

  // Tracks all scheduled-but-not-yet-finished AudioBufferSourceNodes
  const activeSourcesRef = useRef<AudioBufferSourceNode[]>([]);
  // Playback clock: next chunk starts where the previous one ends
  const nextStartTimeRef = useRef<number>(0);

  // ── Playback setup ─────────────────────────────────────────────────────────

  const stopAllAudio = useCallback(() => {
    activeSourcesRef.current.forEach((src) => {
      try { src.stop(); src.disconnect(); } catch { /* already ended */ }
    });
    activeSourcesRef.current = [];
    if (playbackCtx.current) {
      nextStartTimeRef.current = playbackCtx.current.currentTime;
    }
  }, []);

  // Register handlers so the WS hook can call them
  useEffect(() => {
    onAudioChunk.current = (b64: string) => playPcmChunk(b64);
    onInterrupt.current = stopAllAudio;
    return () => {
      onAudioChunk.current = null;
      onInterrupt.current = null;
    };
  });

  const playPcmChunk = useCallback((b64: string) => {
    if (!playbackCtx.current) {
      playbackCtx.current = new AudioContext({ sampleRate: PLAYBACK_SAMPLE_RATE });
      nextStartTimeRef.current = playbackCtx.current.currentTime;
    }
    const ctx = playbackCtx.current;

    // Decode base64 → ArrayBuffer → Int16 PCM → Float32
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

    const int16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768.0;

    const buffer = ctx.createBuffer(1, float32.length, PLAYBACK_SAMPLE_RATE);
    buffer.copyToChannel(float32, 0);

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);

    // Schedule sequentially so chunks don't overlap
    const startTime = Math.max(ctx.currentTime, nextStartTimeRef.current);
    source.start(startTime);
    nextStartTimeRef.current = startTime + buffer.duration;

    // Track so we can stop mid-playback on interruption
    activeSourcesRef.current.push(source);
    source.onended = () => {
      activeSourcesRef.current = activeSourcesRef.current.filter((s) => s !== source);
    };
  }, []);

  // ── Capture setup ──────────────────────────────────────────────────────────

  const startRecording = useCallback(async () => {
    if (isRecording) return;

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    streamRef.current = stream;

    const ctx = new AudioContext({ sampleRate: CAPTURE_SAMPLE_RATE });
    captureCtx.current = ctx;

    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    setAnalyserNode(analyser);

    const source = ctx.createMediaStreamSource(stream);
    // ScriptProcessorNode is deprecated but universally supported for PCM capture
    const processor = ctx.createScriptProcessor(BUFFER_SIZE, 1, 1);
    processorNode.current = processor;

    processor.onaudioprocess = (e) => {
      if (isMutedRef.current) return;
      const input = e.inputBuffer.getChannelData(0);
      // Convert float32 → int16 PCM
      const int16 = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        int16[i] = s < 0 ? s * 32768 : s * 32767;
      }
      // Base64 encode and send
      const bytes = new Uint8Array(int16.buffer);
      let binary = "";
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
      const b64 = btoa(binary);
      send({ type: "audio", data: b64 });
    };

    source.connect(analyser);
    source.connect(processor);
    processor.connect(ctx.destination);

    setIsRecording(true);
  }, [isRecording, send]);

  const toggleMute = useCallback(() => {
    isMutedRef.current = !isMutedRef.current;
    setIsMuted(isMutedRef.current);
  }, []);

  const stopRecording = useCallback(() => {
    isMutedRef.current = false;
    setIsMuted(false);
    processorNode.current?.disconnect();
    processorNode.current = null;

    captureCtx.current?.close();
    captureCtx.current = null;

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    setAnalyserNode(null);
    setIsRecording(false);
  }, []);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopRecording();
      playbackCtx.current?.close();
    };
  }, [stopRecording]);

  return { isRecording, isMuted, startRecording, stopRecording, toggleMute, analyserNode };
}
