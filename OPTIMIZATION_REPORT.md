# AI Agent DND Game — 全面优化分析报告

> 分析对象：`D:\Project\AI_Agent_DND_Game`（v3.1 架构）
> 分析日期：2026-06-10

---

## 一、项目整体评价

这是一个架构设计非常成熟的 AI 跑团项目。从 v1.0 (Claude Code) → v2.0 (Hermes) → v3.0 (OpenCode) 的演进路径可以看出，你已经在 Skill 分层、token 优化、按需加载方面做了大量思考。v3.1 的角色 Skill 重构（SKILL.md 精简至 ~20 行锚点 + references 按需查阅）是一个很漂亮的设计决策。

以下从三个维度提出优化建议：**Script 注入**、**战术地图可视化**、**其他结构性改进**。

---

## 二、Script 注入优化（Token 减负核心）

### 2.1 什么是 Skill Scripts？

Agent Skill 标准目录结构如下：

```
skill-name/
├── SKILL.md          # 必需：元数据 + 行为指令
├── references/       # 可选：静态知识文档（AI 阅读用）
├── scripts/          # 可选：可执行脚本（AI 执行用，不读内容）
└── assets/           # 可选：模板、素材等
```

`scripts/` 目录下的文件是**可执行代码**（Python / Bash / Node.js），Agent 在需要时直接调用执行，**不需要读取脚本内容到上下文**。这意味着：

| 维度 | references/ | scripts/ |
|------|-------------|----------|
| 内容性质 | 静态文档（给 AI 读的） | 可执行代码（给机器跑的） |
| Token 消耗 | AI 读取时消耗 tokens | 不消耗 tokens（只执行，不阅读） |
| 确定性 | LLM 可能遗漏/误读 | 程序执行，100% 确定性 |
| 适用场景 | 叙事风格、角色设定、规则解释 | 数据检索、数值计算、文件操作、格式化输出 |

### 2.2 当前各 Skill 的 Script 机会分析

以下是按优先级排序的 script 注入建议。**核心原则：把"结构化操作"从 SKILL.md 的指令描述中抽出来，变成确定性执行的脚本。**

---

### 优先级 1：dnd-query — 跨文件情报检索（最高收益）

**当前问题：** 玩家说"查一下格鲁什"，AI 需要依次读取 L1、L2、L4、L5、L6 五个文件，在上下文中扫描匹配，然后生成摘要。每次查询可能消耗 3000-5000 tokens（大部分是读文件的开销），而且 AI 可能遗漏某些文件中的信息。

**Script 方案：**

```
dnd-query/
├── SKILL.md
└── scripts/
    └── query.py
```

`scripts/query.py` 的接口设计：

```python
# 调用方式：python scripts/query.py "格鲁什"
# 输出：结构化的匹配结果 JSON

import sys, re, json
from pathlib import Path

KEYWORD = sys.argv[1]
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # 回到项目根

SEARCH_FILES = {
    "L1_世界设定.md": "世界观",
    "L2_模组框架.md": "模组设计",
    "L4_角色状态.md": "角色数据",
    "L5_世界状态.md": "世界状态",
    "L6_冒险笔记.md": "冒险记录",
}

results = {}
for fname, label in SEARCH_FILES.items():
    fpath = PROJECT_ROOT / fname
    if not fpath.exists():
        continue
    content = fpath.read_text(encoding="utf-8")
    # 搜索包含关键词的段落（按 ## 或 ### 分块）
    sections = re.split(r'\n(?=##+ )', content)
    matches = [s.strip() for s in sections if KEYWORD.lower() in s.lower()]
    if matches:
        results[label] = matches

# 也搜索 skill references
SKILL_DIRS = PROJECT_ROOT / ".opencode" / "skills"
for skill_dir in SKILL_DIRS.iterdir():
    ref_dir = skill_dir / "references"
    if not ref_dir.exists():
        continue
    for ref_file in ref_dir.glob("*.md"):
        content = ref_file.read_text(encoding="utf-8")
        sections = re.split(r'\n(?=##+ )', content)
        matches = [s.strip() for s in sections if KEYWORD.lower() in s.lower()]
        if matches:
            results[f"Skill:{skill_dir.name}/{ref_file.name}"] = matches

print(json.dumps(results, ensure_ascii=False, indent=2))
```

**SKILL.md 中的引用方式改为：**

```markdown
## 流程

1. 执行 `python scripts/query.py "关键词"` 获取结构化检索结果
2. 基于检索结果，输出简洁摘要（< 300 字）
3. 如果结果为空，告知玩家"未找到相关信息"
```

**Token 收益估算：** 每次查询从 ~3000-5000 tokens（读全部文件）降至 ~200-500 tokens（只看匹配结果），降幅约 90%。

---

### 优先级 2：dnd-combat — 战斗初始化与回合管理

**当前问题：** 战斗初始化时，AI 需要读 L4 获取所有参战者数据，读 L2 获取敌人数据，手动投先攻骰，然后按模板格式写入 L4b。这个过程涉及大量数值操作和格式化输出，AI 容易算错或格式不对。

**Script 方案：**

```
dnd-combat/
├── SKILL.md
├── references/
│   └── l4b-template.md
└── scripts/
    ├── init_combat.py    # 战斗初始化
    └── roll_dice.py      # 通用骰子工具
```

**`scripts/roll_dice.py` — 通用骰子引擎：**

```python
# 调用方式：
# python scripts/roll_dice.py 2d6+5        → 掷 2d6+5
# python scripts/roll_dice.py init:1d20+2  → 先攻骰
# python scripts/roll_dice.py attack:+7    → 攻击骰（1d20+7）
# python scripts/roll_dice.py advantage:+7 → 优势骰

import sys, random, re

def roll(expr):
    """解析并执行骰子表达式"""
    m = re.match(r'(\d*)d(\d+)([+-]\d+)?', expr)
    if not m:
        return None
    count = int(m.group(1) or 1)
    sides = int(m.group(2))
    mod = int(m.group(3) or 0)
    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + mod
    return {"rolls": rolls, "modifier": mod, "total": total}

# ... 完整实现含 advantage/disadvantage 等
```

**`scripts/init_combat.py` — 战斗初始化器：**

```python
# 调用方式：python scripts/init_combat.py
# 功能：
# 1. 从 L4 读取兰斯和卡芙卡的当前 HP/AC/先攻加值
# 2. 从 L2 读取当前遭遇的敌人数据（根据 L5 的当前场景匹配）
# 3. 为所有参战者投先攻
# 4. 生成完整的 L4b 战斗日志内容（按模板格式）
# 5. 输出到 stdout，AI 直接覆盖写入 L4b

# 这个脚本可以把"读数据 → 投骰 → 格式化"的全流程自动化
# AI 只需要：1) 调用脚本 2) 写一段场景描写 3) 提示当前行动者
```

**Token 收益：** 战斗初始化从 ~1500-2000 tokens（读 L4+L2+格式化 L4b）降至 ~300-500 tokens（读脚本输出 + 写叙事），同时消除计算错误风险。

---

### 优先级 3：dnd-city-rest — 休整自动化

**当前问题：** 休整时 AI 需要手动投 d20、查表、计算费用、更新 L4 金币、推进 L5 日期。每个休整日都是一轮"读表 → 计算 → 改文件"的循环。

**Script 方案：**

```
dnd-city-rest/
├── SKILL.md
├── references/
│   └── encounter-tables.md
└── scripts/
    └── rest_day.py
```

**`scripts/rest_day.py`：**

```python
# 调用方式：python scripts/rest_day.py --days 3 --quality standard
# 功能：
# 1. 为每天投 d20 决定遭遇类型
# 2. 计算总费用（daily_cost × days）
# 3. 输出每天遭遇摘要 + 费用明细 + L4 需要更新的字段
#
# 输出示例：
# Day 1 (翠雨月20日): d20=7 → 安眠之夜（下一天豁免优势） | 费用: 5sp
# Day 2 (翠雨月21日): d20=14 → 水土不服（力量/体质检定劣势） | 费用: 5sp
# Day 3 (翠雨月22日): d20=18 → 大事件：街头火并（投 d6 决定类型） | 费用: 5sp
# ---
# 总费用: 15sp (1gp 5sp)
# L4 更新: 兰斯金币 424→422 gp 5sp, 卡芙卡金币 769→767 gp 8sp（分摊）
```

**Token 收益：** 3 天休整从 ~3 轮交互（每轮 ~500 tokens）降至 1 次脚本调用 + 1 次叙事（~800 tokens 总计）。

---

### 优先级 4：dnd-save / dnd-checkpoint — 状态同步自动化

**当前问题：** 存档和检查点都需要 AI 逐一读 L4/L5/L6，与上下文比对，然后格式化写入。这个过程完全可以用脚本辅助。

**Script 方案：**

```
dnd-save/
├── SKILL.md
└── scripts/
    └── sync_state.py
```

```python
# 调用方式：python scripts/sync_state.py --mode checkpoint
# 或：python scripts/sync_state.py --mode save --session-summary "本次发生了什么"
#
# 功能：
# 1. 读取 L4/L5/L6 当前状态，输出结构化快照
# 2. 检查 L6 节点连续性（node_id 是否连续）
# 3. 检查 L5 时间线与 L6 节点的一致性
# 4. (save 模式) 生成前情提要的骨架模板（AI 填充叙事部分）
# 5. (save 模式) 可选执行 git commit
```

---

### 优先级 5：dnd-dm — 会话启动加速

**当前问题：** 会话启动时 AI 需要按顺序读 L6 → L1 → L2 → L4 → L5，然后合成战役梗概。这是 5 次文件读取操作，每次都将整个文件内容注入上下文。

**Script 方案：**

```
dnd-dm/
├── SKILL.md
├── references/
│   └── ...
└── scripts/
    └── session_startup.py
```

```python
# 调用方式：python scripts/session_startup.py
#
# 功能：
# 1. 读取 L6，提取：叙事摘要、前情提要、存档快照、最近 2-3 个节点
# 2. 读取 L1，提取：世界观关键标签（一段话）
# 3. 读取 L2，提取：当前模组进度和待处理事件
# 4. 读取 L4+L5，提取：角色当前状态 + 世界状态
# 5. 合成一份结构化的"会话启动数据包"（JSON 或格式化文本）
#
# AI 只需要读取这个数据包，然后基于它生成战役梗概和接续叙事
```

**Token 收益估算：** 从 ~8000-12000 tokens（全量读取 5 个文件）降至 ~2000-3000 tokens（结构化摘要），降幅约 70-75%。这是所有 script 中单次收益最大的。

---

### 优先级 6：dnd-settle — 结算自动化

```
dnd-settle/
├── SKILL.md
├── references/
│   └── storybook-format.md
└── scripts/
    └── generate_storybook.py
```

脚本从 L6 节点自动生成冒险故事书骨架（幕/场划分、关键事件提取、关系年表），AI 只需要往骨架里填充叙事文字。

---

### Script 注入总览

| Skill | 新增 Script | 主要功能 | Token 降幅（估） |
|-------|-------------|---------|----------------|
| dnd-query | `query.py` | 跨文件关键词检索 | ~90% |
| dnd-combat | `init_combat.py`, `roll_dice.py` | 战斗初始化 + 骰子 | ~75% |
| dnd-city-rest | `rest_day.py` | 休整日自动化 | ~60% |
| dnd-save | `sync_state.py` | 状态同步 + 一致性检查 | ~50% |
| dnd-dm | `session_startup.py` | 会话启动数据聚合 | ~70% |
| dnd-settle | `generate_storybook.py` | 故事书骨架生成 | ~40% |

**实施建议：** 优先实现 dnd-query 的 `query.py` 和 dnd-dm 的 `session_startup.py`，这两个是每次游戏都会高频触发的，收益最大。

---

## 三、战术地图可视化系统

### 3.1 设计方案

你提到希望在战斗和探索场景中使用符号化的可视地图。这完全可以做到，而且不需要外部图片——用等宽字符（monospace ASCII art）就能实现很好的效果。

建议新建一个 `dnd-map` Skill：

```
dnd-map/
├── SKILL.md
├── references/
│   └── map-symbols.md        # 符号图例和使用规范
└── scripts/
    └── render_map.py         # 地图渲染引擎
```

### 3.2 符号体系（map-symbols.md）

```markdown
# 地图符号图例

## 基础符号

| 符号 | 含义 | 示例 |
|------|------|------|
| @ | 玩家角色（兰斯） | 地图上的 @ 标记 |
| K | 卡芙卡 | 队友 NPC |
| E | 敌人（通用） | 可以用 E1, E2 区分 |
| N | 中立 NPC | 非战斗人员 |
| . | 可通行地面 | |
| # | 墙壁/不可通行 | |
| ~ | 水域/危险地形 | |
| ^ | 高处/台阶 | |
| = | 门（关闭） | |
| ▯ | 门（打开） | |
| □ | 箱子/家具/障碍物 | |
| △ | 陷阱/危险标记 | |
| ○ | 物品/战利品 | |
| * | 火源/光源 | |
| ? | 未知区域/迷雾 | |

## 标注规则

- 角色名标注：@兰斯  K卡芙卡  E1兽人  E2地精
- 距离标注：在两个符号之间用数字标注格数
- 方向标注：N/S/E/W 或 ↑↓→←
- 高度层：用不同行分隔，标注 [1F] [2F] 等
```

### 3.3 地图格式示例

**战斗地图（在 L4b 战斗日志中嵌入）：**

```
╔══════════════════════════════════════╗
║  灰夫人庄园 · 门厅战斗 · 回合 2      ║
╠══════════════════════════════════════╣
║                                      ║
║   #######=====#######               ║
║   #.....#  □  #.....#               ║
║   #.....#     #.....#               ║
║   #..@..=     =..K..#    ← 2F 走廊  ║
║   #.....#     #.....#               ║
║   #..E1.#  *  #..E2.#               ║
║   #.....#     #.....#               ║
║   #######=====#######               ║
║          ○                          ║
║       (掉落物)                       ║
║                                      ║
╠══════════════════════════════════════╣
║  图例: @兰斯(HP:45) K卡芙卡(HP:31)   ║
║  E1人偶(HP:18/25) E2人偶(HP:25/25)  ║
║  ○ 碎裂的人偶零件  * 壁炉(光源)      ║
║  距离: @→E1 = 15ft  K→E2 = 20ft     ║
╚══════════════════════════════════════╝
```

**探索地图（场景切换时展示）：**

```
┌─────────────────────────────────────┐
│  灰夫人庄园 · 楼层总览               │
├─────────────────────────────────────┤
│                                     │
│  [3F] ┌──────────────┐              │
│       │ 画室 ← 当前   │              │
│       └──────┬───────┘              │
│              │ 楼梯                  │
│  [2F] ┌──────┴───────┐              │
│       │ 书房 = 铁门→? │              │
│       └──────┬───────┘              │
│              │ 楼梯                  │
│  [1F] ┌──────┴───────┐   ┌───────┐ │
│       │ 门厅   走廊   │──→│ 厨房  │ │
│       └──────┬───────┘   └───────┘ │
│              │ 前门                  │
│  [B1] ┌──────┴───────┐              │
│       │ ??? 魔法封印   │              │
│       └──────────────┘              │
│                                     │
│  已知: 1F门厅(已探索) 2F书房(已探索)  │
│        3F画室(当前) B1(未探索,封印)   │
└─────────────────────────────────────┘
```

### 3.4 `scripts/render_map.py` 设计

```python
# 调用方式：
# python scripts/render_map.py --type combat --data combat_map.json
# python scripts/render_map.py --type explore --location "灰夫人庄园"
# python scripts/render_map.py --type floorplan --floors "1F:门厅,2F:书房,3F:画室" --current "3F"
#
# 输入：JSON 格式的地图数据
# 输出：ASCII 格式的可视地图（直接嵌入叙事输出）
#
# 地图数据结构示例（combat）：
# {
#   "title": "灰夫人庄园 · 门厅战斗",
#   "grid": [
#     ["#","#","#","#","#","#","#"],
#     ["#",".",".",".",".",".","#"],
#     ["#",".","@",".",".",".","#"],
#     ...
#   ],
#   "entities": [
#     {"symbol": "@", "name": "兰斯", "hp": "45/45", "pos": [2,1]},
#     {"symbol": "K", "name": "卡芙卡", "hp": "31/31", "pos": [2,5]},
#     {"symbol": "E1", "name": "人偶A", "hp": "18/25", "pos": [5,2]}
#   ],
#   "legend": ["*壁炉(光源)", "○掉落物"]
# }
```

### 3.5 集成方式

**与 dnd-combat 集成：** 战斗初始化时，`init_combat.py` 生成 L4b 的同时也生成初始战斗地图数据，`render_map.py` 渲染输出。每回合更新实体位置。

**与 dnd-scene 集成：** 场景切换时，如果新场景有已知的空间布局，自动生成探索地图。

**SKILL.md 中的触发规则：**

```markdown
## 何时展示地图

| 场景 | 自动展示 |
|------|---------|
| 战斗初始化 | 是（必须） |
| 战斗中每回合 | 是（更新位置） |
| 进入新区域（首次探索） | 是（如果空间结构已知） |
| 玩家问"周围有什么" | 是 |
| 战斗中距离/位置有疑问 | 是 |
| 普通对话/叙事 | 否 |
```

---

## 四、其他结构性优化建议

### 4.1 dnd-node Skill 缺失

你的 `RESTRUCTURE_PLAN.md` 中设计了 `dnd-node`（L6 节点追加）Skill，但当前 `.opencode/skills/` 中并不存在这个 Skill。L6 节点的追加逻辑散落在 dnd-save、dnd-checkpoint、dnd-scene 中。

**建议：** 要么补建 `dnd-node` Skill（专注 L6 节点的格式化和追加逻辑），要么在 ARCHITECTURE.md 中明确说明节点追加由哪个 Skill 负责，避免歧义。

### 4.2 L4 与 Skill Reference 的数据冗余

`dnd-kafka/references/character-sheet.md` 和 `dnd-lance/references/character-sheet.md` 中存的是静态快照，而 L4 是动态数据源。这造成了同一个数据（比如卡芙卡的 HP 最大值 31）存在于两个地方。

**当前方案是合理的**（RESTRUCTURE_PLAN 中也说了"冗余的代价很小"），但建议加一条安全规则：

> 在 `dnd-kafka` 和 `dnd-lance` 的 SKILL.md 的 Reference 查阅表中，**character-sheet.md 行**追加一句："⚠ 此为创建时快照，所有实时数据以 L4 为准。"

这能防止 AI 在 L4 更新后仍然引用旧快照的数据。

### 4.3 NPC 快速生成 Skill

当前 dnd-expand 负责模组扩展，但没有一个 Skill 专门处理"AI 需要在叙事中临时创建 NPC"的场景。DM 红线说"不要凭空创造重要 NPC"，但普通 NPC（酒保、路人、商人）是免不了的。

**建议新增 `dnd-npcgen` Skill：**

```
dnd-npcgen/
├── SKILL.md           # NPC 生成规则 + 命名风格
└── scripts/
    └── gen_npc.py     # 随机生成 NPC 基础数据
```

脚本可以随机生成：名字（符合 Forgotten Realms 风格）、种族、职业、关系初始值、一句话人设。AI 只需要调用脚本获取骨架，然后补充个性化描写。

### 4.4 氛围骰子系统

当前 dnd-dm 的叙事原则提到"氛围优先"，但没有给 AI 具体的氛围生成工具。

**建议在 dnd-dm 的 references/ 中新增 `atmosphere-tables.md`：**

按场景类型（森林、城市、地下城、庄园、战斗）提供 d6 感官描写表：

```markdown
## d6 森林感官

1. 松脂和湿泥的气味混在一起，脚下的落叶发出细碎的声响
2. 远处有啄木鸟的节奏，近处的灌木丛里有什么东西在动
3. 阳光穿过树冠在地面投下碎金般的光斑，空气中有蜂蜜一样的暖意
4. 风穿过树梢发出叹息般的声音，带来远处溪水的气息
5. 雾气从地面升起，树木的轮廓变得模糊，一切都笼罩在灰绿色的薄纱中
6. 夜幕降临后森林反而更吵——蛙鸣、虫声、偶尔一声不知名动物的嚎叫
```

AI 在进入新场景时投一个 d6，把结果自然融入描写中。这不需要做成 script（因为 AI 需要读取内容来融入叙事），放在 references/ 中按需加载即可。

### 4.5 L6 节点增加结构化 frontmatter

当前 L6 节点是纯 YAML-like 格式，但缺少机器可读的分隔符。如果未来要做 `query.py` 之类的检索，建议在每个节点前加一个 HTML 注释作为分隔标记：

```markdown
<!-- node: S2N3 | type: 探索 | date: 翠雨月19日 -->

node_id: S2N3
type: 探索
title: 灰夫人庄园初探——门厅、书房与画室
...
```

这样脚本可以用正则快速定位节点边界，不需要解析整个文件。

### 4.6 关系追踪自动化

当前关系系统（5 档 + trend + 浪漫标签）完全靠 AI 记忆和手动判断。在长会话中 AI 可能忘记追踪 trend 计数。

**建议在 dnd-dm SKILL.md 中增加一条自检提醒：**

```markdown
## 关系自检（每次互动后）

涉及 NPC 互动时，快速过一遍：
1. 这次互动是否包含关系信号？（是→继续，否→跳过）
2. 信号方向？（正面→↑  负面→↓）
3. 当前 trend 累计是否触发跨档？（2个同向→跨档）
4. 是否需要更新浪漫计数？
```

更好的方案是写一个 `scripts/relationship_check.py`，输入当前关系数据和本次互动类型，自动计算是否跨档。

### 4.7 定时存档提醒

RESTRUCTURE_PLAN 中提到原 Hermes Agent 有 cron 定时提醒存档的功能，OpenCode 环境下暂未实现。

**替代方案：** 在 dnd-dm SKILL.md 的"工作规范"中增加一条：

```markdown
### 存档提醒

在以下时机主动建议存档：
- 战斗结束后
- 场景切换（地图级）后
- 关系跨档后
- 玩家完成一个重要决策后
- 对话超过 20 轮未存档时
```

### 4.8 dnd-combat 增加"快速战斗"模式

当前战斗流程是完整的回合制，适合重要战斗。但对于小遭遇（比如 dnd-city-rest 中骰到 18 的"街头火并"），完整的 L4b 初始化 + 回合管理 + 结算太重了。

**建议在 dnd-combat SKILL.md 中增加一个分流：**

```markdown
## 战斗分级

| 级别 | 判断标准 | 流程 |
|------|---------|------|
| 完整战斗 | Boss 战、主线战斗、玩家主动发起 | 完整流程（初始化→回合→结算） |
| 快速战斗 | 随机遭遇、小怪清理、休整日事件 | 简化流程（AI 叙述为主，2-3 次关键检定决定结果） |
```

---

## 五、优先级排序总表

| 优先级 | 优化项 | 类型 | 预期收益 | 实施难度 |
|--------|--------|------|---------|---------|
| P0 | dnd-query 添加 `query.py` | Script | Token 降 90%，查询准确度大幅提升 | 低 |
| P0 | dnd-dm 添加 `session_startup.py` | Script | 会话启动 Token 降 70%，启动速度大幅提升 | 中 |
| P1 | dnd-combat 添加 `roll_dice.py` + `init_combat.py` | Script | 战斗初始化自动化，消除计算错误 | 中 |
| P1 | 新建 `dnd-map` Skill（战术地图） | 新功能 | 战斗空间感大幅提升，玩家体验改善 | 中 |
| P2 | dnd-city-rest 添加 `rest_day.py` | Script | 休整流程自动化 | 低 |
| P2 | dnd-save 添加 `sync_state.py` | Script | 存档一致性检查自动化 | 低 |
| P2 | 补建 `dnd-node` Skill 或明确其职责归属 | 结构修复 | 消除节点追加逻辑的分散问题 | 低 |
| P3 | 新增 `dnd-npcgen` Skill | 新功能 | NPC 生成规范化 | 低 |
| P3 | 新增 `atmosphere-tables.md` reference | 内容增强 | 场景描写丰富度提升 | 低 |
| P3 | L6 节点增加结构化分隔标记 | 结构优化 | 为未来脚本化检索打基础 | 低 |
| P3 | 关系追踪 `relationship_check.py` | Script | 消除 trend 计数遗漏风险 | 低 |
| P4 | 快速战斗模式分流 | 规则增强 | 小遭遇不再需要完整战斗流程 | 低 |
| P4 | 定时存档提醒规则 | 规则增强 | 防止长会话忘记存档 | 极低 |

---

## 六、总结

你的项目在架构层面已经做得很好——Skill 分层清晰、按需加载策略合理、角色 Skill 的行为锚点设计很精巧。最大的优化空间在于：**把"AI 按指令做操作"变成"脚本执行操作 + AI 做叙事"。** 这不仅能大幅降低 token 消耗，还能消除数值计算错误、格式不一致等 LLM 固有的不确定性问题。

Script 注入的核心思路是：**凡是"确定性的、结构化的、可重复的"操作，都应该交给脚本；凡是"需要创造力、判断力、叙事能力"的操作，才留给 AI。** 你的 SKILL.md 已经很好地把"规则"和"操作"分开了，下一步就是把"操作"部分进一步脚本化。

战术地图系统是一个独立的新功能维度，它能将纯文字的跑团体验提升为"可视觉化的战术博弈"，尤其在战斗和探索场景中价值很大。等宽字符方案零成本、零依赖，非常适合你的项目。
