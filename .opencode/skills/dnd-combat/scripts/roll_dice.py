#!/usr/bin/env python3
"""
dnd-combat: 通用骰子引擎
用法:
  python roll_dice.py 2d6+5          → 掷 2d6+5
  python roll_dice.py 1d20+7         → 攻击骰
  python roll_dice.py init:1d20+2    → 先攻骰（标记用途）
  python roll_dice.py advantage:1d20+7 → 优势骰（投两次取高）
  python roll_dice.py disadvantage:1d20+7 → 劣势骰（投两次取低）
  python roll_dice.py 4d6kh3         → 4d6 保留最高 3 个（属性生成）

输出 JSON 格式，包含每次掷骰的详细结果和计算过程。
"""

import sys
import re
import random
import json
import argparse

# 确保 Windows 控制台使用 UTF-8 输出
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def parse_and_roll(expr: str) -> dict:
    """解析骰子表达式并执行"""
    result = {"expression": expr, "rolls": [], "modifier": 0, "total": 0, "breakdown": ""}

    # 检查前缀模式
    mode = "normal"
    if expr.startswith("init:"):
        mode = "initiative"
        expr = expr[5:]
    elif expr.startswith("advantage:"):
        mode = "advantage"
        expr = expr[10:]
    elif expr.startswith("disadvantage:"):
        mode = "disadvantage"
        expr = expr[13:]

    # 解析 NdS+M 或 NdSkhK 格式
    m = re.match(r'^(\d*)d(\d+)(?:kh(\d+))?([+-]\d+)?$', expr)
    if not m:
        result["error"] = f"无法解析表达式: {expr}"
        return result

    count = int(m.group(1) or 1)
    sides = int(m.group(2))
    keep_high = int(m.group(3)) if m.group(3) else None
    modifier = int(m.group(4) or 0)

    # D&D 暴击/大失败判定（仅针对 d20 单骰/优势/劣势）
    def _check_critical_fumble(val: int, s: int):
        if s == 20:
            if val == 20:
                result["critical"] = True
            elif val == 1:
                result["fumble"] = True

    if mode in ("advantage", "disadvantage"):
        # 优势/劣势：投两次 1d20
        roll1 = random.randint(1, sides)
        roll2 = random.randint(1, sides)
        if mode == "advantage":
            chosen = max(roll1, roll2)
        else:
            chosen = min(roll1, roll2)
        result["rolls"] = [roll1, roll2]
        result["chosen"] = chosen
        result["modifier"] = modifier
        result["total"] = chosen + modifier
        result["mode"] = mode
        _check_critical_fumble(chosen, sides)
        crit_mark = "💥" if result.get("critical") else "💀" if result.get("fumble") else ""
        result["breakdown"] = (
            f"[{roll1}] vs [{roll2}] → 取{'高' if mode == 'advantage' else '低'}"
            f" = {chosen} + {modifier} = {result['total']} {crit_mark}"
        )
    else:
        # 普通掷骰
        rolls = [random.randint(1, sides) for _ in range(count)]
        if keep_high and keep_high < count:
            rolls_sorted = sorted(rolls, reverse=True)
            kept = rolls_sorted[:keep_high]
            dropped = rolls_sorted[keep_high:]
            total = sum(kept) + modifier
            result["rolls"] = rolls
            result["kept"] = kept
            result["dropped"] = dropped
            result["total"] = total
            result["breakdown"] = (
                f"[{', '.join(str(r) for r in rolls)}] "
                f"保留最高{keep_high}个: [{', '.join(str(r) for r in kept)}] "
                f"+ {modifier} = {total}"
            )
        else:
            total = sum(rolls) + modifier
            result["rolls"] = rolls
            result["total"] = total
            # 仅单骰 d20 判定暴击/大失败
            if count == 1:
                _check_critical_fumble(rolls[0], sides)
            crit_mark = "💥" if result.get("critical") else "💀" if result.get("fumble") else ""
            result["breakdown"] = (
                f"[{' + '.join(str(r) for r in rolls)}] + {modifier} = {total} {crit_mark}"
            )

    result["modifier"] = modifier

    if mode == "initiative":
        result["mode"] = "initiative"

    return result


def format_for_display(result: dict) -> str:
    """格式化为可读的 D&D 风格输出"""
    if "error" in result:
        return f"❌ {result['error']}"

    mode = result.get("mode", "normal")
    prefix = ""
    if mode == "initiative":
        prefix = "🎯 先攻: "
    elif mode == "advantage":
        prefix = "⬆ 优势: "
    elif mode == "disadvantage":
        prefix = "⬇ 劣势: "

    # 暴击/大失败高亮
    if result.get("critical"):
        prefix = "💥 暴击! " + prefix
    elif result.get("fumble"):
        prefix = "💀 大失败! " + prefix

    return f"{prefix}{result['expression']} → {result['breakdown']}"


def main():
    parser = argparse.ArgumentParser(description="D&D 骰子引擎")
    parser.add_argument("expressions", nargs="+", help="骰子表达式（如 2d6+5, init:1d20+2）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    results = []
    for expr in args.expressions:
        result = parse_and_roll(expr)
        results.append(result)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(format_for_display(result))
        # 同时输出 JSON 供程序解析
        print("\n---JSON---")
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
