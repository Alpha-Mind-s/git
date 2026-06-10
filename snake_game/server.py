"""
贪吃蛇游戏 Web 服务。

提供 REST API 和 WebSocket 接口，支持多局游戏并发。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from snake_game.game import Direction, GameConfig, GameStatus, SnakeGame
from snake_game.models import (
    CreateGameRequest,
    DirectionChange,
    GameStateResponse,
    ErrorResponse,
)

logger = logging.getLogger("snake_game")


class GameSession:
    """管理一局游戏的整个生命周期"""

    def __init__(self, config: GameConfig) -> None:
        self.game = SnakeGame(config=config, game_id=uuid.uuid4().hex[:12])
        self._connections: list[WebSocket] = []
        self._tick_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def add_connection(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.append(ws)

    async def remove_connection(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.remove(ws)

    async def broadcast(self, message: dict) -> None:
        async with self._lock:
            stale: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_json(message)
                except Exception:
                    stale.append(ws)
            for ws in stale:
                self._connections.remove(ws)

    async def start_tick_loop(self, timestamp: float = 0.0) -> None:
        self.game.start(timestamp)
        self._tick_task = asyncio.create_task(self._tick_loop())

    def stop_tick_loop(self) -> None:
        if self._tick_task and not self._tick_task.done():
            self._tick_task.cancel()
            self._tick_task = None

    async def _tick_loop(self) -> None:
        """游戏主循环"""
        while True:
            if self.game.status == GameStatus.GAME_OVER:
                state = self.game.get_state(
                    game_id=self.game.game_id,
                    timestamp=time.time(),
                )
                await self.broadcast({
                    "type": "game_over",
                    "data": GameStateResponse.from_game_state(state).model_dump(),
                })
                break

            if self.game.status == GameStatus.PLAYING:
                tick_start = time.time()
                self.game.tick(tick_start)
                state = self.game.get_state(
                    game_id=self.game.game_id,
                    timestamp=tick_start,
                )
                await self.broadcast({
                    "type": "state",
                    "data": GameStateResponse.from_game_state(state).model_dump(),
                })

                # 根据速度计算下一次 tick 的等待时间
                interval = 1.0 / self.game.speed
                elapsed = time.time() - tick_start
                await asyncio.sleep(max(0, interval - elapsed))
            else:
                # PAUSED / WAITING
                await asyncio.sleep(0.1)


# ── 全局游戏管理 ──────────────────────────────────────────

_games: dict[str, GameSession] = {}
_stale_cleanup_task: Optional[asyncio.Task] = None


def _create_session(config: GameConfig) -> GameSession:
    session = GameSession(config)
    _games[session.game.game_id] = session
    return session


async def _cleanup_stale_games() -> None:
    """定期清理结束超过 5 分钟的游戏"""
    while True:
        await asyncio.sleep(60)
        now = time.time()
        stale = [
            gid for gid, sess in _games.items()
            if (sess.game.status == GameStatus.GAME_OVER
                and now - sess.game.updated_at > 300)
        ]
        for gid in stale:
            session = _games.pop(gid, None)
            if session:
                session.stop_tick_loop()
                logger.info("清理过期游戏 %s", gid)


# ── FastAPI 应用 ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _stale_cleanup_task
    _stale_cleanup_task = asyncio.create_task(_cleanup_stale_games())
    yield
    _stale_cleanup_task.cancel()
    # 清理所有游戏
    for session in _games.values():
        session.stop_tick_loop()
    _games.clear()


app = FastAPI(
    title="Snake Game Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST API ──────────────────────────────────────────────


@app.get("/api/games", response_model=list[GameStateResponse])
async def list_games():
    """获取所有活跃游戏的状态"""
    results: list[GameStateResponse] = []
    now = time.time()
    for gid, session in list(_games.items()):
        state = session.game.get_state(game_id=gid, timestamp=now)
        results.append(GameStateResponse.from_game_state(state))
    return results


@app.post(
    "/api/games",
    response_model=GameStateResponse,
    status_code=201,
)
async def create_game(req: CreateGameRequest):
    """创建新游戏"""
    config = GameConfig(
        width=req.width,
        height=req.height,
        initial_speed=req.initial_speed,
        wrap_walls=req.wrap_walls,
        food_count=req.food_count,
    )
    session = _create_session(config)
    await session.start_tick_loop(timestamp=time.time())
    state = session.game.get_state(
        game_id=session.game.game_id,
        timestamp=time.time(),
    )
    logger.info("创建游戏 %s (%dx%d)", session.game.game_id, req.width, req.height)
    return GameStateResponse.from_game_state(state)


@app.get(
    "/api/games/{game_id}",
    response_model=GameStateResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_game(game_id: str):
    """获取指定游戏的状态"""
    session = _games.get(game_id)
    if not session:
        raise HTTPException(404, f"游戏 {game_id} 不存在")
    state = session.game.get_state(game_id=game_id, timestamp=time.time())
    return GameStateResponse.from_game_state(state)


@app.delete(
    "/api/games/{game_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
async def delete_game(game_id: str):
    """删除指定游戏"""
    session = _games.pop(game_id, None)
    if not session:
        raise HTTPException(404, f"游戏 {game_id} 不存在")
    session.stop_tick_loop()
    logger.info("删除游戏 %s", game_id)


@app.post(
    "/api/games/{game_id}/direction",
    response_model=GameStateResponse,
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def change_direction(game_id: str, req: DirectionChange):
    """改变蛇的方向"""
    session = _games.get(game_id)
    if not session:
        raise HTTPException(404, f"游戏 {game_id} 不存在")
    direction = Direction(req.direction.upper())
    ok = session.game.change_direction(direction)
    if not ok:
        raise HTTPException(400, "无法改变方向（游戏未开始、方向相反或操作过快）")
    state = session.game.get_state(game_id=game_id, timestamp=time.time())
    return GameStateResponse.from_game_state(state)


@app.post("/api/games/{game_id}/pause", response_model=GameStateResponse)
async def pause_game(game_id: str):
    """暂停游戏"""
    session = _games.get(game_id)
    if not session:
        raise HTTPException(404, f"游戏 {game_id} 不存在")
    session.game.pause()
    state = session.game.get_state(game_id=game_id, timestamp=time.time())
    return GameStateResponse.from_game_state(state)


@app.post("/api/games/{game_id}/resume", response_model=GameStateResponse)
async def resume_game(game_id: str):
    """恢复游戏"""
    session = _games.get(game_id)
    if not session:
        raise HTTPException(404, f"游戏 {game_id} 不存在")
    session.game.resume()
    state = session.game.get_state(game_id=game_id, timestamp=time.time())
    return GameStateResponse.from_game_state(state)


# ── WebSocket ─────────────────────────────────────────────


@app.websocket("/ws/{game_id}")
async def game_websocket(ws: WebSocket, game_id: str):
    """
    WebSocket 实时游戏连接。

    客户端发送的 JSON 消息格式:
    - {"type": "direction", "direction": "UP"}
    - {"type": "pause"}
    - {"type": "resume"}

    服务器推送的 JSON 消息格式:
    - {"type": "state", "data": {...}}   — 每 tick 推送
    - {"type": "game_over", "data": {...}} — 游戏结束
    - {"type": "error", "message": "..."}  — 错误信息
    """
    session = _games.get(game_id)
    if not session:
        await ws.accept()
        await ws.send_json({"type": "error", "message": f"游戏 {game_id} 不存在"})
        await ws.close()
        return

    await ws.accept()
    await session.add_connection(ws)
    logger.info("WebSocket 连接: 游戏 %s", game_id)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "无效的 JSON"})
                continue

            msg_type = msg.get("type", "")

            if msg_type == "direction":
                direction_str = msg.get("direction", "")
                try:
                    direction = Direction(direction_str.upper())
                except ValueError:
                    await ws.send_json({
                        "type": "error",
                        "message": f"无效的方向: {direction_str}",
                    })
                    continue
                session.game.change_direction(direction)

            elif msg_type == "pause":
                session.game.pause()

            elif msg_type == "resume":
                session.game.resume()

            else:
                await ws.send_json({
                    "type": "error",
                    "message": f"未知消息类型: {msg_type}",
                })

    except WebSocketDisconnect:
        pass
    finally:
        await session.remove_connection(ws)
        logger.info("WebSocket 断开: 游戏 %s", game_id)


# ── 入口 ──────────────────────────────────────────────────


def main() -> None:
    """启动服务器"""
    import uvicorn
    uvicorn.run(
        "snake_game.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
