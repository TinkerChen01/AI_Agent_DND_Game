#!/usr/bin/env python3
"""
dnd-dm: 关系追踪检查脚本
用法:
  python relationship_check.py --current "亲密,→,6" --signal positive
  python relationship_check.py --current "友善,↑,1" --signal positive
  python relationship_check.py --current "友善,→,0" --signal negative --romantic true

输入当前关系数据和本次互动信号，自动计算是否跨档。
输出更新后的关系状态和操作建议。

参数:
  --current: 当前关系状态，格式 "档位,trend,浪漫计数"
  --signal: 本次互动信号 (positive/negative/neutral)
  --romantic: 本次互动是否为浪漫互动 (true/false)
"""

import json
import argparse
import sys

# 确保 Windows 控制台使用 UTF-8 输出
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 档位定义
LEVELS = {1: "死敌", 2: "不友善", 3: "中立", 4: "友善", 5: "亲密"}
LEVEL_NAMES = {v: k for k, v in LEVELS.items()}
TRENDS = ["↑", "↓", "→"]


def parse_current(current_str: str) -> dict:
    """解析当前关系状态字符串"""
    parts = [p.strip() for p in current_str.split(",")]
    if len(parts) != 3:
        return {"error": f"格式错误: {current_str}，期望格式: '档位,trend,浪漫计数'"}

    level_name = parts[0]
    trend = parts[1]
    romantic_count = int(parts[2])

    if level_name not in LEVEL_NAMES:
        return {"error": f"未知档位: {level_name}，可选: {list(LEVEL_NAMES.keys())}"}

    return {
        "level": LEVEL_NAMES[level_name],
        "level_name": level_name,
        "trend": trend,
        "romantic_count": romantic_count,
        "up_count": 1 if trend == "↑" else 0,
        "down_count": 1 if trend == "↓" else 0,
    }


def check_relationship(current: dict, signal: str, is_romantic: bool) -> dict:
    """计算关系变化"""
    result = {
        "before": current.copy(),
        "signal": signal,
        "is_romantic": is_romantic,
        "changed": False,
        "cross_level": False,
        "romantic_label_change": None,
        "actions": [],
    }

    if signal == "neutral":
        result["actions"].append("无关系信号，不处理")
        result["after"] = current.copy()
        return result

    # 计算 trend 累计
    up_count = current.get("up_count", 0)
    down_count = current.get("down_count", 0)

    if signal == "positive":
        # 如果有向下的 trend，先抵消
        if down_count > 0:
            down_count -= 1
            result["actions"].append("正面信号抵消一个 ↓")
        else:
            up_count += 1
            result["actions"].append("正面信号 → ↑ +1")
    elif signal == "negative":
        if up_count > 0:
            up_count -= 1
            result["actions"].append("负面信号抵消一个 ↑")
        else:
            down_count += 1
            result["actions"].append("负面信号 → ↓ +1")

    # 确定新 trend
    if up_count > 0:
        new_trend = "↑"
    elif down_count > 0:
        new_trend = "↓"
    else:
        new_trend = "→"

    # 检查跨档
    level = current["level"]
    if up_count >= 2:
        if level < 5:
            level += 1
            up_count = 0
            down_count = 0
            new_trend = "→"
            result["cross_level"] = True
            result["actions"].append(f"2个 ↑ → 向上跨档至 {LEVELS[level]}")
            result["actions"].append("trend 重置为 →")
        else:
            result["actions"].append("已达最高档（亲密），无法再升")
            up_count = 0
            new_trend = "→"

    elif down_count >= 2:
        if level > 1:
            level -= 1
            up_count = 0
            down_count = 0
            new_trend = "→"
            result["cross_level"] = True
            result["actions"].append(f"2个 ↓ → 向下跨档至 {LEVELS[level]}")
            result["actions"].append("trend 重置为 →")
        else:
            result["actions"].append("已达最低档（死敌），无法再降")
            down_count = 0
            new_trend = "→"

    # 浪漫互动处理
    romantic_count = current.get("romantic_count", 0)
    if is_romantic:
        romantic_count += 1
        result["actions"].append(f"浪漫互动 +1（总计 {romantic_count}）")
        if romantic_count == 3 and level >= 4:
            result["romantic_label_change"] = "暧昧"
            result["actions"].append("浪漫计数达 3 + 档位 ≥ 友善 → 获得暧昧标签")
        elif romantic_count == 6 and result.get("romantic_label_change") == "暧昧":
            result["romantic_label_change"] = "恋人"
            result["actions"].append("浪漫计数达 6 → 暧昧升级为恋人")

    result["changed"] = result["cross_level"] or signal != "neutral" or is_romantic

    result["after"] = {
        "level": level,
        "level_name": LEVELS[level],
        "trend": new_trend,
        "up_count": up_count,
        "down_count": down_count,
        "romantic_count": romantic_count,
    }

    # L4/L6 操作提示
    if result["cross_level"]:
        result["actions"].append("⚠ 必须：更新 L4 关系表 + 追加 L6 节点（type: 角色发展）")
    if result["romantic_label_change"]:
        result["actions"].append(f"⚠ 必须：追加 L6 节点记录浪漫标签变化 → {result['romantic_label_change']}")

    return result


def main():
    parser = argparse.ArgumentParser(description="D&D 关系追踪检查")
    parser.add_argument("--current", required=True, help="当前状态: '档位,trend,浪漫计数'")
    parser.add_argument("--signal", required=True, choices=["positive", "negative", "neutral"],
                        help="本次互动信号")
    parser.add_argument("--romantic", default="false", help="是否浪漫互动 (true/false)")
    args = parser.parse_args()

    current = parse_current(args.current)
    if "error" in current:
        print(f"❌ {current['error']}")
        return

    is_romantic = args.romantic.lower() == "true"
    result = check_relationship(current, args.signal, is_romantic)

    # 格式化输出
    before = result["before"]
    after = result["after"]

    print(f"{'='*40}")
    print(f"  关系变化检查")
    print(f"{'='*40}\n")

    print(f"信号: {args.signal}" + (" (浪漫互动)" if is_romantic else ""))
    print()

    print(f"变化前: {before['level_name']}({before['trend']}) 浪漫计数={before['romantic_count']}")
    print(f"变化后: {after['level_name']}({after['trend']}) 浪漫计数={after['romantic_count']}")

    if result["romantic_label_change"]:
        print(f"浪漫标签: → {result['romantic_label_change']}")
    print()

    print("操作记录:")
    for action in result["actions"]:
        print(f"  • {action}")

    if result["cross_level"]:
        print(f"\n⚡ 跨档! {before['level_name']} → {after['level_name']}")

    print(f"\n{'='*40}")

    # JSON
    print("\n---JSON---")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
