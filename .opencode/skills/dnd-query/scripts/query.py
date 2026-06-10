#!/usr/bin/env python3
"""
dnd-query: 跨文件情报检索脚本
用法: python query.py "关键词"
      python query.py "关键词" --files L2,L6
      python query.py "关键词" --max-results 5

在 L1-L6 数据文件和 Skill references 中搜索关键词，
输出结构化匹配结果。AI 基于结果生成摘要。
"""

import sys
import re
import json
import argparse
from pathlib import Path

# 确保 Windows 控制台使用 UTF-8 输出
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def find_project_root():
    """从脚本位置向上查找项目根目录（含 L1_世界设定.md 的目录）"""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "L1_世界设定.md").exists():
            return current
        current = current.parent
    # fallback: 脚本在 .opencode/skills/dnd-query/scripts/ 下
    return Path(__file__).resolve().parents[4]


def split_into_sections(content: str) -> list[dict]:
    """将 markdown 内容按标题拆分为段落"""
    sections = []
    current_title = ""
    current_lines = []

    for line in content.split("\n"):
        if re.match(r'^#{1,4}\s', line):
            if current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    sections.append({"title": current_title, "content": text})
            current_title = line.strip().lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        text = "\n".join(current_lines).strip()
        if text:
            sections.append({"title": current_title, "content": text})

    return sections


def search_file(filepath: Path, keyword: str, label: str, max_results: int = 10) -> list[dict]:
    """在单个文件中搜索关键词"""
    if not filepath.exists():
        return []

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return []

    keyword_lower = keyword.lower()
    sections = split_into_sections(content)
    matches = []

    for section in sections:
        full_text = f"{section['title']}\n{section['content']}"
        if keyword_lower in full_text.lower():
            # 提取包含关键词的上下文（前后各 2 行）
            lines = full_text.split("\n")
            context_lines = []
            for i, line in enumerate(lines):
                if keyword_lower in line.lower():
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    context_lines.append("\n".join(lines[start:end]))

            matches.append({
                "source": label,
                "section": section["title"] or "(文件开头)",
                "context": context_lines[:3],  # 最多 3 段上下文
                "filepath": str(filepath)
            })

            if len(matches) >= max_results:
                break

    return matches


def main():
    parser = argparse.ArgumentParser(description="D&D 跨文件情报检索")
    parser.add_argument("keyword", help="搜索关键词")
    parser.add_argument("--files", help="指定搜索文件（逗号分隔，如 L2,L6）", default=None)
    parser.add_argument("--max-results", type=int, default=15, help="最大结果数")
    args = parser.parse_args()

    root = find_project_root()
    keyword = args.keyword

    # 定义搜索范围
    all_files = {
        "L1_世界设定.md": "世界观",
        "L2_模组框架.md": "模组设计",
        "L4_角色状态.md": "角色数据",
        "L5_世界状态.md": "世界状态",
        "L6_冒险笔记.md": "冒险记录",
    }

    # Skill references
    skill_refs = {}
    skills_dir = root / ".opencode" / "skills"
    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            ref_dir = skill_dir / "references"
            if not ref_dir.exists():
                continue
            for ref_file in sorted(ref_dir.glob("*.md")):
                label = f"Skill:{skill_dir.name}/{ref_file.name}"
                skill_refs[str(ref_file)] = label

    # 如果指定了文件过滤
    if args.files:
        allowed = set(f.strip() for f in args.files.split(","))
        all_files = {k: v for k, v in all_files.items()
                     if any(a in k for a in allowed)}
        skill_refs = {k: v for k, v in skill_refs.items()
                      if any(a in k for a in allowed)}

    # 执行搜索
    all_matches = []

    for fname, label in all_files.items():
        filepath = root / fname
        matches = search_file(filepath, keyword, label, args.max_results)
        all_matches.extend(matches)

    for fpath_str, label in skill_refs.items():
        matches = search_file(Path(fpath_str), keyword, label, args.max_results)
        all_matches.extend(matches)

    # 输出结果
    output = {
        "keyword": keyword,
        "total_matches": len(all_matches),
        "results": all_matches[:args.max_results]
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
