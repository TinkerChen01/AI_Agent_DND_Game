"""Generate a blank L2 module skeleton following the standard template."""
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import argparse
import os

P = "【待填充】"


def _region_block(rid: str) -> str:
    """Generate the detail block for a single region."""
    return f"""\
### 地区 R{rid}：{P}地区名

#### 空间布局（DM 必读）

{P}：ASCII 总览图

```
（在此绘制地区内部结构）
```

**floorplan JSON（dnd-map 预制数据）：**

```json
{{
  "title": "{P}",
  "floors": [
    {{"id": "F1", "name": "{P}", "status": "unexplored", "rooms": ["{P}"]}}
  ],
  "connections": [["F1","F2"]]
}}
```

#### 节点 N0：{P}节点名

**场景描写**

{P}：感官细节描写，200-500字

**互动要素**

| 要素类型 | 描写 | 机制 |
|---------|------|------|
| 【NPC行为/环境机关/线索】 | {P} | {P} |

**可搜索物品表**

| 搜索位置 | 发现 | 备注 |
|---------|------|------|
| {P} | {P} | 【DC或自动】 |

**节点完成条件**

{P}
"""


def build_skeleton(name: str, level: str, regions: int) -> str:
    """Return the complete skeleton markdown as a string."""
    r2_row = f"| R2 | {P} | 【室内/野外/城镇/地下/异空间】 | 【N】 | 【N】 | 【有/无】 |" if regions == 2 else ""
    r2_detail = _region_block("2") if regions == 2 else ""
    r2_cross = f"""\
### 跨地区衔接

> 仅当模组有 2 个地区时填写。

{P}：从 R1 到 R2 的过渡方式（地理路径、时间跳跃、剧情转折）
""" if regions == 2 else ""
    ns = name.replace(" ", "_").lower()

    sections = []
    # Header
    sections.append(f"""\
# L2 — 模组框架：{name}

> 剧本骨架。定义主线节点、关键 NPC、关键地点和边界条件。
> **AI 在此框架内自由发挥细节，但不违背框架定义的设定。**""")
    # §0 速查索引
    sections.append(f"""\
## 〇、模组速查索引

### 0.1 地区表
| 地区ID | 地区名 | 类型 | 节点数 | 战斗数 | Boss |
|--------|--------|------|--------|--------|------|
| R1 | {P} | 【室内/野外/城镇/地下/异空间】 | 【N】 | 【N】 | 【有/无】 |
{r2_row}

### 0.2 节点索引表
| 节点ID | 标题 | 类型 | 地区 | 触发条件 | 完成条件 |
|--------|------|------|------|---------|---------|
| N0 | 【开场节点】 | 开场 | R1 | {P} | {P} |
| N1 | {P} | 【探索/解谜/战斗】 | R1 | {P} | {P} |
| N2 | {P} | 【Boss/结局】 | R1 | {P} | {P} |

### 0.3 战斗索引表
| 战斗ID | 标题 | 节点 | 敌人摘要 | 可选 | Boss |
|--------|------|------|---------|------|------|
| C0 | {P} | N? | {P} | 否 | 否 |

### 0.4 NPC 索引表
| NPC | 身份 | 地区 | 首次出现 | 立场 |
|-----|------|------|---------|------|
| {P} | {P} | R1 | N? | {P} |

### 0.5 奖励索引表
| 来源 | 物品/金币 | 感兴趣角色 |
|------|----------|-----------|
| {P} | {P} | {P} |""")
    # §一 模组概述
    sections.append(f"""\
## 一、模组概述

### 概述表
| 项目 | 内容 |
|------|------|
| **模组名称** | {name} |
| **等级范围** | {level} |
| **预计时长** | 【短团1章/中团2-3章】 |
| **核心钩子** | {P}：一句话吸引人的描述 |
| **故事引擎** | 【探索型/解咒型/讨伐型/拯救型/防卫型】 |
| **一句话版** | {P} |
| **素材引用** | {P}：素材库编号列表 |
| **地区数量** | {regions} |

### 开局接入

**接入方式 A — {P}触发地点**

{P}：开局场景描写，200-400字""")
    # §二 地区详设
    sec2 = f"## 二、地区详设\n\n{_region_block('1')}"
    if r2_detail:
        sec2 += f"\n{r2_detail}"
    sections.append(sec2)
    # §三 主线流程
    sec3 = f"""\
## 三、主线流程

### 节点流程图

```
[开场] N0 → N1 → 【Boss】 N2 → 【结局】
```

### 三幕结构标注

| 幕 | 对应节点 | 叙事功能 |
|----|---------|---------|
| **第一幕：钩子** | N0 | {P} |
| **第二幕：深入** | N1 | {P} |
| **第三幕：高潮** | N2 | {P} |"""
    if r2_cross:
        sec3 += f"\n\n{r2_cross}"
    sections.append(sec3)

    # §四 关键 NPC
    sections.append(f"""\
## 四、关键 NPC

### NPC 速查表

| NPC | 身份 | 立场 | 一句话描述 | AI 扮演要点 |
|-----|------|------|-----------|------------|
| {P} | {P} | {P} | {P} | {P} |

### NPC 深度背景

#### 【NPC名】

{P}：背景故事，200-500字""")

    # §五 战斗设计
    sections.append(f"""\
## 五、战斗设计

### 战斗速查表

| 战斗ID | 标题 | 节点 | 触发条件 | 敌人 | CR 预估 | 可选 |
|--------|------|------|---------|------|---------|------|
| C0 | {P} | N? | {P} | {P} | {P} | 否 |

### 战斗 C0 详细配置

#### 敌人数据

| 敌人 | 定位 | AC | HP | 攻击 | 特殊能力 |
|------|------|----|----|------|---------|
| {P} | 【头目/精英/杂兵】 | {P} | {P} | {P} | {P} |

#### 环境

{P}：战场地形描述

#### 胜利/结束条件

{P}""")

    # §六 奖励
    sections.append(f"""\
## 六、奖励

### 奖励总表

| 来源 | 类型 | 内容 | 素材编号 |
|------|------|------|---------|
| {P} | {P} | {P} | {P} |""")

    # §七 边界条件与失败安全网
    sections.append(f"""\
## 七、边界条件与失败安全网

### 边界条件

```
[✓] 允许的：
- {P}

[×] 不允许的：
- {P}
```

### 失败安全网

| 失败场景 | 兜底方案 |
|---------|---------|
| 关键 NPC 死亡 | {P} |
| 关键线索遗漏 | {P} |
| Boss 被击杀而非说服 | {P} |
| 玩家拒绝主线任务 | {P} |
| 玩家跳过地区 | {P} |""")

    # §八 模组完成条件与衔接
    sections.append(f"""\
## 八、模组完成条件与衔接

### 完成检查清单

| 条件 | 说明 |
|------|------|
| ☐ {P} | {P} |

### L5 初始状态模板

| 项目 | 初始值 |
|------|--------|
| 当前幕 | 第一章：【模组名】 |
| 游戏内日期 | {P} |
| 所在区域 | {P} |
| 具体位置 | {P} |
| 环境 | {P} |
| 氛围 | {P} |

**初始 Plot Flags：**

| Flag | 初始值 | 说明 |
|------|--------|------|
| module_{ns}_started | true | 【模组名】开始 |

**初始待处理事件：**

| 优先级 | 内容 | 触发条件 | 状态 |
|--------|------|---------|------|
| 高 | {P} | {P} | 待触发 |""")

    # §九 叙事锚点
    sections.append(f"""\
## 九、叙事锚点（DM 参考）

- **核心体验**：{P}
- **视觉基调**：{P}
- **叙事基调**：{P}
- **关键原则**：{P}""")

    return ("\n\n---\n\n".join(sections) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Generate a blank L2 module skeleton.")
    ap.add_argument("--name", required=True, help="Module name")
    ap.add_argument("--level", required=True, help='e.g. "Lv.4→Lv.5"')
    ap.add_argument("--regions", required=True, type=int, choices=[1, 2])
    ap.add_argument("--output", default=None, help="Output path (default: L2_{name}.md)")
    args = ap.parse_args()
    if args.output is None:
        args.output = f"L2_{args.name}.md"
    skeleton = build_skeleton(args.name, args.level, args.regions)
    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(skeleton)
    print(f"骨架已生成: {args.output}, {args.regions} 个地区, 等级范围 {args.level}")


if __name__ == "__main__":
    main()
