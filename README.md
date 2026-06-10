# Snake Game Backend

多人在线贪吃蛇游戏后端服务（当前为单机版）。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务器（热重载）
uvicorn snake_game.server:app --reload --host 0.0.0.0 --port 8000

# 运行测试
pytest -v
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/games` | 列出所有活跃游戏 |
| `POST` | `/api/games` | 创建新游戏 |
| `GET` | `/api/games/{id}` | 获取游戏状态 |
| `DELETE` | `/api/games/{id}` | 删除游戏 |
| `POST` | `/api/games/{id}/direction` | 改变方向 |
| `POST` | `/api/games/{id}/pause` | 暂停游戏 |
| `POST` | `/api/games/{id}/resume` | 恢复游戏 |
| `WS` | `/ws/{id}` | WebSocket 实时连接 |

API 文档在启动后访问 http://localhost:8000/docs。

## WebSocket 协议

### 客户端 → 服务器

```json
{"type": "direction", "direction": "UP"}
{"type": "pause"}
{"type": "resume"}
```

### 服务器 → 客户端

```json
{"type": "state", "data": { "score": 5, "snake": [...], ... }}
{"type": "game_over", "data": { ... }}
{"type": "error", "message": "..."}
```

## 项目结构

```
├── snake_game/
│   ├── __init__.py      # 包初始化
│   ├── game.py          # 核心游戏引擎（纯逻辑）
│   ├── models.py        # Pydantic 数据模型
│   └── server.py        # FastAPI + WebSocket 服务
├── tests/
│   └── test_game.py     # 单元测试
├── requirements.txt
└── README.md
```
