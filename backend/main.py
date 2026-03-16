"""
Scout backend — FastAPI app with WebSocket endpoint.

WebSocket protocol (single connection per session):
  Browser → Backend: { "type": "audio", "data": "<base64 PCM 16kHz>" }
                     { "type": "control", "action": "start"|"stop"|"interrupt" }
  Backend → Browser: see models.py for all event types
"""
import base64
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── Active sessions ───────────────────────────────────────────────────────────
_active_sessions: dict = {}
_active_tasks: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Scout backend starting")
    yield
    logger.info("Scout backend shutting down")


app = FastAPI(title="Scout", lifespan=lifespan)


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logger.info("WebSocket connected: session=%s", session_id)

    from agent.session import ScoutSession
    import asyncio

    # Cancel any existing session for this session_id
    if session_id in _active_sessions:
        _active_sessions[session_id].stop()
    if session_id in _active_tasks:
        _active_tasks[session_id].cancel()

    session = ScoutSession(session_id=session_id, websocket=websocket)
    _active_sessions[session_id] = session

    # Start the Gemini Live session as a background task
    session_task = asyncio.create_task(session.run())
    _active_tasks[session_id] = session_task

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            msg_type = message.get("type")

            if msg_type == "audio":
                # Decode base64 PCM and push to session audio queue
                pcm_bytes = base64.b64decode(message["data"])
                await session.push_audio(pcm_bytes)

            elif msg_type == "text_input":
                text = message.get("text", "").strip()
                if text:
                    await session.push_text(text)

            elif msg_type == "control":
                action = message.get("action")
                if action == "stop":
                    session.stop()
                    break
                elif action == "interrupt":
                    # Clear the audio queue to interrupt current playback
                    while not session.audio_queue.empty():
                        try:
                            session.audio_queue.get_nowait()
                        except Exception:
                            break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session=%s", session_id)
    except Exception as exc:
        logger.error("WebSocket error session=%s: %s", session_id, exc)
    finally:
        session.stop()
        session_task.cancel()
        _active_sessions.pop(session_id, None)
        _active_tasks.pop(session_id, None)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "active_sessions": len(_active_sessions)}


# ── Static files (served after WS and API routes) ────────────────────────────

_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
