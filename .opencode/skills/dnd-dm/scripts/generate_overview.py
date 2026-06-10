#!/usr/bin/env python3
"""
dnd-dm: 战役总览生成脚本
用法: python generate_overview.py

从 L4/L5/L6 提取关键数据，生成 L0_战役总览.md。
存档流程中由 dnd-save 调用，或独立运行查看当前状态。
"""

import re
import sys
from pathlib import Path
from datetime import datetime

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


def extract_l4(l4: str) -> dict:
    """提取角色摘要"""
    chars = []
    for name in ["兰斯", "卡芙卡"]:
        pattern = rf'## (?:一|二)、{name}.*?(?=## (?:一|二|三)、|\Z)'
        match = re.search(pattern, l4, re.DOTALL)
        if not match:
            continue
        section = match.group(0)
        data = {"name": name}

        hp = re.search(r'HP 当前/最大.*?\|\s*\*\*(\d+)\s*/\s*(\d+)\*\*', section)
        if hp:
            data["hp"] = f"{hp.group(1)}/{hp.group(2)}"

        gold = re.search(r'金币.*?\|\s*\*\*(\d+)', section)
        if gold:
            data["gold"] = int(gold.group(1))

        level = re.search(r'等级.*?\|\s*\*\*(\d+)\*\*', section)
        if level:
            data["level"] = int(level.group(1))

        # 关系
        relations = []
        rel_pattern = re.compile(r'^\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|', re.MULTILINE)
        in_rel = False
        for line in section.split("\n"):
            if "关系表" in line:
                in_rel = True
                continue
            if in_rel and line.startswith("|") and "---" not in line:
                m = rel_pattern.match(line)
                if m and m.group(1) not in ("对象", "—", "", "（其他在游戏过程中追加）"):
                    relations.append({
                        "target": m.group(1),
                        "level": m.group(2),
                        "trend": m.group(3),
                    })
            if in_rel and line.startswith("### ") and "关系" not in line:
                in_rel = False

        data["relations"] = relations
        chars.append(data)

    # 队伍共有资金
    team_gold = re.search(r'队伍资金.*?\|\s*(\d+)\s*gp', l4)
    team = {"gold": int(team_gold.group(1)) if team_gold else 0}

    return {"characters": chars, "team": team}


def extract_l5(l5: str) -> dict:
    """提取世界状态摘要"""
    data = {}

    kv = {
        "campaign": r'\*\*战役名称\*\*\s*\|\s*(.+?)\s*\|',
        "act": r'\*\*当前幕\*\*\s*\|\s*(.+?)\s*\|',
        "date": r'\*\*游戏内日期\*\*\s*\|\s*(.+?)\s*\|',
        "location": r'\*\*具体位置\*\*\s*\|\s*(.+?)\s*\|',
    }
    for key, pattern in kv.items():
        m = re.search(pattern, l5)
        if m:
            data[key] = m.group(1).strip()

    # 活跃任务
    quests = []
    quest_pattern = re.compile(r'\|\s*(.+?)\s*\|\s*([✅🔍❌]+.*?)(?=\s*\|)\s*\|\s*(.+?)\s*\|')
    for m in quest_pattern.finditer(l5):
        name = m.group(1).strip()
        if name and name not in ("任务", ""):
            quests.append({"name": name, "status": m.group(2).strip(), "note": m.group(3).strip()})
    data["quests"] = quests

    # 待处理事件
    pending = []
    pending_pattern = re.compile(r'\|\s*(高|中|低)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|')
    for m in pending_pattern.finditer(l5):
        if m.group(1).strip() in ("高", "中", "低"):
            pending.append({
                "priority": m.group(1).strip(),
                "content": m.group(2).strip(),
                "status": m.group(4).strip(),
            })
    data["pending"] = pending

    # 势力（只在 "## 五、势力动态" 到下一个 "##" 之间搜索）
    forces = []
    force_section = re.search(r'## 五、势力动态\s*\n(.*?)(?=\n## |\Z)', l5, re.DOTALL)
    if force_section:
        force_text = force_section.group(1)
        force_pattern = re.compile(r'^\|\s*(\S.*?)\s*\|\s*(\S.*?)\s*\|\s*([^\|]*?)\s*\|\s*(.+?)\s*\|$', re.MULTILINE)
        for m in force_pattern.finditer(force_text):
            name = m.group(1).strip()
            if name not in ("势力", "---", "") and "---" not in name and not re.match(r'^-+$', name):
                forces.append({"name": name, "status": m.group(4).strip()})
    data["forces"] = forces

    return data


def extract_l6(l6: str) -> dict:
    """提取冒险记录摘要"""
    data = {}

    # 过往冒险摘要
    past_match = re.search(
        r'## 过往冒险摘要\s*\n.*?\n(?:\|.*?\|.*?\|\s*\n)((?:\|.*?\|.*?\|\s*\n)+)',
        l6
    )
    if past_match:
        rows = re.findall(r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|', past_match.group(1))
        data["past_adventures"] = [{"module": r[0], "summary": r[1]} for r in rows if r[0] not in ("模组", "---")]

    # 最新节点
    header_pattern = re.compile(
        r'<!--\s*node:\s*(\S+)\s*\|\s*type:\s*(.+?)\s*\|\s*date:\s*(.+?)\s*\|\s*session:\s*(\d+)\s*-->'
    )
    nodes = []
    for m in header_pattern.finditer(l6):
        nodes.append({
            "id": m.group(1),
            "type": m.group(2).strip(),
            "date": m.group(3).strip(),
        })
    data["recent_nodes"] = nodes[-3:] if len(nodes) > 3 else nodes
    data["total_sessions"] = max(
        (int(re.search(r'S(\d+)', n["id"]).group(1)) for n in nodes if re.search(r'S(\d+)', n["id"])),
        default=0
    )
    data["total_nodes"] = len(nodes)

    return data


def extract_l2_hooks(l2: str) -> list:
    """从 L2 提取下个模组钩子"""
    hooks = []
    hook_section = re.search(r'### 下个模组钩子\s*\n(.*?)(?=\n###|\n---|\Z)', l2, re.DOTALL)
    if hook_section:
        for line in hook_section.group(1).split("\n"):
            line = line.strip()
            if line.startswith("- **"):
                # 清理格式：- **名称**：描述 → 名称：描述
                line = re.sub(r'^- \*\*(.+?)\*\*', r'\1', line)
                hooks.append(line.strip())
            elif line.startswith("- "):
                hooks.append(line[2:].strip())
    return hooks


def generate_overview(l4: str, l5: str, l6: str, l2: str) -> str:
    """生成战役总览 markdown"""
    d4 = extract_l4(l4)
    d5 = extract_l5(l5)
    d6 = extract_l6(l6)
    hooks = extract_l2_hooks(l2)

    lines = []
    lines.append("# 兰斯的冒险 — 战役总览")
    lines.append("")
    lines.append(f"> 自动更新于 {datetime.now().strftime('%Y-%m-%d %H:%M')}。此文件由脚本生成，请勿手动编辑。")
    lines.append("")

    # 当前状态
    lines.append("## 当前状态")
    lines.append("")
    if d5.get("campaign"):
        lines.append(f"**战役**：{d5['campaign']}  ")
    if d5.get("act"):
        lines.append(f"**当前幕**：{d5['act']}  ")
    if d5.get("date"):
        lines.append(f"**游戏内日期**：{d5['date']}  ")
    if d5.get("location"):
        lines.append(f"**当前位置**：{d5['location']}  ")
    lines.append("")

    # 角色状态
    for char in d4.get("characters", []):
        rels = ", ".join(f"{r['target']}（{r['level']}·{r['trend']}）" for r in char.get("relations", []))
        lines.append(f"**{char['name']}**：Lv.{char.get('level', '?')}  HP {char.get('hp', '?')}  金币 {char.get('gold', '?')} gp")
        if rels:
            lines.append(f"  关系：{rels}")
        lines.append("")

    team_gold = d4.get("team", {}).get("gold", 0)
    if team_gold:
        lines.append(f"**队伍共享**：{team_gold} gp  ")
    lines.append("")

    # 已完成模组
    if d6.get("past_adventures"):
        lines.append("## 已完成模组")
        lines.append("")
        for adv in d6["past_adventures"]:
            lines.append(f"- [x] **{adv['module']}** — {adv['summary']}")
        lines.append("")

    # 进行中
    active_quests = [q for q in d5.get("quests", []) if "进行中" in q.get("status", "")]
    if active_quests:
        lines.append("## 进行中")
        lines.append("")
        for q in active_quests:
            lines.append(f"- [ ] **{q['name']}** — {q['note']}")
        lines.append("")

    # 待处理事件
    if d5.get("pending"):
        lines.append("## 待处理事件")
        lines.append("")
        for p in d5["pending"]:
            lines.append(f"- [{p['priority']}] {p['content']}（{p['status']}）")
        lines.append("")

    # 势力动态
    if d5.get("forces"):
        lines.append("## 势力动态")
        lines.append("")
        for f in d5["forces"]:
            lines.append(f"- **{f['name']}**：{f['status']}")
        lines.append("")

    # 下个模组钩子
    if hooks:
        lines.append("## 待开启钩子")
        lines.append("")
        for h in hooks:
            lines.append(f"- [ ] {h}")
        lines.append("")

    # 最近节点
    if d6.get("recent_nodes"):
        lines.append("## 最近事件")
        lines.append("")
        for n in d6["recent_nodes"]:
            lines.append(f"- `{n['id']}` {n['type']} | {n['date']}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*总节点数：{d6.get('total_nodes', 0)}  |  总会话数：{d6.get('total_sessions', 0)}*")

    return "\n".join(lines)


def main():
    root = find_project_root()
    l4 = read_file_safe(root / "L4_角色状态.md")
    l5 = read_file_safe(root / "L5_世界状态.md")
    l6 = read_file_safe(root / "L6_冒险笔记.md")
    l2 = read_file_safe(root / "L2_模组框架.md")

    overview = generate_overview(l4, l5, l6, l2)

    # 写入 L0 文件
    output_path = root / "L0_战役总览.md"
    output_path.write_text(overview, encoding="utf-8")

    print(overview)
    print(f"\n✓ 已写入 {output_path}")


if __name__ == "__main__":
    main()
