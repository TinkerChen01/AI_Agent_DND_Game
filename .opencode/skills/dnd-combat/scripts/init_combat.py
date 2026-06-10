#!/usr/bin/env python3
"""
dnd-combat: 战斗初始化脚本
用法: python init_combat.py [--enemies "敌人1:HP:AC:先攻加值,敌人2:..."]
      python init_combat.py --from-l2

功能:
1. 从 L4 读取兰斯和卡芙卡的当前 HP/AC/先攻加值
2. 从 L2 读取当前遭遇的敌人数据（或使用手动指定）
3. 为所有参战者投先攻
4. 生成完整的 L4b 战斗日志内容

输出: 可直接覆盖写入 L4b 的 markdown 内容
"""

import re
import random
import json
import argparse
import sys
from pathlib import Path

# 确保 Windows 控制台使用 UTF-8 输出
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def find_project_root():
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "L1_世界设定.md").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parents[4]


def read_file_safe(filepath: Path) -> str:
    try:
        return filepath.read_text(encoding="utf-8")
    except Exception:
        return ""


def extract_combat_stats(content: str, char_name: str) -> dict:
    """从 L4 提取角色的战斗数据"""
    # 定位角色区块
    pattern = rf'## (?:一|二)、{char_name}.*?(?=## (?:一|二|三)、|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return {}

    section = match.group(0)
    stats = {"name": char_name}

    # HP
    hp = re.search(r'HP 当前/最大.*?\|\s*\*\*(\d+)\s*/\s*(\d+)\*\*', section)
    if hp:
        stats["hp_current"] = int(hp.group(1))
        stats["hp_max"] = int(hp.group(2))

    # AC
    ac = re.search(r'\*\*AC\*\*.*?\|\s*\*\*(\d+)\*\*', section)
    if ac:
        stats["ac"] = int(ac.group(1))

    # 先攻加值
    init = re.search(r'先攻.*?\|\s*\+(\d+)', section)
    if init:
        stats["initiative_mod"] = int(init.group(1))

    # 速度
    speed = re.search(r'速度.*?\|\s*(\d+)', section)
    if speed:
        stats["speed"] = f"{speed.group(1)} ft"

    return stats


def extract_l5_context(content: str) -> dict:
    """从 L5 提取当前战斗相关上下文"""
    ctx = {}
    loc = re.search(r'\*\*具体位置\*\*\s*\|\s*(.+?)\s*\|', content)
    if loc:
        ctx["location"] = loc.group(1).strip()

    date = re.search(r'\*\*游戏内日期\*\*\s*\|\s*(.+?)\s*\|', content)
    if date:
        ctx["date"] = date.group(1).strip()

    time = re.search(r'\*\*当前时间\*\*\s*\|\s*(.+?)\s*\|', content)
    if time:
        ctx["time"] = time.group(1).strip()

    return ctx


def roll_initiative(combatants: list) -> list:
    """为所有参战者投先攻并排序"""
    for c in combatants:
        mod = c.get("initiative_mod", 0)
        roll = random.randint(1, 20)
        c["initiative_roll"] = roll
        c["initiative_total"] = roll + mod

    # 按先攻从高到低排序
    combatants.sort(key=lambda x: x["initiative_total"], reverse=True)
    return combatants


def generate_l4b(combatants: list, context: dict, battle_name: str = "") -> str:
    """生成 L4b 战斗日志 markdown"""

    player_names = {"兰斯", "卡芙卡"}
    players = [c for c in combatants if c["name"] in player_names]
    enemies = [c for c in combatants if c["name"] not in player_names]

    # 先攻顺序
    init_rows = ""
    for i, c in enumerate(combatants, 1):
        side = "玩家方" if c["name"] in player_names else "敌方"
        roll_detail = f"1d20({c['initiative_roll']})+{c.get('initiative_mod', 0)}"
        init_rows += f"| {i} | {c['name']} | {c['initiative_total']}（{roll_detail}） | {side} |\n"

    # 玩家方速查
    player_rows = ""
    for p in players:
        player_rows += f"| {p['name']} | {p.get('hp_current', '?')}/{p.get('hp_max', '?')} | {p.get('ac', '?')} | 正常 |\n"

    # 敌方速查
    enemy_rows = ""
    for e in enemies:
        enemy_rows += f"| {e['name']} | {e.get('hp_current', '?')}/{e.get('hp_max', '?')} | {e.get('ac', '?')} | 正常 |\n"

    location = context.get("location", "（待填写）")
    game_time = f"{context.get('date', '（待填写）')} {context.get('time', '')}"

    l4b = f"""# L4b — 战斗日志

> 战斗中临时文件。战斗结束后归档清空。

---

## 战斗概况

| 项目 | 内容 |
|------|------|
| 战斗名称 | {battle_name or '（待填写）'} |
| 游戏内时间 | {game_time} |
| 地点 | {location} |
| 回合数 | 1 |
| 当前行动者 | {combatants[0]['name'] if combatants else '（待确定）'} |

## 先攻顺序

| 顺序 | 角色 | 先攻值 | 备注 |
|------|------|--------|------|
{init_rows}
## 参战者状态速查

### 玩家方

| 角色 | HP当前/最大 | AC | 状态 |
|------|-----------|-----|------|
{player_rows}
### 敌方

| 角色 | HP当前/最大 | AC | 状态 |
|------|-----------|-----|------|
{enemy_rows}
## 资源消耗（本战累计）

| 角色 | 资源 | 初始 | 已消耗 | 剩余 |
|------|------|------|--------|------|
| | | | | |

## 关键转折点

> 战斗中状态用上下文维护。仅在倒地、boss入场、环境剧变时追加记录。

| 回合 | 事件 |
|------|------|
| | |
"""
    return l4b


def main():
    parser = argparse.ArgumentParser(description="D&D 战斗初始化")
    parser.add_argument("--enemies", help="敌人数据，格式: '名称:HP:AC:先攻加值,名称:HP:AC:先攻加值'", default=None)
    parser.add_argument("--battle-name", help="战斗名称", default="")
    parser.add_argument("--json", action="store_true", help="同时输出 JSON")
    args = parser.parse_args()

    root = find_project_root()

    # 读取 L4 和 L5
    l4_content = read_file_safe(root / "L4_角色状态.md")
    l5_content = read_file_safe(root / "L5_世界状态.md")

    # 提取玩家方数据
    lance = extract_combat_stats(l4_content, "兰斯")
    kafka = extract_combat_stats(l4_content, "卡芙卡")

    combatants = []
    if lance:
        combatants.append(lance)
    if kafka:
        combatants.append(kafka)

    # 解析敌人数据
    if args.enemies:
        for enemy_str in args.enemies.split(","):
            parts = enemy_str.strip().split(":")
            if len(parts) >= 4:
                combatants.append({
                    "name": parts[0].strip(),
                    "hp_current": int(parts[1]),
                    "hp_max": int(parts[1]),
                    "ac": int(parts[2]),
                    "initiative_mod": int(parts[3]),
                })
            elif len(parts) >= 1 and parts[0].strip():
                # 只提供名字，其他待填写
                combatants.append({
                    "name": parts[0].strip(),
                    "hp_current": 0,
                    "hp_max": 0,
                    "ac": 0,
                    "initiative_mod": 0,
                })

    # 提取上下文
    context = extract_l5_context(l5_content)

    # 投先攻
    combatants = roll_initiative(combatants)

    # 生成 L4b
    l4b_content = generate_l4b(combatants, context, args.battle_name)

    print(l4b_content)

    if args.json:
        json_output = {
            "battle_name": args.battle_name,
            "context": context,
            "combatants": combatants,
            "initiative_order": [
                {"order": i + 1, "name": c["name"], "total": c["initiative_total"],
                 "roll": c["initiative_roll"]}
                for i, c in enumerate(combatants)
            ]
        }
        print("\n---JSON---")
        print(json.dumps(json_output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
