"""api/websocket.py — WebSocket endpoint for real-time analysis (v6.0-03).

Streams pipeline progress to connected clients. Protocol:

Client sends:
  {"type": "analyse", "profile": {...}, "assumptions": {...}}

Server streams:
  {"type": "progress", "stage": "cashflow", "status": "running", "index": 3, "total": 16}
  {"type": "progress", "stage": "cashflow", "status": "complete", "index": 3, "total": 16, "duration_ms": 12.5}
  ...
  {"type": "result", "report": {...}}
  {"type": "error", "detail": "..."}
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from engine.pipeline_streaming import StageUpdate, get_stage_names, run_pipeline_streaming

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/analyse")
async def ws_analyse(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming analysis."""
    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await _send_error(websocket, "Invalid JSON")
                continue

            msg_type = message.get("type")
            if msg_type == "analyse":
                await _handle_analyse(websocket, message)
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await _send_error(websocket, f"Unknown message type: {msg_type}")

    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected")
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
        try:
            await _send_error(websocket, str(exc))
            await websocket.close()
        except Exception:
            pass


async def _handle_analyse(websocket: WebSocket, message: dict[str, Any]) -> None:
    """Run the streaming pipeline and send progress updates."""
    profile = message.get("profile")
    if not profile or not isinstance(profile, dict):
        await _send_error(websocket, "Missing or invalid 'profile' field")
        return

    assumptions = message.get("assumptions")
    stage_names = get_stage_names()
    total = len(stage_names)

    try:
        for update in run_pipeline_streaming(profile, assumptions_override=assumptions):
            index = stage_names.index(update.stage) if update.stage in stage_names else -1
            payload = _update_to_dict(update, index, total)

            if update.stage == "report" and update.status == "complete" and update.result:
                await websocket.send_json({
                    "type": "progress",
                    "stage": "report",
                    "status": "complete",
                    "index": index,
                    "total": total,
                    "duration_ms": update.duration_ms,
                })
                await websocket.send_json({
                    "type": "result",
                    "report": update.result,
                })
            else:
                await websocket.send_json(payload)

    except Exception as exc:
        logger.error("Pipeline error during WebSocket analysis: %s", exc)
        await _send_error(websocket, f"Pipeline failed: {exc}")


def _update_to_dict(update: StageUpdate, index: int, total: int) -> dict[str, Any]:
    """Convert a StageUpdate to a JSON-serialisable dict."""
    d: dict[str, Any] = {
        "type": "progress",
        "stage": update.stage,
        "status": update.status,
        "index": index,
        "total": total,
    }
    if update.duration_ms:
        d["duration_ms"] = update.duration_ms
    if update.error:
        d["error"] = update.error
    return d


async def _send_error(websocket: WebSocket, detail: str) -> None:
    """Send an error message to the WebSocket client."""
    await websocket.send_json({"type": "error", "detail": detail})
