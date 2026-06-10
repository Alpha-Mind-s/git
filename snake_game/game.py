"""
贪吃蛇核心游戏引擎。

纯逻辑层，不涉及任何 I/O，可独立测试。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Direction(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    @property
    def opposite(self) -> Direction:
        return _OPPOSITES[self]

    @property
    def vector(self) -> tuple[int, int]:
        return _VECTORS[self]


_VECTORS = {
    Direction.UP: (0, -1),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}

_OPPOSITES = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}


class GameStatus(str, Enum):
    WAITING = "WAITING"   # 等待开始
    PLAYING = "PLAYING"   # 进行中
    PAUSED = "PAUSED"     # 暂停
    GAME_OVER = "GAME_OVER"  # 结束


@dataclass
class GameConfig:
    """游戏配置"""
    width: int = 20
    height: int = 20
    initial_speed: float = 1.0        # 每秒移动步数
    speed_increment: float = 0.1       # 每吃一个食物增加的速度
    max_speed: float = 10.0
    wrap_walls: bool = False           # True = 穿墙, False = 撞墙死
    initial_length: int = 3
    food_count: int = 1                # 同时存在的食物数量


@dataclass
class GameState:
    """不可变游戏快照，用于序列化输出"""
    game_id: str
    status: GameStatus
    width: int
    height: int
    snake: list[tuple[int, int]]       # 头在 index 0
    food: list[tuple[int, int]]
    direction: Direction
    score: int
    speed: float
    tick_interval: float               # 毫秒
    created_at: float
    updated_at: float


class SnakeGame:
    """单局贪吃蛇游戏核心逻辑"""

    def __init__(
        self,
        config: Optional[GameConfig] = None,
        game_id: str = "",
        seed: Optional[int] = None,
    ) -> None:
        self.config = config or GameConfig()
        self.game_id = game_id
        self._rng = random.Random(seed)

        self.status = GameStatus.WAITING
        self.direction: Direction = Direction.RIGHT
        self._next_direction: Direction = Direction.RIGHT
        self._direction_queued: bool = False

        # 蛇：头在 index 0
        mid_x = self.config.width // 2
        mid_y = self.config.height // 2
        self.snake: list[tuple[int, int]] = [
            (mid_x - i, mid_y) for i in range(self.config.initial_length)
        ]

        self.score = 0
        self.speed = self.config.initial_speed
        self.food: list[tuple[int, int]] = []

        self.created_at = 0.0
        self.updated_at = 0.0

        self._spawn_food()

    # ── 公开方法 ──────────────────────────────────────────

    def start(self, timestamp: float = 0.0) -> None:
        """开始游戏"""
        if self.status in (GameStatus.GAME_OVER,):
            return
        self.status = GameStatus.PLAYING
        self.created_at = timestamp or self.created_at
        self.updated_at = timestamp or self.updated_at

    def pause(self) -> None:
        """暂停"""
        if self.status == GameStatus.PLAYING:
            self.status = GameStatus.PAUSED

    def resume(self) -> None:
        """恢复"""
        if self.status == GameStatus.PAUSED:
            self.status = GameStatus.PLAYING

    def change_direction(self, direction: Direction) -> bool:
        """
        改变方向。返回 True 表示生效。
        不能反向，每个 tick 只能改变一次方向。
        """
        if self.status != GameStatus.PLAYING:
            return False
        if direction.opposite == self.direction:
            return False
        if self._direction_queued:
            return False
        self._next_direction = direction
        self._direction_queued = True
        return True

    def tick(self, timestamp: float = 0.0) -> GameStatus:
        """
        执行一个游戏 tick。
        返回当前状态。
        """
        if self.status != GameStatus.PLAYING:
            return self.status

        self._direction_queued = False
        self.direction = self._next_direction

        head = self.snake[0]
        dx, dy = self.direction.vector
        new_head = (head[0] + dx, head[1] + dy)

        # 碰撞检测
        if self.config.wrap_walls:
            new_head = (
                new_head[0] % self.config.width,
                new_head[1] % self.config.height,
            )
        else:
            if not (0 <= new_head[0] < self.config.width and
                    0 <= new_head[1] < self.config.height):
                self.status = GameStatus.GAME_OVER
                self.updated_at = timestamp
                return self.status

        # 自碰检测（排除尾巴，因为尾巴即将移除——除非吃东西）
        eating = new_head in self.food
        body_to_check = self.snake[:-1] if not eating else self.snake
        if new_head in body_to_check:
            self.status = GameStatus.GAME_OVER
            self.updated_at = timestamp
            return self.status

        # 移动蛇
        self.snake.insert(0, new_head)
        if eating:
            self.score += 1
            self.speed = min(
                self.speed + self.config.speed_increment,
                self.config.max_speed,
            )
            self.food.remove(new_head)
            self._spawn_food()
        else:
            self.snake.pop()

        self.updated_at = timestamp
        return self.status

    def get_state(self, game_id: str = "", timestamp: float = 0.0) -> GameState:
        """获取当前游戏快照"""
        return GameState(
            game_id=game_id or self.game_id,
            status=self.status,
            width=self.config.width,
            height=self.config.height,
            snake=list(self.snake),
            food=list(self.food),
            direction=self.direction,
            score=self.score,
            speed=self.speed,
            tick_interval=1000.0 / self.speed,
            created_at=self.created_at,
            updated_at=timestamp or self.updated_at,
        )

    # ── 内部方法 ──────────────────────────────────────────

    def _spawn_food(self) -> None:
        """在空白格子上生成食物"""
        occupied = set(self.snake) | set(self.food)
        max_attempts = self.config.width * self.config.height * 2
        while len(self.food) < self.config.food_count:
            if len(self.food) + len(occupied) >= self.config.width * self.config.height:
                break  # 棋盘已满
            x = self._rng.randint(0, self.config.width - 1)
            y = self._rng.randint(0, self.config.height - 1)
            if (x, y) not in occupied:
                self.food.append((x, y))
                occupied.add((x, y))
