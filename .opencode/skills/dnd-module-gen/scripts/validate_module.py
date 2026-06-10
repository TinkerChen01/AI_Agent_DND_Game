#!/usr/bin/env python3
"""L2 模组文件验证器 — 校验 L2 markdown 是否符合标准模板规范."""
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import argparse, re, json
from pathlib import Path

def find_default_file(start: Path) -> Path | None:
    cur = start.resolve()
    for _ in range(6):
        candidate = cur / "L2_模组框架.md"
        if candidate.is_file():
            return candidate
        if cur.parent == cur:
            break
        cur = cur.parent
    return None

def extract_module_name(lines: list[str]) -> str:
    for line in lines:
        s = line.strip()
        if s and s.startswith("#"):
            return s.lstrip("#").strip()
        if s:
            return s
    return "(未知)"

def extract_table_rows(lines: list[str], start: int, keyword: str) -> list[str]:
    idx = -1
    for i in range(start, len(lines)):
        if keyword in lines[i]:
            idx = i; break
    if idx == -1:
        return []
    rows: list[str] = []
    for i in range(idx + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith("|"):
            rows.append(s)
        elif s.startswith("## ") or s.startswith("### "):
            break
    return rows

def validate(text: str, filepath: str) -> tuple[int, int, str]:
    lines = text.splitlines()
    passed = total = 0
    fails: list[str] = []
    results: list[str] = []

    def record(ok: bool, label: str, detail: str = ""):
        nonlocal passed, total
        total += 1
        tag = "[PASS]" if ok else "[FAIL]"
        if ok and detail:
            msg = f"{tag} {label} ({detail})"
        elif not ok and detail:
            msg = f"{tag} {label}: {detail}"
        else:
            msg = f"{tag} {label}"
        results.append(msg)
        if ok:
            passed += 1
        else:
            fails.append(msg)

    # 1. §〇 速查索引存在性
    record(any("## 〇、模组速查索引" in l for l in lines), "§〇 速查索引存在")

    # 2. 索引表完整性
    subs = ["0.1 地区表", "0.2 节点索引表", "0.3 战斗索引表", "0.4 NPC 索引表", "0.5 奖励索引表"]
    found = [s for s in subs if any(s in l for l in lines)]
    miss = [s for s in subs if s not in found]
    record(not miss, "索引表完整性",
           f"{len(found)}/{len(subs)}" if not miss else f"缺少 {', '.join(miss)}")

    # 3. 必填节存在性
    reqd = ["## 一、模组概述", "## 二、", "## 三、", "## 五、", "## 七、", "## 八、"]
    freq = [r for r in reqd if any(r in l for l in lines)]
    mreq = [r for r in reqd if r not in freq]
    record(not mreq, "必填节存在性",
           f"{len(freq)}/{len(reqd)}" if not mreq else f"缺少 {', '.join(mreq)}")

    # 4. 节点连续性
    node_ids: list[int] = []
    for row in extract_table_rows(lines, 0, "0.2 节点索引表"):
        for m in re.finditer(r"N(\d+)", row):
            if (nid := int(m.group(1))) not in node_ids:
                node_ids.append(nid)
    node_ids.sort()
    if node_ids:
        gaps = [f"N{n}" for n in range(node_ids[0], node_ids[-1] + 1) if n not in node_ids]
        record(not gaps, "节点连续性",
               f"{len(node_ids)} 个节点" if not gaps else f"缺少 {', '.join(gaps)}")
    else:
        record(False, "节点连续性", "未找到节点 ID")

    # 5. 战斗-节点对应
    crefs: list[str] = []
    for row in extract_table_rows(lines, 0, "0.3 战斗索引表"):
        crefs.extend(re.findall(r"N\d+", row))
    if crefs:
        bad = [r for r in crefs if int(r[1:]) not in node_ids]
        record(not bad, "战斗-节点对应",
               f"{len(crefs)}/{len(crefs)}" if not bad else f"无效引用 {', '.join(bad)}")
    else:
        record(True, "战斗-节点对应", "0/0 (无战斗条目)")

    # 6. 地区空间布局
    rids: list[str] = []
    for row in extract_table_rows(lines, 0, "0.1 地区表"):
        rids.extend(re.findall(r"R(\d+)", row))
    if rids:
        mr = [f"R{r}" for r in rids if not any(f"### 地区 R{r}" in l for l in lines)]
        record(not mr, "地区空间布局",
               f"{len(rids)}/{len(rids)}" if not mr else f"缺少 {', '.join(mr)} 节")
    else:
        record(True, "地区空间布局", "0/0 (无地区条目)")

    # 7. floorplan JSON
    rsec = [i for i, l in enumerate(lines) if re.match(r"###\s+地区\s+R\d+", l)]
    jbad: list[str] = []
    for idx, ss in enumerate(rsec):
        se = rsec[idx + 1] if idx + 1 < len(rsec) else len(lines)
        block = "\n".join(lines[ss:se])
        jm = re.search(r"```json\s*\n([\s\S]*?)```", block)
        h = lines[ss].strip()
        if not jm:
            jbad.append(f"{h} 缺少 JSON"); continue
        try:
            data = json.loads(jm.group(1))
            if "title" not in data or "floors" not in data:
                jbad.append(f"{h} 缺少 title/floors")
        except json.JSONDecodeError:
            jbad.append(f"{h} JSON 解析失败")
    if rsec:
        record(not jbad, "floorplan JSON",
               f"{len(rsec)}/{len(rsec)}" if not jbad else "; ".join(jbad))
    else:
        record(True, "floorplan JSON", "无地区节 (跳过)")

    # 8-11. 简单关键字检查
    for kw, label in [("失败安全网", "失败安全网"), ("完成检查清单", "完成检查清单"),
                      ("L5 初始状态模板", "L5 初始状态模板"), ("叙事锚点", "叙事锚点")]:
        record(any(kw in l for l in lines), label)

    # 组装报告
    name = extract_module_name(lines)
    hdr = f"=== L2 模组验证报告 ===\n文件: {filepath}\n模组名: {name}\n"
    summary = f"\n结果: {passed}/{total} 项通过"
    fdetail = "\n\n--- 未通过项 ---\n" + "\n".join(f"  {f}" for f in fails) if fails else ""
    return passed, total, f"{hdr}\n{chr(10).join(results)}\n{summary}{fdetail}"

def main() -> int:
    parser = argparse.ArgumentParser(description="L2 模组文件验证器")
    parser.add_argument("--file", "-f", type=str, default=None, help="L2 模组 markdown 文件路径")
    args = parser.parse_args()
    fp = Path(args.file) if args.file else (find_default_file(Path.cwd()) or Path("L2_模组框架.md"))
    if not fp.is_file():
        print(f"[ERROR] 文件不存在: {fp}", file=sys.stderr)
        return 1
    text = fp.read_text(encoding="utf-8")
    passed, total, report = validate(text, str(fp))
    print(report)
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
