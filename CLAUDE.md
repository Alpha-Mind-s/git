# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build / Run / Test

```bash
# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
uvicorn snake_game.server:app --reload --host 0.0.0.0 --port 8000

# 运行全部测试
pytest -v

# 运行单个测试文件
pytest tests/test_game.py -v

# 运行单个测试用例
pytest tests/test_game.py::test_eat_food -v
```

API 文档地址: http://localhost:8000/docs

## 项目架构

```
snake_game/
├── game.py       # 核心游戏引擎（纯逻辑，无 I/O）
├── models.py     # Pydantic 请求/响应模型
├── server.py     # FastAPI 应用 + WebSocket 端点
tests/
└── test_game.py  # pytest 单元测试
```

### 关键设计

- **game.py** — 游戏引擎完全无外部依赖（只有 Python stdlib），`SnakeGame` 类管理单局游戏的所有状态。`GameConfig` 控制棋盘大小、速度、穿墙等参数。`GameState` 是不可变的输出快照。
- **server.py** — `GameSession` 包装 `SnakeGame`，管理 WebSocket 连接池和 asyncio tick 循环。`_games` 是全局的 `dict[str, GameSession]`，支持多局游戏并发。`_cleanup_stale_games()` 每 60s 清理结束超过 5 分钟的游戏。
- **方向队列** — 每个 tick 只接受一次方向变化，防止一帧内多次转向绕过自碰检测。
- **WebSocket 协议** — 客户端发送 `{"type":"direction","direction":"UP"}`，服务器每 tick 推送 `{"type":"state","data":{...}}`。
