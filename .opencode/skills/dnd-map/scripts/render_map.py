#!/usr/bin/env python3
"""
dnd-map: 战术地图渲染引擎
用法:
  python render_map.py --type combat --data '{"title":"战斗","grid":[...],"entities":[...]}'
  python render_map.py --type combat --file combat_map.json
  python render_map.py --type floorplan --data '{"title":"庄园","floors":[...]}'
  python render_map.py --type explore --data '{"title":"区域","areas":[...]}'

从 JSON 数据渲染 ASCII 战术地图。

JSON 数据格式:

Combat（战斗地图）:
{
  "title": "战斗标题",
  "round": 2,
  "grid_width": 12,
  "grid_height": 8,
  "terrain": [
    {"x": 0, "y": 0, "w": 3, "h": 8, "symbol": "#", "label": "墙壁"},
    {"x": 5, "y": 3, "symbol": "*", "label": "壁炉"},
  ],
  "entities": [
    {"symbol": "@", "name": "兰斯", "x": 2, "y": 3, "hp": "45/45", "side": "player"},
    {"symbol": "K", "name": "卡芙卡", "x": 2, "y": 5, "hp": "31/31", "side": "player"},
    {"symbol": "E", "name": "人偶A", "x": 7, "y": 2, "hp": "18/25", "side": "enemy"},
  ],
  "items": [
    {"symbol": "○", "name": "掉落物", "x": 5, "y": 6},
  ],
  "legend": ["*=壁炉(光源)", "○=掉落物"]
}

Floorplan（楼层总览）:
{
  "title": "灰夫人庄园",
  "floors": [
    {"id": "3F", "name": "画室", "status": "current", "rooms": ["画室"]},
    {"id": "2F", "name": "书房", "status": "explored", "rooms": ["主卧", "书房", "铁门"]},
    {"id": "1F", "name": "门厅", "status": "explored", "rooms": ["门厅", "走廊", "厨房"]},
    {"id": "B1", "name": "地下", "status": "locked", "rooms": ["实验室(封印)"]},
  ],
  "connections": [["3F","2F"],["2F","1F"],["1F","B1"]]
}

Explore（区域探索）:
{
  "title": "区域名称",
  "areas": [
    {"name": "地点A", "status": "explored", "notes": "已搜索"},
    {"name": "地点B", "status": "current", "notes": "当前位置"},
    {"name": "地点C", "status": "unknown", "notes": "?"},
  ],
  "paths": [["地点A","地点B"],["地点B","地点C"]]
}
"""

import json
import argparse
import sys
from pathlib import Path

# 确保 Windows 控制台使用 UTF-8 输出
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# 符号常量
WALL = "#"
FLOOR = "."
DOOR_CLOSED = "="
DOOR_OPEN = "▯"
UNKNOWN = "?"

STATUS_SYMBOLS = {
    "current": "← 当前",
    "explored": "✓",
    "locked": "🔒",
    "unknown": "?",
    "unexplored": "—",
}


def render_combat_map(data: dict) -> str:
    """渲染战斗地图"""
    title = data.get("title", "战斗")
    round_num = data.get("round", 1)
    width = data.get("grid_width", 14)
    height = data.get("grid_height", 8)
    entities = data.get("entities", [])
    terrain = data.get("terrain", [])
    items = data.get("items", [])
    legend = data.get("legend", [])

    # 初始化网格
    grid = [[FLOOR for _ in range(width)] for _ in range(height)]

    # 放置地形
    for t in terrain:
        sym = t.get("symbol", "#")
        x, y = t.get("x", 0), t.get("y", 0)
        w = t.get("w", 1)
        h = t.get("h", 1)
        for dy in range(h):
            for dx in range(w):
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width:
                    grid[ny][nx] = sym

    # 放置物品
    for item in items:
        x, y = item.get("x", 0), item.get("y", 0)
        if 0 <= y < height and 0 <= x < width:
            grid[y][x] = item.get("symbol", "○")

    # 放置实体（最后放置，覆盖地形）
    for entity in entities:
        x, y = entity.get("x", 0), entity.get("y", 0)
        if 0 <= y < height and 0 <= x < width:
            grid[y][x] = entity.get("symbol", "?")

    # 渲染
    border = "═" * (width * 2 + 3)
    lines = []
    lines.append(f"╔{border}╗")
    lines.append(f"║  {title} · 回合 {round_num}" + " " * max(0, width * 2 + 3 - len(title) - 7) + "║")
    lines.append(f"╠{border}╣")
    lines.append(f"║" + " " * (width * 2 + 3) + "║")

    for row_idx in range(height):
        row_str = "  "
        for col_idx in range(width):
            cell = grid[row_idx][col_idx]
            row_str += cell + " "
        lines.append(f"║ {row_str}║")

    lines.append(f"║" + " " * (width * 2 + 3) + "║")
    lines.append(f"╠{border}╣")

    # 实体信息
    player_entities = [e for e in entities if e.get("side") == "player"]
    enemy_entities = [e for e in entities if e.get("side") == "enemy"]

    if player_entities:
        info_parts = []
        for p in player_entities:
            info_parts.append(f"{p['symbol']}{p['name']}({p.get('hp', '?')})")
        lines.append(f"║  玩家: {'  '.join(info_parts)}" + " " * 4 + "║")

    if enemy_entities:
        info_parts = []
        for e in enemy_entities:
            info_parts.append(f"{e['symbol']}{e['name']}({e.get('hp', '?')})")
        lines.append(f"║  敌方: {'  '.join(info_parts)}" + " " * 4 + "║")

    # 物品和图例
    if items:
        item_strs = [f"{i.get('symbol', '○')} {i.get('name', '')}" for i in items]
        lines.append(f"║  物品: {'  '.join(item_strs)}" + " " * 4 + "║")

    if legend:
        lines.append(f"║  {'  '.join(legend)}" + " " * 4 + "║")

    # 距离速查（玩家和敌人之间）
    for p in player_entities:
        for e in enemy_entities:
            px, py = p.get("x", 0), p.get("y", 0)
            ex, ey = e.get("x", 0), e.get("y", 0)
            dist = (abs(px - ex) + abs(py - ey)) * 5  # 每格 5ft
            lines.append(f"║  {p['name']}→{e['name']}: {dist}ft" + " " * 8 + "║")

    lines.append(f"╚{border}╝")

    return "\n".join(lines)


def render_floorplan(data: dict) -> str:
    """渲染楼层总览地图"""
    title = data.get("title", "建筑")
    floors = data.get("floors", [])
    connections = data.get("connections", [])

    border = "═" * 50
    lines = []
    lines.append(f"╔{border}╗")
    lines.append(f"║  {title} · 楼层总览" + " " * (50 - len(title) - 8) + "║")
    lines.append(f"╠{border}╣")
    lines.append(f"║" + " " * 50 + "║")

    for i, floor in enumerate(floors):
        fid = floor.get("id", "?")
        name = floor.get("name", "")
        status = floor.get("status", "unknown")
        rooms = floor.get("rooms", [])
        status_sym = STATUS_SYMBOLS.get(status, "")

        # 楼层头
        status_marker = ""
        if status == "current":
            status_marker = " ★ 当前"
        elif status == "explored":
            status_marker = " ✓ 已探索"
        elif status == "locked":
            status_marker = " 🔒 封锁"

        lines.append(f"║  [{fid}] {name}{status_marker}" + " " * 8 + "║")

        # 房间列表
        if rooms:
            room_str = " · ".join(rooms)
            lines.append(f"║        {room_str}" + " " * 8 + "║")

        # 连接指示
        if i < len(floors) - 1:
            conn_found = False
            for conn in connections:
                if floor.get("id") in conn and floors[i + 1].get("id") in conn:
                    conn_found = True
                    break
            if conn_found:
                lines.append(f"║          │" + " " * 30 + "║")
                lines.append(f"║          ▼ 楼梯" + " " * 30 + "║")

        lines.append(f"║" + " " * 50 + "║")

    # 图例
    lines.append(f"╠{border}╣")
    lines.append(f"║  图例: ★当前  ✓已探索  🔒封锁  ?未知" + " " * 10 + "║")
    lines.append(f"╚{border}╝")

    return "\n".join(lines)


def render_explore_map(data: dict) -> str:
    """渲染区域探索地图"""
    title = data.get("title", "区域")
    areas = data.get("areas", [])
    paths = data.get("paths", [])

    border = "═" * 50
    lines = []
    lines.append(f"╔{border}╗")
    lines.append(f"║  {title} · 区域地图" + " " * (50 - len(title) - 8) + "║")
    lines.append(f"╠{border}╣")
    lines.append(f"║" + " " * 50 + "║")

    for area in areas:
        name = area.get("name", "")
        status = area.get("status", "unknown")
        notes = area.get("notes", "")

        symbol = {"explored": "[✓]", "current": "[★]", "unknown": "[?]", "locked": "[🔒]"}.get(status, "[ ]")
        note_str = f" — {notes}" if notes else ""

        lines.append(f"║  {symbol} {name}{note_str}" + " " * 8 + "║")

    # 路径
    if paths:
        lines.append(f"║" + " " * 50 + "║")
        lines.append(f"║  路径:" + " " * 38 + "║")
        for path in paths:
            if len(path) == 2:
                lines.append(f"║    {path[0]} ←→ {path[1]}" + " " * 16 + "║")

    lines.append(f"║" + " " * 50 + "║")
    lines.append(f"╚{border}╝")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="D&D 战术地图渲染引擎")
    parser.add_argument("--type", choices=["combat", "floorplan", "explore"], required=True,
                        help="地图类型")
    parser.add_argument("--data", default=None, help="JSON 格式的地图数据")
    parser.add_argument("--file", default=None, help="JSON 文件路径")
    args = parser.parse_args()

    # 获取数据
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif args.data:
        data = json.loads(args.data)
    else:
        # 从 stdin 读取
        data = json.load(sys.stdin)

    # 渲染
    if args.type == "combat":
        result = render_combat_map(data)
    elif args.type == "floorplan":
        result = render_floorplan(data)
    elif args.type == "explore":
        result = render_explore_map(data)
    else:
        result = "不支持的地图类型"

    print(result)


if __name__ == "__main__":
    main()
