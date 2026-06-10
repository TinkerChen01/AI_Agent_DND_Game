#!/usr/bin/env python3
"""
dnd-settle: 冒险故事书骨架生成器
用法: python generate_storybook.py
      python generate_storybook.py --module-name "丝线回廊" --chapter 2

从 L6 节点自动生成冒险故事书骨架（幕/场划分、登场人物、
关系年表、关键事件时间线），AI 往骨架里填充叙事文字即可。
"""

import re
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


def extract_nodes(content: str) -> list:
    """从 L6 提取所有节点的完整数据"""
    nodes = []

    # 按 node_id 分块
    blocks = re.split(r'(?=^node_id:\s)', content, flags=re.MULTILINE)

    for block in blocks:
        if not block.strip().startswith("node_id:"):
            continue

        node = {}
        # 基础字段
        for field in ["node_id", "type", "title", "in_game_date"]:
            m = re.search(rf'^{field}:\s*(.+?)$', block, re.MULTILINE)
            if m:
                node[field] = m.group(1).strip()

        # summary (多行)
        m = re.search(r'summary:\s*\|\s*\n(.*?)(?=\nkey_events:|\ncharacter_changes:|\Z)', block, re.DOTALL)
        if m:
            node["summary"] = m.group(1).strip()

        # key_events
        events = re.findall(r'  - (.+)', block)
        if events:
            node["key_events"] = events

        # character_changes
        changes = {}
        change_section = re.search(r'character_changes:\s*\n(.*?)(?=\nloot_acquired:|\nunlock_flags:|\Z)', block, re.DOTALL)
        if change_section:
            for line in change_section.group(1).strip().split("\n"):
                m = re.match(r'\s+(\S+):\s*(.+)', line)
                if m:
                    changes[m.group(1)] = m.group(2).strip()
        node["character_changes"] = changes

        # loot
        loot_section = re.search(r'loot_acquired:\s*\n(.*?)(?=\nunlock_flags:|\ndm_notes:|\Z)', block, re.DOTALL)
        if loot_section:
            loot_items = re.findall(r'  - (.+)', loot_section.group(1))
            node["loot"] = loot_items

        # dm_notes
        m = re.search(r'dm_notes:\s*(.+)', block)
        if m:
            node["dm_notes"] = m.group(1).strip()

        if node.get("node_id"):
            nodes.append(node)

    return nodes


def extract_relationship_changes(content: str) -> list:
    """从 L6 节点中提取关系变化事件"""
    changes = []
    nodes = extract_nodes(content)

    for node in nodes:
        if node.get("type") == "角色发展":
            changes.append({
                "date": node.get("in_game_date", ""),
                "event": node.get("title", ""),
                "detail": node.get("summary", ""),
            })
        # 也检查 key_events 中的关系关键词
        for event in node.get("key_events", []):
            keywords = ["关系", "暧昧", "亲密", "恋人", "友善", "跨档", "浪漫"]
            if any(kw in event for kw in keywords):
                changes.append({
                    "date": node.get("in_game_date", ""),
                    "event": event,
                    "node": node.get("node_id"),
                })

    return changes


def group_into_acts(nodes: list) -> list:
    """将节点分组为幕（Act）"""
    if not nodes:
        return []

    acts = []
    current_act = {"title": "", "nodes": []}

    # 简单分组策略：按 type 变化或场景切换分幕
    type_groups = []
    current_type = None
    for node in nodes:
        if node.get("type") != current_type and len(current_act["nodes"]) >= 2:
            type_groups.append(current_act)
            current_act = {"title": "", "nodes": []}
        current_type = node.get("type")
        current_act["nodes"].append(node)

    if current_act["nodes"]:
        type_groups.append(current_act)

    # 命名幕
    for i, group in enumerate(type_groups, 1):
        first_node = group["nodes"][0]
        group["title"] = f"第{i}幕：{first_node.get('title', '未知')}"

    return type_groups


def extract_appearing_characters(nodes: list) -> dict:
    """从节点中提取登场人物"""
    characters = {}
    name_keywords = {
        "兰斯": "人类野蛮人",
        "卡芙卡": "半精灵邪术士",
        "艾尔莎": "面包师妻子",
        "托米": "被困的男孩",
        "赫尔穆特": "炼金术师",
        "格鲁什": "匪帮副官",
        "伊芙琳": "贵族小姐",
        "科温": "龙枪骑士",
        "布隆": "矮人铁匠",
        "科恩": "散塔林联系人",
        "灰手套": "匪帮头目",
    }

    for node in nodes:
        text = json.dumps(node, ensure_ascii=False)
        for name, role in name_keywords.items():
            if name in text:
                if name not in characters:
                    characters[name] = {"role": role, "first_appear": node.get("node_id", ""), "appearances": 0}
                characters[name]["appearances"] += 1

    return characters


def generate_markdown(module_name: str, chapter: int, nodes: list, acts: list,
                      characters: dict, rel_changes: list) -> str:
    """生成故事书 markdown 骨架"""

    md = f"""# 第 {chapter} 章：{module_name}

> **[卷首语——AI 请填写一句点明本段冒险核心的话语]**

## 登场人物

| 角色 | 身份 | 一句话描述 |
|------|------|-----------|
"""

    for name, data in characters.items():
        md += f"| {name} | {data['role']} | [AI 填写] |\n"

    md += "\n## 冒险正文\n\n"

    for act in acts:
        md += f"### {act['title']}\n\n"
        for node in act["nodes"]:
            md += f"#### {node.get('title', '未命名事件')}\n"
            md += f"*{node.get('in_game_date', '')}*\n\n"
            md += f"[AI 基于以下摘要展开叙事]\n\n"
            md += f"> 摘要：{node.get('summary', '无')}\n"
            if node.get("key_events"):
                md += f">\n> 关键事件：\n"
                for event in node["key_events"]:
                    md += f"> - {event}\n"
            md += "\n"

    # 名场面
    md += """## 名场面

> **[AI 从冒险中选出 3-5 个最具画面感的瞬间]**

> **「场景标题」**
>
> [AI 描述名场面，3-5 句话，定格在最具画面感的瞬间]

"""

    # 关系年表
    md += "## 关系年表\n\n"
    md += "| 时间 | 变化 | 契机 |\n"
    md += "|------|------|------|\n"

    if rel_changes:
        for change in rel_changes:
            md += f"| {change.get('date', '?')} | {change.get('event', '?')} | {change.get('detail', change.get('node', ''))} |\n"
    else:
        md += "| （本模组无关系变化，或 AI 补充） | | |\n"

    # 结局定帧
    md += """
## 结局定帧

[AI 填写模组结束时的最后一幕描写——画面、光线、空气、未说完的话]
"""

    return md


def main():
    parser = argparse.ArgumentParser(description="D&D 冒险故事书骨架生成器")
    parser.add_argument("--module-name", default="", help="模组名称")
    parser.add_argument("--chapter", type=int, default=1, help="章节号")
    args = parser.parse_args()

    root = find_project_root()

    # 读取 L6
    l6_content = read_file_safe(root / "L6_冒险笔记.md")

    # 读取 L2 获取模组名
    l2_content = read_file_safe(root / "L2_模组框架.md")
    module_name = args.module_name
    if not module_name:
        m = re.search(r'\*\*模组名称\*\*\s*\|\s*(.+?)\s*\|', l2_content)
        if m:
            module_name = m.group(1).strip()
        else:
            module_name = "未命名模组"

    # 提取数据
    nodes = extract_nodes(l6_content)
    acts = group_into_acts(nodes)
    characters = extract_appearing_characters(nodes)
    rel_changes = extract_relationship_changes(l6_content)

    # 生成骨架
    storybook = generate_markdown(module_name, args.chapter, nodes, acts, characters, rel_changes)

    print(storybook)

    # JSON 摘要
    print("\n---JSON---")
    summary = {
        "module_name": module_name,
        "chapter": args.chapter,
        "total_nodes": len(nodes),
        "total_acts": len(acts),
        "characters_found": len(characters),
        "relationship_changes": len(rel_changes),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
