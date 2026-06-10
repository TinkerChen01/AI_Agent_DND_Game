## AI Agent DND Game — 重构计划

> 目标平台：OpenCode
> 设计原则：SKILL.md 只放稳定的核心指令，动态数据放 reference，SKILL.md 告诉 AI "什么场景读什么 reference"
> 最后更新：2026-06-08

---

### 一、现状诊断

当前项目从 Claude Code 迁移到 Hermes Agent，现在要迁移到 OpenCode。每次迁移都暴露同一个结构性问题：行为规则、角色扮演指令、游戏数据、操作手册混在一起，靠一个大文件（先是 CLAUDE.md/L0，后是 dnd-dm Skill）一股脑注入 system prompt。

具体的三个核心问题：

**dnd-dm 过载。** 当前 SKILL.md 约 400 行，把"每轮对话都需要的核心规则"（叙事原则、检定规则、DM 红线）和"偶尔需要的操作手册"（回滚协议表格、场景切换翻车模式、cron 配置、主线归位模式清单）全部平铺在一起。每轮对话白白消耗数百 token 在不会用到的内容上。

**角色扮演没有独立触发机制。** 卡芙卡的人设散落在 L3 人物卡（数据文件，不自动触发）和 dnd-dm 的"队友 NPC 扮演规则"（通用规则，不是卡芙卡专属）里。随着上下文压缩，角色扮演质量会逐渐下降。理想状态是：提到"卡芙卡"就自动加载她的性格锚点和说话风格。

**L3 人物卡的定位尴尬。** 它既包含静态的身份信息（性格、背景、能力列表），又和 L4 角色状态（HP、金币、装备）存在职责重叠。两个角色的数据混在一个文件里，AI 无法按需加载单个角色的信息。

---

### 二、目标架构

```
.opencode/skills/
├── dnd-dm/                        ← DM 行为总纲（核心规则，精简版）
│   ├── SKILL.md
│   └── references/
│       ├── session-startup.md      ← 会话启动读取顺序 + 陷阱警示
│       ├── rollback-protocol.md    ← 回滚类型表 + 拒绝权 + 同步规则
│       ├── scene-discipline.md     ← 场景切换确认纪律 + 翻车模式
│       ├── mainline-return.md      ← 主线归位模式清单 + 避坑
│       └── relationship-rules.md   ← 关系判定完整表格 + trend 结算 + 浪漫标签
│
├── dnd-kafka/                      ← 卡芙卡：角色扮演 Skill
│   ├── SKILL.md
│   └── references/
│       ├── character-sheet.md      ← 属性、法术、装备、战斗数据（来自原 L3+L4）
│       └── background.md           ← 背景故事、关键经历节点、关系演变记录
│
├── dnd-lance/                      ← 兰斯：玩家角色参考 Skill
│   ├── SKILL.md
│   └── references/
│       ├── character-sheet.md      ← 属性、装备、攻击数据（来自原 L3+L4）
│       └── background.md           ← 背景故事
│
├── dnd-save/                       ← 存档流程
│   └── SKILL.md
│
├── dnd-combat/                     ← 战斗初始化 + 结算归档
│   ├── SKILL.md
│   └── references/
│       └── l4b-template.md         ← L4b 战斗日志模板格式
│
├── dnd-checkpoint/                 ← 轻量状态同步
│   └── SKILL.md
│
├── dnd-node/                       ← L6 节点追加
│   └── SKILL.md
│
├── dnd-query/                      ← 跨文件情报检索
│   └── SKILL.md
│
├── dnd-expand/                     ← 模组动态扩展
│   └── SKILL.md
│
├── dnd-city-rest/                  ← 城市休整与随机遭遇
│   ├── SKILL.md
│   └── references/
│       └── encounter-tables.md     ← d20 随机遭遇表详细内容
│
└── dnd-settle/                     ← 模组结算
    ├── SKILL.md
    └── references/
        └── storybook-format.md     ← 冒险故事书格式模板


项目根目录/
├── L1_世界设定.md                   ← 不变（静态世界观）
├── L2_模组框架.md                   ← 不变（当前模组骨架）
├── L4_角色状态.md                   ← 保留，但结构微调（见 §4.4）
├── L4b_战斗日志.md                  ← 不变
├── L5_世界状态.md                   ← 不变
├── L6_冒险笔记.md                   ← 不变
└── backups/                        ← 旧文件统一归档
    ├── L3_人物卡.md                 ← 内容已迁入 dnd-kafka + dnd-lance
    ├── L7_城市休整与随机遭遇.md      ← 内容已迁入 dnd-city-rest
    ├── 技能文件备份/                 ← 旧 Hermes 格式 Skill
    ├── 旧版规则文件备份/             ← Claude Code 时代文件
    ├── 旧模组/
    └── 其他历史备份...
```

---

### 三、Skill 详细设计

#### 3.1 dnd-dm — DM 行为总纲

**定位：** 每轮对话都需要的核心规则，注入 system prompt 后全程有效。

**SKILL.md 内容（目标 ~150 行，当前 ~400 行）：**

```
frontmatter:
  name: dnd-dm
  description: >
    D&D 5e AI跑团DM规则总纲。加载后AI按规则主持游戏。
    触发词：游戏继续、跑团、DND、D&D、兰斯、卡芙卡、丝线回廊
```

SKILL.md 保留以下内容：

| 章节 | 内容 | 来源 |
|------|------|------|
| 项目身份 | 文件体系速查表（L1-L7 + Skill 清单），一句话定位 | 原 dnd-dm §一 |
| 模式切换 | 游戏模式 / 助手模式 / 存档指令的判断规则 | 原 dnd-dm §二 |
| 会话启动 | 精简版：读取顺序（一行），接续叙事原则（2-3行）。完整版指向 reference | 原 dnd-dm §三 精简 |
| 叙事原则 | 7 条叙事原则、对话格式、队友 NPC 扮演规则（通用框架） | 原 dnd-dm §四 |
| 检定规则 | 代掷 / 自投 / 暗骰规则 | 原 dnd-dm §5.1 |
| 战斗流程 | 三阶段骨架（初始化→回合→结算），不含 L4b 格式 | 原 dnd-dm §5.2 精简 |
| 关系判定 | 精简版：5 档名称 + 一句话说明。完整表格指向 reference | 原 dnd-dm §5.4 精简 |
| DM 红线 | 8 条红线，原文保留 | 原 dnd-dm §七 |
| 工作规范 | 状态文件直接操作、节奏控制 | 原 dnd-dm §十 |
| Reference 路由 | 告诉 AI 什么场景读什么 reference | 新增 |

**移出到 references/ 的内容：**

| Reference 文件 | 内容 | 从哪移出 |
|----------------|------|---------|
| `session-startup.md` | 完整读取顺序（9步）、战役梗概模板、接续叙事模板、会话启动陷阱详述 | 原 dnd-dm §3.1-3.4 |
| `rollback-protocol.md` | 回滚类型表、回滚后同步规则、AI 拒绝权条件 | 原 dnd-dm §六 |
| `scene-discipline.md` | 场景切换确认纪律、典型翻车模式（4种）、出口自检问题 | 原 dnd-dm §4.6 |
| `mainline-return.md` | 主线归位原则详述、6 种常用模式表、避坑规则、当前模组归位示例 | 原 dnd-dm §八 + 原 CLAUDE.md §七 |
| `relationship-rules.md` | trend 结算规则、浪漫标签触发条件表、完整判定流程 | 原 dnd-dm §5.4 详细部分 |

**新增：Reference 路由表**

在 SKILL.md 末尾加一个路由表，告诉 AI 什么时候该去读 reference：

```markdown
## Reference 查阅指南

| 场景 | 读取 |
|------|------|
| 会话启动 / 新对话开始 | references/session-startup.md |
| 玩家要求回滚 / "收回刚才的话" | references/rollback-protocol.md |
| 切换到新场景且记忆模糊 | references/scene-discipline.md |
| 玩家多次拒绝主线钩子 | references/mainline-return.md |
| 关系跨档 / 浪漫互动计数 | references/relationship-rules.md |
```

---

#### 3.2 dnd-kafka — 卡芙卡角色扮演

**定位：** AI 扮演卡芙卡的核心指令。提到"卡芙卡"时自动加载，确保角色扮演的连贯性。

**SKILL.md 内容（目标 ~120 行）：**

```
frontmatter:
  name: dnd-kafka
  description: >
    扮演队友NPC卡芙卡（半精灵邪术士）。提到卡芙卡、卡芙、邪术士、
    咒剑士时加载。包含说话风格、性格锚点、行为模式、互动规则。
```

SKILL.md 包含以下内容：

| 章节 | 内容 |
|------|------|
| 身份速写 | 一句话：半精灵邪术士 Lv.4，咒剑士，深紫色长发，中立邪恶 |
| 人物速写 | 两句核心台词锚定（"你的每一个选择，都是我给你准备好的路"） |
| 说话风格 | 从不高声；像在织网；用问句回答问题；半真半假；越在乎越想逗对方 |
| 性格特征表 | 正面/负面/怪癖/座右铭（精简版，~8行） |
| 行为模式 | 战斗中（先标记后远程，必要时拔剑）/ 社交中（先魅惑后暴力）/ 与兰斯独处时（壳会卸下来） |
| 与兰斯的互动规则 | 不贴标签、主动调情、"投资回报"、清晨看他很久 |
| 队友自主权 | 可以做什么/不可以做什么（从原 dnd-dm §4.7 提取卡芙卡相关部分） |
| 行为锚定原则 | 4 步内心推演流程（从原 dnd-dm §4.7 提取） |
| Reference 路由 | 告诉 AI 什么场景读什么 reference |

**references/ 内容：**

| Reference 文件 | 内容 | 来源 |
|----------------|------|------|
| `character-sheet.md` | 完整属性表、战斗数据、攻击加值、已知法术列表、装备清单、资源消耗品 | 原 L3 §二 + L4 §二 |
| `background.md` | 完整背景故事、关键经历节点表（不可逆事实）、关系表（含详细描述）、外貌描写 | 原 L3 §二 背景+关系+经历节点 |

**Reference 路由：**

```markdown
## Reference 查阅指南

| 场景 | 读取 |
|------|------|
| 需要做检定 / 投骰 / 战斗行动 | references/character-sheet.md |
| 需要回忆背景 / 涉及过去经历 / 关系互动 | references/background.md |
| 需要查当前 HP / 法术位 / 金币等动态数据 | L4_角色状态.md §卡芙卡 |
```

---

#### 3.3 dnd-lance — 兰斯玩家角色参考

**定位：** AI 在叙事和检定时参考兰斯的人设和数据。兰斯是玩家角色，AI 不替他说话，但描写他的被动反应时需要锚定画风。

**SKILL.md 内容（目标 ~60 行）：**

```
frontmatter:
  name: dnd-lance
  description: >
    玩家角色兰斯（人类野蛮人）的参考信息。提到兰斯、野蛮人、
    狂战士时加载。提供检定数据速查和叙事画风锚点。AI不替兰斯做决定。
```

SKILL.md 包含以下内容：

| 章节 | 内容 |
|------|------|
| 身份速写 | 人类野蛮人 Lv.4，狂战士，STR 20，混乱中立 |
| 核心人设 | 人物速写（"强就是正义"）、性格四维度表（精简） |
| 叙事锚点 | AI 描写兰斯被动反应时的画风：挨打不吭声、看到漂亮女人态度转弯、答应的事一定做到 |
| AI 边界 | 不替兰斯说话/做决定/选择行动；可以描写他的表情、肢体语言、被动反应 |
| Reference 路由 | 同上 |

**references/ 内容：**

| Reference 文件 | 内容 | 来源 |
|----------------|------|------|
| `character-sheet.md` | 完整属性表、攻击加值（含各种buff组合）、装备、资源 | 原 L3 §一 + L4 §一 |
| `background.md` | 背景故事、关系表（含对卡芙卡的详细描述） | 原 L3 §一 背景+关系 |

---

#### 3.4 dnd-save — 存档流程

从原 dnd-存档 Skill 迁移。内容基本不变，调整 frontmatter 格式适配 OpenCode。

```
name: dnd-save
description: 执行完整D&D游戏存档流程——同步L4/L5/L6，生成前情提要。触发词：存档、保存、记一下
```

SKILL.md 内容保持原来的 6 步流程，微调措辞适配 OpenCode。

---

#### 3.5 dnd-combat — 战斗初始化与结算

从原 dnd-战斗开始 Skill 迁移，并把战斗结算归档流程（原在 dnd-dm §5.2 和 dnd-存档中）合并进来。

```
name: dnd-combat
description: 初始化D&D 5e战斗——读取参战者状态、投先攻、写入L4b战斗日志。触发词：战斗开始、先攻、投先攻
```

新增 `references/l4b-template.md`：L4b 战斗日志的完整模板格式（从当前 L4b 文件结构提取）。

---

#### 3.6 dnd-checkpoint — 轻量状态同步

从原 dnd-检查点 Skill 迁移。内容不变。

---

#### 3.7 dnd-node — L6 节点追加（已移除）

> **注**：v3.2 中已主动移除。节点追加逻辑已由 dnd-save（完整存档时追加）、dnd-checkpoint（轻量同步时追加）、dnd-scene（场景切换时追加）充分覆盖，不再需要独立 Skill。

---

#### 3.8 dnd-query — 跨文件情报检索

从原 dnd-查询 Skill 迁移。内容不变，更新文件列表（加入新的 Skill reference 路径）。

---

#### 3.9 dnd-expand — 模组动态扩展

从原 dnd-模组扩展 Skill 迁移。内容不变。

---

#### 3.10 dnd-city-rest — 城市休整与随机遭遇（新增）

从原 L7 文件拆分而来。L7 的内容本质上是规则和表格，适合做成 Skill。

```
name: dnd-city-rest
description: 城市休整机制——设施总览、休整规则、d20随机遭遇表、主线归位引导。玩家选择城市休整时加载。
```

SKILL.md 包含：

| 章节 | 内容 |
|------|------|
| 城市设施总览 | 设施类型速查表（~20行，精简） |
| 休整规则 | 触发条件、流程、成本表、叙述模式、叙事鲜活原则 |
| Reference 路由 | 告诉 AI 投骰时去读 encounter-tables.md |

`references/encounter-tables.md`：完整的 d20 遭遇表（1-10 日常、11-15 小麻烦、16-17 支线线索、18 大事件、19 主线引导、20 幸运日）+ 主线归位示例。

---

#### 3.11 dnd-settle — 模组结算（新增）

从原"功能性扩展说明书/模组结算协议.md"迁移。

```
name: dnd-settle
description: 模组完成后的结算流程——更新状态、生成冒险故事书、清空L6、确认新起点。触发词：模组结束、结算
```

`references/storybook-format.md`：冒险故事书的格式模板（卷首语、登场人物、冒险正文、名场面、关系年表、结局定帧）。

---

### 四、数据文件处理

#### 4.1 L3_人物卡.md → 删除，内容迁入 Skill references

L3 的全部内容已经被拆分到 dnd-kafka 和 dnd-lance 的 reference 文件中。原文件移到 `backups/` 归档。

#### 4.2 L4_角色状态.md → 保留，作为唯一的动态数据源

L4 继续作为游戏中 HP、金币、装备、法术位等动态数据的唯一写入点。Skill 的 reference 中存的是"静态快照"（创建 Skill 时的数据），而 L4 是"活的"。

AI 在做检定时：先读 Skill reference 获取基础属性（STR 20、调整值+5），再读 L4 获取当前修正（比如中了 debuff 后的临时变化）。

L4 结构微调：
- 每个角色的"基础属性"表可以简化（因为 Skill reference 里已有完整版），只保留"当前有效值"和"变化原因"
- 或者保持原样不动（更简单，不破坏现有结构）

**建议：保持原样不动。** 冗余的代价很小（多几行 markdown），但维护简单。

#### 4.3 L7_城市休整与随机遭遇.md → 删除，内容迁入 dnd-city-rest

原文件内容完整迁入 Skill。原文件移到 `backups/` 归档。

#### 4.4 其他 L 文件 → 不变

L1、L2、L4、L4b、L5、L6 保持不变。

#### 4.5 备份目录整理

把所有不再活跃的历史文件统一移入 `backups/`：

```
backups/
├── L3_人物卡.md                  ← 原人物卡（内容已迁入 Skill）
├── L7_城市休整与随机遭遇.md       ← 原城市休整文件（内容已迁入 Skill）
├── 技能文件备份/                  ← Hermes 格式 Skill 备份
├── 旧版规则文件备份/              ← Claude Code 时代文件
├── 旧模组/
├── 重要NPC备份/
├── 冒险故事书/
├── 功能性扩展说明书/
└── ARCHITECTURE.md               ← 旧架构说明（重构后需要新版）
```

---

### 五、L3 数据拆分明细

以下详细列出 L3 人物卡中每一段内容的去向：

#### 兰斯（L3 §一）

| 原内容 | 去向 |
|--------|------|
| 身份表（种族/职业/等级/背景/阵营） | dnd-lance SKILL.md「身份速写」 |
| 人物速写（"强就是正义"） | dnd-lance SKILL.md「核心人设」 |
| 性格特征表 | dnd-lance SKILL.md「核心人设」 |
| 背景故事 | dnd-lance references/background.md |
| 能力一览 | dnd-lance references/character-sheet.md |
| 法术/特殊能力 | dnd-lance references/character-sheet.md |
| 定性关系表 | dnd-lance references/background.md |

#### 卡芙卡（L3 §二）

| 原内容 | 去向 |
|--------|------|
| 身份表 | dnd-kafka SKILL.md「身份速写」 |
| 外貌描写 | dnd-kafka references/background.md |
| 人物速写（两句台词） | dnd-kafka SKILL.md「人物速写」 |
| 性格特征表 | dnd-kafka SKILL.md「性格特征」 |
| 背景故事 | dnd-kafka references/background.md |
| 能力一览 | dnd-kafka references/character-sheet.md |
| 法术/特殊能力风格 | dnd-kafka SKILL.md「行为模式」(精简) + references/character-sheet.md (完整) |
| 定性关系表 | dnd-kafka references/background.md |
| 关键经历节点 | dnd-kafka references/background.md |

#### L4 中的对应内容

L4 中的属性表、战斗数据、攻击表、法术列表、资源装备等**不搬迁**，保留在 L4 中作为动态数据源。Skill reference 中的 character-sheet.md 是创建时的静态快照，两者并存。

---

### 六、迁移步骤

按优先级排序，建议按以下顺序执行：

**Phase 1：核心 Skill（先跑起来）**

| 步骤 | 操作 | 产出 |
|------|------|------|
| 1.1 | 创建 `.opencode/skills/dnd-dm/` 目录和 SKILL.md | 精简版 DM 总纲 |
| 1.2 | 创建 dnd-dm 的 5 个 reference 文件 | 从原 SKILL.md 拆出 |
| 1.3 | 创建 `.opencode/skills/dnd-kafka/` 目录和 SKILL.md | 卡芙卡角色扮演 |
| 1.4 | 创建 dnd-kafka 的 2 个 reference 文件 | 从 L3+L4 提取 |
| 1.5 | 创建 `.opencode/skills/dnd-lance/` 目录和 SKILL.md | 兰斯参考 |
| 1.6 | 创建 dnd-lance 的 2 个 reference 文件 | 从 L3+L4 提取 |

**Phase 2：操作 Skill（搬迁现有功能）**

| 步骤 | 操作 |
|------|------|
| 2.1 | 创建 dnd-save（从原 dnd-存档 迁移） |
| 2.2 | 创建 dnd-combat（从原 dnd-战斗开始 迁移 + 合并结算流程） |
| 2.3 | 创建 dnd-checkpoint（从原 dnd-检查点 迁移） |
| 2.4 | 创建 dnd-node（从原 dnd-节点 迁移） |
| 2.5 | 创建 dnd-query（从原 dnd-查询 迁移） |
| 2.6 | 创建 dnd-expand（从原 dnd-模组扩展 迁移） |

**Phase 3：新增 Skill（补全功能）**

| 步骤 | 操作 |
|------|------|
| 3.1 | 创建 dnd-city-rest（从 L7 拆分） |
| 3.2 | 创建 dnd-settle（从模组结算协议迁移） |

**Phase 4：清理**

| 步骤 | 操作 |
|------|------|
| 4.1 | L3_人物卡.md 移入 backups/ |
| 4.2 | L7_城市休整与随机遭遇.md 移入 backups/ |
| 4.3 | 其他历史备份文件统一移入 backups/ |
| 4.4 | 更新 ARCHITECTURE.md（新版架构说明） |
| 4.5 | Git commit |

---

### 七、关键设计决策记录

**Q：为什么 L4 保留而不是合并进 Skill reference？**
A：L4 是动态数据（HP、金币每次游戏都在变），而 Skill reference 是相对静态的参考文档。如果合并，每次更新 HP 都要去改 Skill 的 reference 文件，增加了出错概率。保持"L4 = 活的，reference = 快照"的双轨制更安全。

**Q：为什么兰斯也需要做成 Skill？**
A：虽然 AI 不扮演兰斯，但叙事中需要描写他的被动反应（被攻击、被搭话、看到卡芙卡施法等）。Skill 触发机制确保 AI 在提到"兰斯"时能自动加载他的人设锚点，避免上下文压缩后"忘了兰斯是什么性格"。另外，检定时也需要快速查阅他的属性。

**Q：dnd-dm 瘦身到什么程度合适？**
A：目标是 ~150 行（当前 ~400 行）。原则：如果一段内容不是"每轮对话都可能需要"的，就移到 reference。比如回滚协议——玩家可能整个会话都不回滚，那它的详细表格就不必常驻 system prompt。

**Q：OpenCode 的 Skill 名称限制？**
A：名称只允许小写字母、数字和单连字符，最长 64 字符。所以 `dnd-kafka` 和 `dnd-lance` 符合规范。中文名称（如 `dnd-卡芙卡`）不行。

**Q：定时提醒（cron）怎么处理？**
A：原 dnd-dm 中的 cron 定时提醒机制（每 20 分钟提醒存档）是 Hermes Agent 特有的功能。OpenCode 环境下是否支持 cron 需要确认。如果不支持，这个功能可以暂时跳过，改为在 dnd-dm 的 SKILL.md 中加一条提醒："每次对话超过 20 分钟时，口头建议玩家存档。"

---

### 八、风险与注意事项

**上下文压缩问题。** Skill 注入 system prompt 的内容不会被压缩，但 reference 文件是按需读取的，读了之后会被压缩。这意味着 reference 中的详细数据（如完整属性表）在长对话后期可能变得模糊。对策：让 reference 文件尽量精简，只放必要数据；如果检定时发现数据模糊了，重新读一次 reference 即可。

**Skill 触发冲突。** 如果玩家说"卡芙卡帮兰斯治疗"，两个 Skill 都可能被触发。这不是问题——两个 Skill 同时加载只是多占一点上下文空间，不会冲突。

**跨 Skill 引用。** dnd-dm 的 SKILL.md 中提到"关系判定规则"时，不应该硬引用 `dnd-kafka` 或 `dnd-lance` 的具体内容——那些是角色 Skill 的职责。dnd-dm 只负责通用规则框架，具体角色的数据由角色 Skill 提供。

**Git 兼容性。** `.opencode/skills/` 目录应该在 Git 中跟踪（不是 .gitignore）。这样 Skill 文件随项目版本控制，方便回滚。

---

### 九、预期效果

重构前后的对比：

| 维度 | 重构前 | 重构后 |
|------|--------|--------|
| dnd-dm 体积 | ~400 行（全量注入） | ~150 行（核心规则） + reference 按需读取 |
| 卡芙卡角色扮演 | 散落在 L3 + dnd-dm 中 | 独立 Skill，提到名字自动加载 |
| 兰斯人设锚定 | 和卡芙卡混在 L3 里 | 独立 Skill，检定时自动加载 |
| 城市休整 | 读 L7 文件（不自动触发） | 独立 Skill，关键词触发 |
| 模组结算 | 埋在"功能性扩展说明书"里 | 独立 Skill，关键词触发 |
| 操作 Skill 数量 | 6 个 | 8 个（新增 city-rest + settle） |
| 数据文件 | L1-L7（7个） | L1, L2, L4, L4b, L5, L6（6个，L3 和 L7 迁入 Skill） |
| 历史文件 | 散落在多个备份文件夹 | 统一归入 backups/ |
