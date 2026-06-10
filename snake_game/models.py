"""
Pydantic 数据模型，用于 API 请求/响应。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateGameRequest(BaseModel):
    width: int = Field(default=20, ge=5, le=100, description="棋盘宽度")
    height: int = Field(default=20, ge=5, le=100, description="棋盘高度")
    initial_speed: float = Field(default=1.0, ge=0.5, le=20.0, description="初始速度（步/秒）")
    wrap_walls: bool = Field(default=False, description="是否允许穿墙")
    food_count: int = Field(default=1, ge=1, le=10, description="同时存在的食物数量")


class DirectionChange(BaseModel):
    direction: str = Field(..., pattern="^(UP|DOWN|LEFT|RIGHT)$")


class Position(BaseModel):
    x: int
    y: int


class GameStateResponse(BaseModel):
    game_id: str
    status: str
    width: int
    height: int
    snake: list[Position]
    food: list[Position]
    direction: str
    score: int
    speed: float
    tick_interval: float
    created_at: float
    updated_at: float

    @classmethod
    def from_game_state(cls, state) -> GameStateResponse:
        return cls(
            game_id=state.game_id,
            status=state.status.value,
            width=state.width,
            height=state.height,
            snake=[Position(x=x, y=y) for x, y in state.snake],
            food=[Position(x=x, y=y) for x, y in state.food],
            direction=state.direction.value,
            score=state.score,
            speed=state.speed,
            tick_interval=state.tick_interval,
            created_at=state.created_at,
            updated_at=state.updated_at,
        )


class ErrorResponse(BaseModel):
    detail: str
