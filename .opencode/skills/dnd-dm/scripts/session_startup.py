#!/usr/bin/env python3
"""
dnd-dm: 会话启动数据聚合脚本
用法: python session_startup.py

读取 L1-L6 全部数据文件，提取关键信息，
输出一份结构化的"会话启动数据包"。
AI 基于此数据包生成战役梗概和接续叙事，无需逐一读取原始文件。
"""

import re
import json
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
    except Exception as e:
        return f"[读取失败: {e}]"


def extract_l6_data(content: str) -> dict:
    """从 L6 提取叙事摘要、前情提要、存档快照、最近节点"""
    data = {
        "campaign_name": "",
        "narrative_summary": "",
        "full_recap": "",
        "save_snapshot": "",
        "recent_nodes": [],
        "past_adventures": "",
    }

    # 过往冒险摘要
    past_match = re.search(
        r'## 过往冒险摘要\s*\n.*?\n\|.*?\|.*?\|\s*\n((?:\|.*?\|.*?\|\s*\n)+)',
        content
    )
    if past_match:
        data["past_adventures"] = past_match.group(1).strip()

    # 叙事摘要
    summary_match = re.search(
        r'### ① 叙事摘要\s*\n(.*?)(?=\n### ②|\Z)',
        content, re.DOTALL
    )
    if summary_match:
        data["narrative_summary"] = summary_match.group(1).strip()

    # 完整回顾
    recap_match = re.search(
        r'### ② 完整回顾\s*\n(.*?)(?=\n### ③|\Z)',
        content, re.DOTALL
    )
    if recap_match:
        data["full_recap"] = recap_match.group(1).strip()

    # 存档快照
    snapshot_match = re.search(
        r'### ③ 存档快照\s*\n(.*?)(?=\n## |\Z)',
        content, re.DOTALL
    )
    if snapshot_match:
        data["save_snapshot"] = snapshot_match.group(1).strip()

    # 节点记录 - 利用 HTML 注释分隔符提取节点（更稳定）
    nodes = []
    # 匹配 <!-- node: ID | type: TYPE | date: DATE | session: N --> 格式
    header_pattern = re.compile(
        r'<!--\s*node:\s*(\S+)\s*\|\s*type:\s*(.+?)\s*\|\s*date:\s*(.+?)\s*\|\s*session:\s*(\d+)\s*-->'
    )
    # 按节点分块：找到所有注释位置，然后截取注释到下一个注释（或文件结尾）之间的内容
    matches = list(header_pattern.finditer(content))
    for i, m in enumerate(matches):
        node_id = m.group(1)
        node_type = m.group(2).strip()
        node_date = m.group(3).strip()
        session_num = int(m.group(4))
        # 截取该节点的完整内容
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block = content[start:end]
        # 从块中提取 title 和 summary
        title_match = re.search(r'title:\s*(.+?)\s*\n', block)
        title = title_match.group(1).strip() if title_match else ""
        summary_match = re.search(r'summary:\s*\|\s*\n(.*?)(?=\nkey_events:|\ncharacter_changes:|\nloot_acquired:|\nunlock_flags:|\n\n## |\Z)', block, re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else ""
        # 清理 summary 中的缩进管道符（YAML 多行格式）
        summary_lines = [line.lstrip() for line in summary.split('\n')]
        summary_clean = ' '.join(summary_lines)
        nodes.append({
            "node_id": node_id,
            "type": node_type,
            "title": title,
            "in_game_date": node_date,
            "session": session_num,
            "summary": summary_clean
        })

    # 只取最近 3 个节点
    data["recent_nodes"] = nodes[-3:] if len(nodes) > 3 else nodes

    return data


def extract_l5_data(content: str) -> dict:
    """从 L5 提取当前世界状态"""
    data = {
        "campaign_name": "",
        "current_act": "",
        "date": "",
        "time": "",
        "weather": "",
        "module_progress": "",
        "location_area": "",
        "location_specific": "",
        "environment": "",
        "companions": [],
        "active_quests": [],
        "plot_flags": {},
    }

    # 简单键值提取
    kv_patterns = {
        "campaign_name": r'\*\*战役名称\*\*\s*\|\s*(.+?)\s*\|',
        "current_act": r'\*\*当前幕\*\*\s*\|\s*(.+?)\s*\|',
        "date": r'\*\*游戏内日期\*\*\s*\|\s*(.+?)\s*\|',
        "time": r'\*\*当前时间\*\*\s*\|\s*(.+?)\s*\|',
        "weather": r'\*\*天气\*\*\s*\|\s*(.+?)\s*\|',
        "module_progress": r'\*\*模组进度\*\*\s*\|\s*(.+?)\s*\|',
        "location_area": r'所在区域.*?\|\s*\*\*(.+?)\*\*',
        "location_specific": r'具体位置.*?\|\s*\*\*(.+?)\*\*',
    }

    for key, pattern in kv_patterns.items():
        m = re.search(pattern, content)
        if m:
            data[key] = m.group(1).strip()

    # 同伴状态
    companion_pattern = re.compile(r'\|\s*(\S+)\s*\|\s*(.+?)\s*\|')
    in_companion = False
    for line in content.split("\n"):
        if "同行者" in line:
            in_companion = True
            continue
        if in_companion and line.startswith("|") and "---" not in line:
            m = companion_pattern.match(line)
            if m and m.group(1) not in ("角色", ""):
                data["companions"].append({
                    "name": m.group(1),
                    "status": m.group(2)
                })
        if in_companion and line.startswith("## "):
            in_companion = False

    # 活跃任务
    quest_pattern = re.compile(r'\|\s*(.+?)\s*\|\s*([✅🔍❌]+.*?)(?=\s*\|)\s*\|\s*(.+?)\s*\|')
    for m in quest_pattern.finditer(content):
        quest_name = m.group(1).strip()
        if quest_name not in ("任务", ""):
            data["active_quests"].append({
                "name": quest_name,
                "status": m.group(2).strip(),
                "note": m.group(3).strip()
            })

    # 待处理事件
    pending = []
    pending_pattern = re.compile(r'\|\s*(高|中|低)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|')
    for m in pending_pattern.finditer(content):
        priority = m.group(1).strip()
        if priority in ("高", "中", "低"):
            pending.append({
                "priority": priority,
                "content": m.group(2).strip(),
                "trigger": m.group(3).strip(),
                "status": m.group(4).strip()
            })
    data["pending_events"] = pending

    return data


def extract_l4_data(content: str) -> dict:
    """从 L4 提取角色当前状态"""
    data = {"characters": []}

    # 按角色分块
    char_sections = re.split(r'^## (一|二|三)、', content, flags=re.MULTILINE)

    for i in range(1, len(char_sections), 2):
        section = char_sections[i + 1] if i + 1 < len(char_sections) else ""
        char = {}

        # 名字
        name_match = re.search(r'^#\s*#+\s*(.+)', section, re.MULTILINE)
        if not name_match:
            # 从标题推断
            title = char_sections[i]
            if "兰斯" in title or "一" in title:
                char["name"] = "兰斯"
            elif "卡芙卡" in title or "二" in title:
                char["name"] = "卡芙卡"
            else:
                char["name"] = "未知"

        # HP
        hp_match = re.search(r'HP 当前/最大.*?\|\s*\*\*(\d+)\s*/\s*(\d+)\*\*', section)
        if hp_match:
            char["hp_current"] = int(hp_match.group(1))
            char["hp_max"] = int(hp_match.group(2))

        # AC
        ac_match = re.search(r'AC.*?\|\s*\*\*(\d+)\*\*', section)
        if ac_match:
            char["ac"] = int(ac_match.group(1))

        # 金币
        gold_match = re.search(r'金币.*?\|\s*\*\*(\d+)\s*gp\*\*', section)
        if gold_match:
            char["gold"] = int(gold_match.group(1))

        # 等级
        level_match = re.search(r'等级.*?\|\s*\*\*(\d+)\*\*', section)
        if level_match:
            char["level"] = int(level_match.group(1))

        # 狂暴次数
        rage_match = re.search(r'狂暴次数.*?\|\s*(\d+)\s*/\s*(\d+)', section)
        if rage_match:
            char["rage_uses"] = int(rage_match.group(1))
            char["rage_max"] = int(rage_match.group(2))

        # 法术位
        spell_match = re.search(r'邪术士法术位.*?\|\s*(\d+)\s*/\s*(\d+)', section)
        if spell_match:
            char["spell_slots"] = int(spell_match.group(1))
            char["spell_slots_max"] = int(spell_match.group(2))

        # Buff/Debuff
        buff_section = re.search(r'### Buff.*?\n(.*?)(?=\n### |\Z)', section, re.DOTALL)
        if buff_section:
            buffs = [l.strip() for l in buff_section.group(1).split("\n")
                     if l.strip() and "---" not in l and "状态" not in l]
            char["buffs"] = [b for b in buffs if "—" not in b]

        data["characters"].append(char)

    return data


def extract_l2_brief(content: str) -> dict:
    """从 L2 提取模组关键信息（精简版）"""
    data = {
        "module_name": "",
        "level_range": "",
        "main_nodes": [],
        "pending_node": "",
    }

    name_match = re.search(r'\*\*模组名称\*\*\s*\|\s*(.+?)\s*\|', content)
    if name_match:
        data["module_name"] = name_match.group(1).strip()

    level_match = re.search(r'\*\*等级范围\*\*\s*\|\s*(.+?)\s*\|', content)
    if level_match:
        data["level_range"] = level_match.group(1).strip()

    # 提取主线节点标题
    node_titles = re.findall(r'### (节点 \d+：.+)', content)
    data["main_nodes"] = node_titles

    return data


def extract_l1_brief(content: str) -> str:
    """从 L1 提取世界观关键标签（一段话）"""
    # 取文件前 30 行作为精华
    lines = content.split("\n")[:30]
    # 去掉空行和纯格式行
    meaningful = [l for l in lines if l.strip() and not l.strip().startswith("---")]
    return "\n".join(meaningful[:15])


def main():
    root = find_project_root()

    # 读取所有文件
    l1 = read_file_safe(root / "L1_世界设定.md")
    l2 = read_file_safe(root / "L2_模组框架.md")
    l4 = read_file_safe(root / "L4_角色状态.md")
    l5 = read_file_safe(root / "L5_世界状态.md")
    l6 = read_file_safe(root / "L6_冒险笔记.md")

    # 提取数据
    l6_data = extract_l6_data(l6)
    l5_data = extract_l5_data(l5)
    l4_data = extract_l4_data(l4)
    l2_data = extract_l2_brief(l2)
    l1_brief = extract_l1_brief(l1)

    # 组装会话启动数据包
    startup_packet = {
        "session_startup_data": {
            "world_setting_brief": l1_brief,
            "module": l2_data,
            "current_state": {
                "campaign": l5_data.get("campaign_name", ""),
                "act": l5_data.get("current_act", ""),
                "date": l5_data.get("date", ""),
                "time": l5_data.get("time", ""),
                "weather": l5_data.get("weather", ""),
                "module_progress": l5_data.get("module_progress", ""),
                "location": {
                    "area": l5_data.get("location_area", ""),
                    "specific": l5_data.get("location_specific", ""),
                    "environment": l5_data.get("environment", ""),
                },
                "companions": l5_data.get("companions", []),
                "active_quests": l5_data.get("active_quests", []),
                "pending_events": l5_data.get("pending_events", []),
            },
            "characters": l4_data.get("characters", []),
            "memory": {
                "past_adventures": l6_data.get("past_adventures", ""),
                "narrative_summary": l6_data.get("narrative_summary", ""),
                "full_recap": l6_data.get("full_recap", ""),
                "save_snapshot": l6_data.get("save_snapshot", ""),
                "recent_nodes": l6_data.get("recent_nodes", []),
            }
        }
    }

    print(json.dumps(startup_packet, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
