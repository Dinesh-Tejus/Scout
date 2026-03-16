"""
ScoutSession manages a single user's WebSocket ↔ Gemini Live connection.

Responsibilities:
- Proxy browser PCM audio (16kHz) to Gemini Live
- Receive audio responses (24kHz PCM) and send back to browser
- Intercept function calls → dispatch to tool handlers → return results to Gemini
- Emit structured JSON events to the browser as research progresses
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from fastapi import WebSocket

from google import genai
from google.genai import types

from agent.prompts import SCOUT_SYSTEM_PROMPT, TOOL_DECLARATIONS
from agent import tools as tool_dispatcher
from models import AgentThinkingEvent, AudioEvent, ErrorEvent, InterruptEvent, TranscriptEvent

logger = logging.getLogger(__name__)

_LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-09-2025"

_GEMINI_CONFIG = {
    "response_modalities": ["AUDIO"],
    "input_audio_transcription": {},
    "output_audio_transcription": {},
    "system_instruction": SCOUT_SYSTEM_PROMPT,
    "tools": [{"function_declarations": TOOL_DECLARATIONS}],
    "speech_config": types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
        )
    ),
}


class ScoutSession:
    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.websocket = websocket
        self.audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.text_queue: asyncio.Queue[str] = asyncio.Queue()
        self.inject_queue: asyncio.Queue[str] = asyncio.Queue()
        self.session_state: dict = {"competitors": {}}
        self._running = False

    async def inject_context(self, text: str) -> None:
        """Send context to Gemini Live without showing in transcript."""
        await self.inject_queue.put(text)

    async def ws_emit(self, payload: dict) -> None:
        """Send a JSON event to the browser WebSocket."""
        try:
            await self.websocket.send_text(json.dumps(payload))
        except Exception as exc:
            logger.warning("ws_emit failed: %s", exc)

    async def run(self) -> None:
        """Main entry point: load Firestore state (if configured), start Gemini Live session."""

        self._running = True

        client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],

        )

        try:
            async with client.aio.live.connect(
                model=_LIVE_MODEL,
                config=_GEMINI_CONFIG,
            ) as live_session:
                # Run sender and receiver concurrently
                await asyncio.gather(
                    self._audio_sender(live_session),
                    self._response_receiver(live_session),
                )
        except Exception as exc:
            logger.error("Gemini Live session error: %s", exc)
            await self.ws_emit(ErrorEvent(message=str(exc)).model_dump())

    async def _audio_sender(self, live_session) -> None:
        """Drain inject_queue, text_queue, and audio_queue, forwarding input to Gemini Live."""
        while self._running:
            # Internal context injections (no transcript)
            try:
                text = self.inject_queue.get_nowait()
                await live_session.send_realtime_input(text=text)
                continue
            except asyncio.QueueEmpty:
                pass

            # User-typed text (with transcript)
            try:
                text = self.text_queue.get_nowait()
                await self.ws_emit(TranscriptEvent(text=text, role="user").model_dump())
                await live_session.send_realtime_input(text=text)
                continue
            except asyncio.QueueEmpty:
                pass

            # Audio
            try:
                pcm_bytes = await asyncio.wait_for(self.audio_queue.get(), timeout=1.0)
                await live_session.send_realtime_input(
                    audio=types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")
                )
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                logger.warning("audio_sender error: %s", exc)
                break

    async def _response_receiver(self, live_session) -> None:
        """
        Receive messages from Gemini Live:
        - audio data  → forward to browser
        - text        → emit transcript event
        - tool calls  → dispatch, return results

        The outer while loop re-enters receive() after each model turn exhausts
        the inner generator, enabling multi-turn conversations.
        """
        while self._running:
            try:
                async for response in live_session.receive():
                    # Barge-in: Gemini VAD detected user speaking mid-playback
                    if response.server_content and response.server_content.interrupted:
                        await self.ws_emit(InterruptEvent().model_dump())

                    # Audio response chunk
                    if response.data is not None:
                        encoded = base64.b64encode(response.data).decode()
                        await self.ws_emit(AudioEvent(data=encoded).model_dump())

                    # Transcription events
                    if response.server_content:
                        sc = response.server_content
                        if sc.input_transcription and sc.input_transcription.text:
                            await self.ws_emit(
                                TranscriptEvent(text=sc.input_transcription.text, role="user").model_dump()
                            )
                        if sc.output_transcription and sc.output_transcription.text:
                            await self.ws_emit(
                                TranscriptEvent(text=sc.output_transcription.text, role="agent").model_dump()
                            )

                    # Capture Gemini thinking/reasoning parts (currently dropped with warning)
                    if response.server_content and response.server_content.model_turn:
                        for part in (response.server_content.model_turn.parts or []):
                            if getattr(part, "thought", False) and part.text:
                                await self.ws_emit(AgentThinkingEvent(text=part.text).model_dump())

                    # Function calls
                    if response.tool_call:
                        await self._handle_tool_calls(live_session, response.tool_call)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("response_receiver error: %s", exc)
                if not self._running:
                    break

    async def _handle_tool_calls(self, live_session, tool_call) -> None:
        """
        Process all function calls in a tool_call response.
        Dispatches each to the appropriate handler and returns results to Gemini.
        """
        function_responses = []

        for fc in tool_call.function_calls:
            result = await tool_dispatcher.dispatch(
                tool_name=fc.name,
                tool_args=dict(fc.args) if fc.args else {},
                session_id=self.session_id,
                ws_emit=self.ws_emit,
                session_state=self.session_state,
                push_inject=self.inject_context,
            )

            function_responses.append(
                types.FunctionResponse(
                    id=fc.id,
                    name=fc.name,
                    response={"result": result},
                )
            )

        await live_session.send_tool_response(function_responses=function_responses)

    def stop(self) -> None:
        self._running = False

    async def push_audio(self, pcm_bytes: bytes) -> None:
        """Called from the WebSocket handler to enqueue incoming audio."""
        await self.audio_queue.put(pcm_bytes)

    async def push_text(self, text: str) -> None:
        """Called from the WebSocket handler to enqueue a text command."""
        await self.text_queue.put(text)
