#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WebSocket live pour la gamification FeedFormula AI."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

try:
    from database import get_db, get_user_by_id, serialize_user
except Exception:  # pragma: no cover - fallback import direct
    from .database import get_db, get_user_by_id, serialize_user  # type: ignore

router = APIRouter(tags=["gamification-live"])

_CONNECTIONS: Dict[str, Set[WebSocket]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _safe_send(websocket: WebSocket, payload: Dict[str, Any]) -> None:
    try:
        await websocket.send_json(payload)
    except Exception:
        raise


async def _broadcast(user_id: str, payload: Dict[str, Any]) -> None:
    sockets = list(_CONNECTIONS.get(user_id, set()))
    if not sockets:
        return
    dead: list[WebSocket] = []
    for ws in sockets:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    if dead:
        remaining = _CONNECTIONS.get(user_id, set())
        for ws in dead:
            remaining.discard(ws)
        if not remaining:
            _CONNECTIONS.pop(user_id, None)


def notify_user_update(user_id: str, payload: Dict[str, Any]) -> None:
    """Point d'entrée synchronisable appelé depuis les routes métier."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_broadcast(str(user_id), payload))


async def _send_snapshot(websocket: WebSocket, user_id: str) -> None:
    db = next(get_db())
    try:
        user = get_user_by_id(db, user_id)
        if user is None:
            await _safe_send(
                websocket,
                {
                    "type": "error",
                    "message": "Utilisateur introuvable.",
                    "timestamp": _now_iso(),
                },
            )
            return

        await _safe_send(
            websocket,
            {
                "type": "snapshot",
                "user": serialize_user(user),
                "timestamp": _now_iso(),
            },
        )
    finally:
        db.close()


@router.websocket("/ws/gamification/{user_id}")
async def gamification_websocket(websocket: WebSocket, user_id: str) -> None:
    await websocket.accept()
    uid = str(user_id or "").strip()
    if not uid:
        await websocket.close(code=1008)
        return

    _CONNECTIONS.setdefault(uid, set()).add(websocket)
    try:
        await _send_snapshot(websocket, uid)
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=8)
            except asyncio.TimeoutError:
                # Polling léger pour envoyer un état à jour.
                db = next(get_db())
                try:
                    user = get_user_by_id(db, uid)
                    if user is not None:
                        await _safe_send(
                            websocket,
                            {
                                "type": "heartbeat",
                                "timestamp": _now_iso(),
                                "user": serialize_user(user),
                            },
                        )
                finally:
                    db.close()
            except WebSocketDisconnect:
                break
            except Exception:
                break
    finally:
        sockets = _CONNECTIONS.get(uid, set())
        sockets.discard(websocket)
        if not sockets:
            _CONNECTIONS.pop(uid, None)


__all__ = ["router", "notify_user_update"]
