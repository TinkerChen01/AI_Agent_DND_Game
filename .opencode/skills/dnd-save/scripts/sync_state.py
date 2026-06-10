#!/usr/bin/env python3
"""
dnd-save: 状态同步与一致性检查脚本
用法: python sync_state.py --mode checkpoint
      python sync_state.py --mode save

功能:
1. 读取 L4/L5/L6 当前状态，输出结构化快照
2. 检查 L6 节点连续性（node_id 是否连续）
3. 检查 L5 时间线与 L6 节点的一致性
4. 标记可能需要更新/补充的字段
5. (save 模式) 生成前情提要的骨架模板
"""

import re
import json
import sys
from datetime import datetime
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
    except Exception as e:
        return f"[读取失败: {e}]"


def check_l4_consistency(content: str) -> dict:
    """检查 L4 角色状态一致性"""
    issues = []
    chars = {}

    # 检查两个角色区块
    for name in ["兰斯", "卡芙卡"]:
        pattern = rf'## (?:一|二)、{name}.*?(?=## (?:一|二|三)、|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            issues.append(f"未找到 {name} 的数据区块")
            continue

        section = match.group(0)
        char_data = {"name": name}

        # HP 检查
        hp = re.search(r'HP 当前/最大.*?\|\s*\*\*(\d+)\s*/\s*(\d+)\*\*', section)
        if hp:
            current = int(hp.group(1))
            maximum = int(hp.group(2))
            char_data["hp"] = f"{current}/{maximum}"
            if current > maximum:
                issues.append(f"{name}: 当前 HP({current}) 超过最大值({maximum})")
            if current <= 0:
                issues.append(f"{name}: 当前 HP 为 0 或负数（已倒地？）")
            if current < maximum // 2:
                issues.append(f"{name}: HP 低于一半（{current}/{maximum}），注意叙事体现伤势")

        # 金币（兼容 "424 gp" 和 "769 gp 3 sp" 格式）
        gold = re.search(r'金币.*?\|\s*\*\*(\d+)', section)
        if gold:
            char_data["gold"] = int(gold.group(1))
            if char_data["gold"] < 0:
                issues.append(f"{name}: 金币为负数")

        chars[name] = char_data

    return {"characters": chars, "issues": issues}


def check_l5_consistency(content: str) -> dict:
    """检查 L5 世界状态"""
    issues = []
    state = {}

    # 基本信息
    date = re.search(r'\*\*游戏内日期\*\*\s*\|\s*(.+?)\s*\|', content)
    if date:
        state["date"] = date.group(1).strip()

    location = re.search(r'\*\*具体位置\*\*\s*\|\s*(.+?)\s*\|', content)
    if location:
        state["location"] = location.group(1).strip()

    progress = re.search(r'\*\*模组进度\*\*\s*\|\s*(.+?)\s*\|', content)
    if progress:
        state["progress"] = progress.group(1).strip()

    # 检查待处理事件
    pending_count = len(re.findall(r'\|\s*(高|中)\s*\|', content))
    state["pending_events_count"] = pending_count

    # 检查 plot flags 是否有重复定义
    flags = re.findall(r'^\|\s*(\S+)\s*\|\s*(true|false|null)\s*\|', content, re.MULTILINE)
    flag_names = [f[0] for f in flags]
    duplicates = {name for name in flag_names if flag_names.count(name) > 1}
    if duplicates:
        issues.append(f"L5 中发现重复的 plot flag: {', '.join(duplicates)}")

    return {"state": state, "issues": issues}


def check_l4_detailed(content: str) -> dict:
    """L4 详细检查：AC、等级、XP、Buff 异常"""
    issues = []
    chars = {}

    # XP 到等级的标准映射（D&D 5e）
    xp_table = {
        1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500,
        6: 14000, 7: 23000, 8: 34000, 9: 48000, 10: 64000,
    }

    for name in ["兰斯", "卡芙卡"]:
        pattern = rf'## (?:一|二)、{name}.*?(?=## (?:一|二|三)、|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            issues.append(f"未找到 {name} 的数据区块")
            continue

        section = match.group(0)
        char_data = {"name": name}

        # HP
        hp = re.search(r'HP 当前/最大.*?\|\s*\*\*(\d+)\s*/\s*(\d+)\*\*', section)
        if hp:
            current = int(hp.group(1))
            maximum = int(hp.group(2))
            char_data["hp"] = f"{current}/{maximum}"
            if current > maximum:
                issues.append(f"{name}: 当前 HP({current}) 超过最大值({maximum})")
            if current <= 0:
                issues.append(f"{name}: 当前 HP 为 0 或负数（已倒地？）")
            if current < maximum // 2:
                issues.append(f"{name}: HP 低于一半（{current}/{maximum}），注意叙事体现伤势")

        # AC 合理性（D&D 5e 中裸 AC 通常在 10-25 之间）
        ac = re.search(r'AC.*?\|\s*\*\*(\d+)\*\*', section)
        if ac:
            ac_val = int(ac.group(1))
            char_data["ac"] = ac_val
            if ac_val < 10:
                issues.append(f"{name}: AC 异常低（{ac_val}），请确认是否漏算")
            if ac_val > 25:
                issues.append(f"{name}: AC 异常高（{ac_val}），请确认是否计算错误")

        # 金币（兼容 "424 gp" 和 "769 gp 3 sp" 格式）
        gold = re.search(r'金币.*?\|\s*\*\*(\d+)', section)
        if gold:
            char_data["gold"] = int(gold.group(1))
            if char_data["gold"] < 0:
                issues.append(f"{name}: 金币为负数")

        # 等级与 XP
        level = re.search(r'等级.*?\|\s*\*\*(\d+)\*\*', section)
        xp = re.search(r'当前 XP.*?\|\s*(\d+)', section)
        if level and xp:
            lvl = int(level.group(1))
            xp_val = int(xp.group(1))
            char_data["level"] = lvl
            char_data["xp"] = xp_val
            expected_xp_min = xp_table.get(lvl, 0)
            expected_xp_max = xp_table.get(lvl + 1, 999999) - 1
            if xp_val < expected_xp_min or xp_val > expected_xp_max:
                issues.append(
                    f"{name}: 等级 {lvl} 对应的 XP 应在 {expected_xp_min}-{expected_xp_max} 之间，"
                    f"实际为 {xp_val}"
                )

        # Buff/Debuff 检查
        buff_section = re.search(r'### Buff / Debuff / 状态\n(.*?)(?=###|\Z)', section, re.DOTALL)
        if buff_section:
            buff_text = buff_section.group(1)
            # 如果表格中有实际的状态行（不是只有表头），检查是否有异常剩余回合
            active_buffs = re.findall(r'^\|\s*(\S+)\s*\|\s*(.+?)\s*\|\s*(\S+)\s*\|', buff_text, re.MULTILINE)
            # 过滤掉表头行
            active_buffs = [b for b in active_buffs if b[0] not in ("状态", "—", "")]
            char_data["active_buffs"] = len(active_buffs)

        chars[name] = char_data

    return {"characters": chars, "issues": issues}


def check_l5_l6_alignment(l5_content: str, l6_content: str) -> list:
    """检查 L5 与 L6 之间的一致性"""
    issues = []

    # L5 当前日期
    l5_date = re.search(r'\*\*游戏内日期\*\*\s*\|\s*(.+?)\s*\|', l5_content)
    l5_date_str = l5_date.group(1).strip() if l5_date else ""

    # L6 最后节点日期（优先从 HTML 注释提取）
    header_pattern = re.compile(
        r'<!--\s*node:\s*\S+\s*\|\s*type:\s*.+?\s*\|\s*date:\s*(.+?)\s*\|\s*session:\s*\d+\s*-->'
    )
    header_matches = list(header_pattern.finditer(l6_content))
    if header_matches:
        l6_last_date = header_matches[-1].group(1).strip()
    else:
        # fallback: 从 in_game_date 提取
        dates = re.findall(r'in_game_date:\s*(.+?)\s*\n', l6_content)
        l6_last_date = dates[-1].strip() if dates else ""

    if l5_date_str and l6_last_date:
        # 简单比较：如果 L5 日期和 L6 最后节点日期差异明显，提示检查
        # 注意：这里只是启发式检查，因为日期格式可能不同
        if l5_date_str != l6_last_date and abs(len(l5_date_str) - len(l6_last_date)) < 10:
            # 如果两者有内容但不完全相同，可能是正常的（L5 是当前状态，L6 是上次记录）
            # 但如果 L6 日期明显晚于 L5，就有问题
            pass  # 暂不触发，因为格式差异太大

    # 检查 L5 的 plot flags 和 L6 的 unlock_flags 是否对齐
    l5_flags = set(re.findall(r'^\|\s*(\S+)\s*\|\s*(?:true|false|null)', l5_content, re.MULTILINE))
    l6_flags = set(re.findall(r'\-\s*(\S+):\s*true', l6_content))

    # L6 中解锁的 flag 应该在 L5 中存在
    missing_in_l5 = l6_flags - l5_flags
    if missing_in_l5:
        issues.append(f"L6 节点中解锁的 flag 在 L5 中未定义: {', '.join(sorted(missing_in_l5)[:3])}")

    return issues


def check_l6_consistency(content: str) -> dict:
    """检查 L6 冒险笔记节点连续性"""
    issues = []

    # 优先使用 HTML 注释分隔符提取节点（v3.4+ 格式）
    header_pattern = re.compile(
        r'<!--\s*node:\s*(\S+)\s*\|\s*type:\s*(.+?)\s*\|\s*date:\s*(.+?)\s*\|\s*session:\s*(\d+)\s*-->'
    )
    header_matches = list(header_pattern.finditer(content))

    nodes = []
    if header_matches:
        for m in header_matches:
            full_id = m.group(1)
            sid_match = re.match(r'S(\d+)N(\d+)', full_id)
            if sid_match:
                nodes.append({
                    "full_id": full_id,
                    "session": int(sid_match.group(1)),
                    "seq": int(sid_match.group(2)),
                    "type": m.group(2).strip(),
                    "date": m.group(3).strip(),
                })
    else:
        # Fallback：旧格式（无 HTML 注释）
        node_ids = re.findall(r'node_id:\s*(S(\d+)N(\d+))', content)
        for full_id, session, seq in node_ids:
            nodes.append({"full_id": full_id, "session": int(session), "seq": int(seq), "type": "", "date": ""})
        if node_ids:
            issues.append("L6 节点缺少 HTML 注释分隔符（<!-- node: ... -->），建议批量更新")

    if not nodes:
        issues.append("L6 中没有找到任何节点")
        return {"nodes": [], "issues": issues, "last_node": None, "last_date": ""}

    # 检查连续性
    prev_session = None
    prev_seq = None
    for node in nodes:
        if prev_session is not None:
            if node["session"] == prev_session:
                if node["seq"] != prev_seq + 1:
                    issues.append(
                        f"节点 {node['full_id']}: 期望 seq={prev_seq + 1}，实际 seq={node['seq']}（可能跳号或重复）"
                    )
            elif node["session"] > prev_session:
                if node["seq"] != 1:
                    issues.append(
                        f"节点 {node['full_id']}: 新会话但 seq={node['seq']}（期望重置为 1）"
                    )
        prev_session = node["session"]
        prev_seq = node["seq"]

    # 检查会话索引一致性
    session_index = re.findall(r'\|\s*(\d+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|', content)
    if session_index:
        last_indexed_session = int(session_index[-1][0])
        last_node_session = nodes[-1]["session"]
        if last_indexed_session < last_node_session:
            issues.append(
                f"会话索引最后记录为 Session {last_indexed_session}，"
                f"但节点已到 Session {last_node_session}（会话索引可能需要更新）"
            )

    return {
        "nodes": [{"id": n["full_id"], "session": n["session"], "seq": n["seq"], "type": n["type"], "date": n["date"]} for n in nodes],
        "total_nodes": len(nodes),
        "last_node": nodes[-1]["full_id"],
        "last_date": nodes[-1].get("date", ""),
        "issues": issues
    }


def generate_save_skeleton(l6_data: dict, l4_data: dict, l5_data: dict) -> dict:
    """生成存档前情提要骨架"""
    skeleton = {
        "narrative_summary_prompt": "请用第一人称口语，约 200 tokens，概括当前冒险状态。",
        "full_recap_prompt": "请锚定最近 5-8 个节点，写 600-800 tokens 的完整回顾。",
        "save_snapshot_prompt": "请写 2-3 段叙事定格描写，作为下次会话的接续起点。",
        "last_node": l6_data.get("last_node"),
        "character_snapshot": l4_data.get("characters", {}),
        "world_snapshot": l5_data.get("state", {}),
    }
    return skeleton


def main():
    import argparse
    parser = argparse.ArgumentParser(description="D&D 状态同步与一致性检查")
    parser.add_argument("--mode", choices=["checkpoint", "save"], default="checkpoint",
                        help="checkpoint=轻量同步, save=完整存档")
    args = parser.parse_args()

    root = find_project_root()

    # 读取文件
    l4_content = read_file_safe(root / "L4_角色状态.md")
    l5_content = read_file_safe(root / "L5_世界状态.md")
    l6_content = read_file_safe(root / "L6_冒险笔记.md")

    # 一致性检查
    l4_check = check_l4_detailed(l4_content)
    l5_check = check_l5_consistency(l5_content)
    l6_check = check_l6_consistency(l6_content)
    cross_issues = check_l5_l6_alignment(l5_content, l6_content)

    # 汇总
    all_issues = l4_check["issues"] + l5_check["issues"] + l6_check["issues"] + cross_issues

    output = {
        "mode": args.mode,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "l4_status": l4_check,
        "l5_status": l5_check,
        "l6_status": l6_check,
        "cross_checks": {"issues": cross_issues},
        "all_issues": all_issues,
        "issue_count": len(all_issues),
    }

    if args.mode == "save":
        output["save_skeleton"] = generate_save_skeleton(l6_check, l4_check, l5_check)

    # 格式化输出
    print(f"{'='*50}")
    print(f"  状态同步报告 ({args.mode})")
    print(f"  时间: {output['timestamp']}")
    print(f"{'='*50}\n")

    # 角色快照
    print("## 角色状态 (L4)")
    for name, data in l4_check["characters"].items():
        hp = data.get("hp", "?")
        gold = data.get("gold", "?")
        ac = data.get("ac", "?")
        lvl = data.get("level", "?")
        xp = data.get("xp", "?")
        buffs = data.get("active_buffs", 0)
        print(f"  {name}: HP {hp}, AC {ac}, 金币 {gold} gp, 等级 {lvl} (XP {xp}), Buff {buffs} 个")
    print()

    # 世界状态
    print("## 世界状态 (L5)")
    state = l5_check["state"]
    print(f"  日期: {state.get('date', '?')}")
    print(f"  位置: {state.get('location', '?')}")
    print(f"  进度: {state.get('progress', '?')}")
    print(f"  待处理事件: {state.get('pending_events_count', 0)} 个")
    print()

    # 节点状态
    print("## 冒险笔记 (L6)")
    print(f"  总节点数: {l6_check['total_nodes']}")
    print(f"  最后节点: {l6_check.get('last_node', '无')}")
    if l6_check.get('last_date'):
        print(f"  最后节点日期: {l6_check['last_date']}")
    print()

    # 问题列表
    if all_issues:
        print(f"## ⚠ 发现 {len(all_issues)} 个问题:")
        for i, issue in enumerate(all_issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("## ✓ 一致性检查通过，无异常")

    if args.mode == "save":
        print("\n## 存档骨架")
        print("  AI 需要生成以下内容：")
        print("  1. 叙事摘要（第一人称，~200 tokens）")
        print("  2. 完整回顾（锚定最近节点，600-800 tokens）")
        print("  3. 存档快照（2-3 段叙事定格）")

    print(f"\n{'='*50}")

    # JSON 输出
    print("\n---JSON---")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
