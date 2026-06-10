"""
贪吃蛇核心逻辑单元测试。
"""

import time

from snake_game.game import Direction, GameConfig, GameStatus, SnakeGame


def make_game(**kwargs) -> SnakeGame:
    config = GameConfig(**kwargs)
    return SnakeGame(config=config, seed=42)


def test_initial_state():
    game = make_game()
    assert game.status == GameStatus.WAITING
    assert game.direction == Direction.RIGHT
    assert len(game.snake) == 3
    assert len(game.food) == 1
    assert game.score == 0


def test_start_game():
    game = make_game()
    game.start()
    assert game.status == GameStatus.PLAYING


def test_move_snake():
    game = make_game()
    game.start()
    head_before = game.snake[0]
    game.tick()
    # 默认为 RIGHT，所以 x 增加 1
    assert game.snake[0] == (head_before[0] + 1, head_before[1])


def test_change_direction():
    game = make_game()
    game.start()
    assert game.change_direction(Direction.UP)
    game.tick()
    head_before = game.snake[0]
    game.tick()  # 第二个 tick 才生效第一个方向变化后的移动
    assert game.snake[0] == (head_before[0], head_before[1] - 1)


def test_cannot_reverse_direction():
    game = make_game()
    game.start()
    assert not game.change_direction(Direction.LEFT)  # 当前 RIGHT，不能反
    assert game.change_direction(Direction.UP)


def test_wall_collision_death():
    """默认不穿墙，撞墙即死"""
    game = make_game(width=5, height=5)
    # 蛇从中间向右，直接走到墙边
    game.snake = [(4, 2), (3, 2), (2, 2)]
    game.start()
    game.tick()  # 撞到 x=5 的墙
    assert game.status == GameStatus.GAME_OVER


def test_wrap_walls():
    """穿墙模式从右边出去回到左边"""
    game = make_game(width=5, height=5, wrap_walls=True)
    game.snake = [(4, 2), (3, 2), (2, 2)]
    game.start()
    game.tick()
    assert game.snake[0] == (0, 2)  # 穿到左边
    assert game.status == GameStatus.PLAYING


def test_self_collision_death():
    game = make_game()
    #  蛇: (0,0)→(1,0)→(2,0)→(2,1)→(1,1)→(0,1)→(0,2)→(1,2)→(2,2)
    #        H   B0   B1   B2   B3   B4   B5   B6   T
    #  头朝右 (RIGHT)，向下走会撞到 (0,1) 中间的身体
    game.snake = [(0, 0), (1, 0), (2, 0), (2, 1), (1, 1), (0, 1), (0, 2), (1, 2), (2, 2)]
    game.start()
    game.change_direction(Direction.DOWN)
    game.tick()
    assert game.status == GameStatus.GAME_OVER


def test_eat_food():
    game = make_game()
    game.start()
    # 把食物放在蛇头正前方
    head = game.snake[0]
    game.food = [(head[0] + 1, head[1])]
    game.tick()
    assert game.score == 1
    assert len(game.snake) == 4  # 增长了


def test_multiple_food():
    game = make_game(food_count=3)
    assert len(game.food) == 3


def test_pause_resume():
    game = make_game()
    game.start()
    game.pause()
    assert game.status == GameStatus.PAUSED
    head_before = game.snake[0]
    game.tick()  # 暂停时不移动
    assert game.snake[0] == head_before
    game.resume()
    assert game.status == GameStatus.PLAYING


def test_speed_increases():
    game = make_game(initial_speed=1.0, speed_increment=0.5)
    game.start()
    head = game.snake[0]
    game.food = [(head[0] + 1, head[1])]
    game.tick()
    assert game.speed == 1.5


def test_game_over_after_eat():
    """吃完食物后撞墙依然会死"""
    game = make_game(width=5, height=5)
    game.snake = [(4, 2), (3, 2), (2, 2)]
    game.food = [(3, 3)]  # 不可达，不影响
    game.start()
    game.tick()
    assert game.status == GameStatus.GAME_OVER


def test_game_state_snapshot():
    game = make_game()
    game.start()
    ts = time.time()
    state = game.get_state(timestamp=ts)
    assert state.score == 0
    assert state.width == 20
    assert state.height == 20
    assert state.status == GameStatus.PLAYING
    assert state.tick_interval == 1000.0
    assert state.updated_at == ts


def test_direction_queue():
    """每个 tick 只能改变一次方向"""
    game = make_game()
    game.start()
    assert game.change_direction(Direction.UP)
    assert not game.change_direction(Direction.LEFT)  # 队列已满
    game.tick()  # 消费队列
    assert game.change_direction(Direction.LEFT)  # 可以再改了
