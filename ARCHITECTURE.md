# 兰斯的冒险 — 架构说明（v3.5）

> 本文档记录项目的文件体系与 Skill 架构设计。
> 最后更新：2026-06-10

---

## 一、项目概述

基于 **D&D 5e** 的 AI Agent 单人跑团游戏，使用 **L1-L6 数据文件 + OpenCode Skill 体系** 管理游戏运行。

- 玩家角色：**兰斯**，人类野蛮人（狂战士）Lv.4
- 队友 NPC（AI 扮演）：**卡芙卡**，半精灵邪术士（咒剑士）Lv.4
- 当前模组：**丝线回廊**（短团，单章）
- 目标平台：**OpenCode**

---

## 二、架构演变

| 版本 | 平台 | 核心变化 |
|------|------|---------|
| v1.0 | Claude Code | CLAUDE.md + L0-L7 + `.claude/skills/` |
| v2.0 | Hermes Agent | CLAUDE.md + L0 合并为 `dnd-dm` Skill，迁移至 `~/.hermes/skills/` |
| **v3.0** | **OpenCode** | L3/L7 拆分为角色 Skill + 城市休整 Skill，dnd-dm 瘦身，11 个 Skill 体系 |

### v3.0 核心变化

- **L3 人物卡删除** → 拆分为 `dnd-kafka`（卡芙卡角色扮演）和 `dnd-lance`（兰斯参考）两个独立 Skill
- **L7 城市休整删除** → 迁入 `dnd-city-rest` Skill
- **dnd-dm 瘦身** → 从 ~400 行精简至 ~230 行，详细规则移入 references/
- **新增 Skill** → `dnd-city-rest`（城市休整）、`dnd-settle`（模组结算）
- **文件归档** → 所有历史文件统一移入 `backups/`

### v3.1 核心变化

- **角色 Skill 重构** → SKILL.md 精简至 ~20 行核心行为锚点（身份/说话风格/性格/行为推演/AI边界），深度内容全部迁入 `references/background.md`
- **Token 优化** → 每次触发注入量从 ~126 行降至 ~20 行（-85%），角色声音锚点每轮常驻，深度知识按需查阅
- **设计原则** → 示例台词从 SKILL.md 移除（防止 AI 套用），改为抽象风格规则；完整示例保留在 references 供深度叙事时查阅

### v3.2 核心变化

- **Script 注入** → 8 个 Skill 新增 `scripts/` 目录，将结构化操作（检索/骰子/状态同步/地图渲染等）从 AI 指令变为可执行脚本，不消耗 token、100% 确定性
- **新增 dnd-map Skill** → ASCII 战术地图系统（战斗地图/楼层总览/区域探索），与 dnd-combat 和 dnd-scene 联动
- **新增氛围骰子系统** → dnd-dm 新增 `references/atmosphere-tables.md`，d6 感官描写表按场景分类
- **关系追踪自动化** → dnd-dm 新增 `scripts/relationship_check.py`，自动计算 trend 累计和跨档
- **战斗分级** → dnd-combat 新增"快速战斗"模式，小遭遇不再需要完整 L4b 流程
- **安全提醒** → 角色 Skill 的 character-sheet.md 增加"⚠ 快照，以 L4 为准"提醒
- **dnd-node 移除** → 节点追加逻辑已由 dnd-save / dnd-checkpoint / dnd-scene 充分覆盖，不再需要独立 Skill

### v3.3 核心变化

- **模组标准化模板** → 定义 12 节结构（§〇速查索引 → §九叙事锚点），所有模组必须遵循，AI 通过 §〇 精准定位内容（预估 token 节省 70-80%）
- **新增 dnd-module-gen Skill** → 从素材库抽取元素，按标准模板自动生成新模组。包含生成骨架脚本、验证脚本、设计指南
- **L2 重构** → 丝线回廊 L2 重构为标准化格式：新增 §〇 速查索引、floorplan JSON、三幕结构标注、失败安全网、完成条件、L5 初始化模板
- **Skill 联动升级** → dnd-map 改为从 L2 §〇+§二 定位地图数据；dnd-expand 遵循模板格式扩展；dnd-settle 集成 dnd-module-gen 生成新模组

### v3.5 核心变化（冗余精简 + 健壮性增强）

- **L5 瘦身** → 移除 §一 战役总览（与 L0 重复）；§十 因果链迁出至 `dnd-dm/references/causal-chain.md`（仅在模组生成/结算时按需加载，日常不占 token）；Plot Flags 添加 snake_case 命名规范，旧模组 flag 归档至独立表；章节重编号（§一~§八）
- **L6 精简** → 前情提要从三层（叙事摘要+完整回顾+存档快照）合并为两层（完整回顾+存档快照），消除信息冗余，每次启动节省约 200 tokens
- **L1 分区加载** → 标注核心常驻区（§一 世界概况，约 20 行）和扩展按需区（§二~§八），会话启动时仅加载核心区，扩展区按主题触发读取
- **L4 攻击表精简** → 移除所有伤害变体行（狂暴/鲁莽+巨武），仅保留当前装备基础数据，变体由 roll_dice.py 实时计算
- **L4b 快照规则强化** → 战斗快照从"超过 10 回合每 3 回合"改为事件驱动触发（HP 变化 ≥ 25%、角色倒地、buff 消退、Boss 换阶段、增援入场）+ 每 5 回合定期刷新
- **分级会话启动** → dnd-dm 新增完整启动和轻量启动两种模式，中断恢复时不再全量加载五个文件
- **DM 纪律集中化** → 创建 `dnd-dm/references/dm-rules.md` 共享规则，dnd-combat/dnd-save/dnd-checkpoint 移除各自重复的纪律文本，改为引用共享 reference
- **dnd-scene 收窄** → 明确触发/不触发条件（同房间位置调整不触发、同楼层相邻房间不触发除非未探索），局部移动保留环境栈做增量修改而非重建
- **dnd-expand/dnd-module-gen 边界** → 添加五维度判断表（空间范围/叙事范围/内容量/NPC/时间线），灰色地带给出过渡方案
- **dnd-save 关系强制检查** → 存档时如果会话中发生过关系相关互动，必须执行 relationship_check.py 确认 trend 状态
- **新增 reference 文件** → `causal-chain.md`（因果链追踪）、`dm-rules.md`（DM 通用纪律）

---

## 三、文件体系

### 活跃数据文件（项目根目录）

| 文件 | 用途 | 更新频率 |
|------|------|---------|
| `L0_战役总览.md` | 战役进度概览（脚本生成） | 每次存档 |
| `L1_世界设定.md` | Forgotten Realms 世界观（静态） | 极少 |
| `L2_模组框架.md` | 当前模组结构/NPC/战斗设计 | 跨模组 |
| `L4_角色状态.md` | HP/资源/装备/关系（动态） | 战斗结束/休整/获得物品 |
| `L4b_战斗日志.md` | 战斗中临时文件 | 战斗期间 |
| `L5_世界状态.md` | 场景/时间/flag/势力/环境栈/情绪节拍 | 场景切换/flag变化 |
| `L6_冒险笔记.md` | 叙事记忆/节点/前情提要 | 关键事件/存档/会话结束 |

### 备份目录（Git 保留，AI 无需读取）

`backups/` 包含所有已归档的历史文件：L3、L7、旧版 Skill、旧版规则、旧模组等。

---

## 四、Skill 体系

```
.opencode/skills/
├── dnd-dm/              ← 主 Skill：DM 行为总纲
│   ├── SKILL.md
│   ├── references/      ← 9 个按需加载文档（含 atmosphere-tables.md, gut-check.md, slow-motion.md, dm-rules.md, causal-chain.md）
│   └── scripts/         ← session_startup.py + relationship_check.py + generate_overview.py
├── dnd-kafka/           ← 角色 Skill：卡芙卡（含私下低语机制）
│   ├── SKILL.md
│   └── references/      ← character-sheet.md + background.md
├── dnd-lance/           ← 角色 Skill：兰斯
│   ├── SKILL.md
│   └── references/      ← character-sheet.md + background.md
├── dnd-save/            ← 存档流程
│   └── scripts/         ← sync_state.py（含一致性检查）
├── dnd-combat/          ← 战斗初始化 + 结算
│   ├── references/      ← L4b 模板
│   └── scripts/         ← roll_dice.py（含暴击/大失败标记）+ init_combat.py
├── dnd-checkpoint/      ← 轻量状态同步
├── dnd-scene/           ← 场景切换自检 + 地图联动 + 环境栈初始化
├── dnd-query/           ← 跨文件情报检索
│   └── scripts/         ← query.py
├── dnd-expand/          ← 模组动态扩展
├── dnd-city-rest/       ← 城市休整与随机遭遇
│   ├── references/      ← d20 遭遇表
│   └── scripts/         ← rest_day.py
├── dnd-settle/          ← 模组结算
│   ├── references/      ← 冒险故事书模板
│   └── scripts/         ← generate_storybook.py
├── dnd-module-gen/      ← 新模组生成（v3.3）
│   ├── SKILL.md
│   ├── references/      ← module-template.md + design-guide.md
│   └── scripts/         ← validate_module.py + generate_skeleton.py
└── dnd-map/             ← 战术地图系统（v3.2）
    ├── SKILL.md
    ├── references/      ← map-symbols.md
    └── scripts/         ← render_map.py
```

### Skill 分类

| 类型 | Skill | 触发方式 |
|------|-------|---------|
| **核心** | dnd-dm | "游戏继续"、跑团、DND、兰斯、卡芙卡、丝线回廊 |
| **角色** | dnd-kafka | 卡芙卡、卡芙、邪术士、咒剑士、紫发女人 |
| **角色** | dnd-lance | 兰斯、野蛮人、狂战士 |
| **操作** | dnd-save | 存档、保存 |
| **操作** | dnd-combat | 战斗开始、先攻、投先攻（不含叙事中的"战斗"一词） |
| **操作** | dnd-checkpoint | 检查点、检查一下 |
| **操作** | dnd-scene | 去、前往、进入、到达、转移到、出发、动身、离开、返回 |
| **操作** | dnd-query | 查询、查一下 |
| **操作** | dnd-expand | 扩展、补充模组 |
| **操作** | dnd-city-rest | 休整、休息几天、城市探索 |
| **操作** | dnd-settle | 模组结束、结算 |
| **操作** | dnd-module-gen | 新模组、生成模组、下一个冒险 |
| **操作** | dnd-map | 地图、看看周围、位置、战术地图 |

### 设计原则

1. **SKILL.md 只放稳定的核心指令** — 角色 Skill 精简至 ~20 行行为锚点，深度内容移入 references/
2. **references/ 放详细数据** — 属性表、法术列表、背景故事、说话风格示例、操作模板等按需查阅的内容
3. **scripts/ 放可执行脚本** — 结构化操作（检索/骰子/状态同步/地图渲染）由脚本执行，不消耗 token，100% 确定性
4. **动态数据留在 L4** — HP/金币/装备等频繁变化的数据以 L4 为唯一写入点
5. **角色 Skill 关键词触发** — 提到角色名字时自动加载行为锚点，确保角色扮演连贯性
6. **示例台词不放 SKILL.md** — 防止 AI 反复套用，改为抽象风格规则；完整示例保留在 references 供深度叙事查阅

---

## 五、游戏运行机制

### 启动流程

```
OpenCode 加载项目
  │
  ▼
dnd-dm Skill 注入（核心规则常驻）
  │
  ▼
AI 读取 L6 → 过往冒险摘要、前情提要（完整回顾+存档快照）、最近节点
  │
  ▼
AI 读取 L1 → L2 → L4 → L5
  │
  ▼
角色 Skill 自动触发（提到卡芙卡/兰斯时）
  │
  ▼
合成战役梗概 → 从存档快照直接接续叙事
```

### Skill 调用链

```
游戏过程中触发事件
  │
  ├─ 提到卡芙卡 → dnd-kafka 自动加载（角色扮演）
  ├─ 提到兰斯 → dnd-lance 自动加载（数据参考）
  ├─ 战斗开始 → dnd-combat（初始化 L4b）
  ├─ 玩家说"存档" → dnd-save（完整存档）
  ├─ 玩家说"检查点" → dnd-checkpoint（轻量同步）
  ├─ 需要记录事件 → dnd-scene（追加 L6）
  ├─ 玩家查询信息 → dnd-query（跨文件检索）
  ├─ 玩家想去未设计区域 → dnd-expand（模组扩展）
  ├─ 玩家选择城市休整 → dnd-city-rest（d20 遭遇）
  └─ 模组完成 → dnd-settle（结算归档）
```

---

## 六、快速上手

```bash
# 1. 在 OpenCode 中打开项目目录
opencode

# 2. 游戏会自动加载 dnd-dm Skill（或通过关键词触发）

# 3. 开始游戏
游戏继续
```

---

## 七、变更记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-05-18 | 2.0 | 从 Claude Code 迁移至 Hermes Agent |
| 2026-06-08 | 3.0 | 迁移至 OpenCode。L3/L7 拆分为角色 Skill + 城市休整 Skill。dnd-dm 瘦身（~400→~230行）。新增 dnd-city-rest 和 dnd-settle。历史文件统一归档至 backups/。 |
| 2026-06-08 | 3.1 | 角色 Skill 重构：SKILL.md 精简至 ~20 行核心行为锚点，深度内容（外貌/性格详解/说话风格示例/行为模式/关系规则）迁入 references/background.md。每次触发 token 消耗降低 ~85%。 |
| 2026-06-10 | 3.2 | Script 注入：8 个 Skill 新增 scripts/ 目录（query.py/session_startup.py/roll_dice.py/init_combat.py/rest_day.py/sync_state.py/generate_storybook.py/render_map.py/relationship_check.py）。新增 dnd-map Skill（ASCII 战术地图系统）。新增氛围骰子系统。战斗分级（完整/快速）。关系追踪自动化。dnd-node 移除（职责由其他 Skill 覆盖）。 |
| 2026-06-10 | 3.3 | 模组标准化模板（§〇速查索引→§九叙事锚点）。新增 dnd-module-gen Skill。L2 重构为标准化格式。Skill 联动升级。 |
| 2026-06-10 | 3.4 | **叙事增强 + 脚本健壮性 + 玩家体验**：① L6 节点增加 HTML 注释分隔符（机器可读）② roll_dice.py 暴击/大失败自动标记 ③ dnd-dm SKILL.md 瘦身至 172 行 ④ 新增 Gut Check（直觉骰）规则 ⑤ 新增慢动作时刻叙事规则 ⑥ sync_state.py 增加 AC/XP/Buff 一致性检查 ⑦ 新增 L0_战役总览（generate_overview.py 自动生成）⑧ 卡芙卡私下低语机制 ⑨ L5 环境状态栈 ⑩ L5 情绪节拍追踪器 |
| 2026-06-11 | 3.5 | **冗余精简 + 健壮性增强**：① L5 移除重复战役总览、因果链迁出至 reference（日常不占 token）、Plot Flags 添加 snake_case 命名规范+旧 flag 归档 ② L6 前情提要从三层合并为两层 ③ L1 分区加载（核心常驻区+扩展按需区）④ L4 攻击表精简（变体由脚本实时计算）⑤ L4b 快照规则改为事件驱动+定期刷新 ⑥ dnd-dm 分级会话启动（完整/轻量）⑦ DM 纪律集中化为共享 reference ⑧ dnd-scene 收窄触发范围 ⑨ dnd-expand/dnd-module-gen 边界澄清 ⑩ dnd-save 关系强制检查 |
