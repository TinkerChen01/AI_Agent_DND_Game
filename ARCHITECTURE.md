# 兰斯的冒险 — 架构说明（v3.0）

> 本文档记录项目的文件体系与 Skill 架构设计。
> 最后更新：2026-06-08

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

---

## 三、文件体系

### 活跃数据文件（项目根目录）

| 文件 | 用途 | 更新频率 |
|------|------|---------|
| `L1_世界设定.md` | Forgotten Realms 世界观（静态） | 极少 |
| `L2_模组框架.md` | 当前模组结构/NPC/战斗设计 | 跨模组 |
| `L4_角色状态.md` | HP/资源/装备/关系（动态） | 战斗结束/休整/获得物品 |
| `L4b_战斗日志.md` | 战斗中临时文件 | 战斗期间 |
| `L5_世界状态.md` | 场景/时间/flag/势力 | 场景切换/flag变化 |
| `L6_冒险笔记.md` | 叙事记忆/节点/前情提要 | 关键事件/存档/会话结束 |

### 备份目录（Git 保留，AI 无需读取）

`backups/` 包含所有已归档的历史文件：L3、L7、旧版 Skill、旧版规则、旧模组等。

---

## 四、Skill 体系

```
.opencode/skills/
├── dnd-dm/              ← 主 Skill：DM 行为总纲
│   ├── SKILL.md
│   └── references/      ← 5 个按需加载文档
├── dnd-kafka/           ← 角色 Skill：卡芙卡
│   ├── SKILL.md
│   └── references/      ← character-sheet.md + background.md
├── dnd-lance/           ← 角色 Skill：兰斯
│   ├── SKILL.md
│   └── references/      ← character-sheet.md + background.md
├── dnd-save/            ← 存档流程
├── dnd-combat/          ← 战斗初始化 + 结算
│   └── references/      ← L4b 模板
├── dnd-checkpoint/      ← 轻量状态同步
├── dnd-scene/           ← 场景切换自检（地图级转移时调用 checkpoint）
├── dnd-query/           ← 跨文件情报检索
├── dnd-expand/          ← 模组动态扩展
├── dnd-city-rest/       ← 城市休整与随机遭遇
│   └── references/      ← d20 遭遇表
└── dnd-settle/          ← 模组结算
    └── references/      ← 冒险故事书模板
```

### Skill 分类

| 类型 | Skill | 触发方式 |
|------|-------|---------|
| **核心** | dnd-dm | "游戏继续"、跑团、DND、兰斯、卡芙卡、丝线回廊 |
| **角色** | dnd-kafka | 卡芙卡、卡芙、邪术士、咒剑士 |
| **角色** | dnd-lance | 兰斯、野蛮人、狂战士 |
| **操作** | dnd-save | 存档、保存 |
| **操作** | dnd-combat | 战斗开始、先攻、投先攻（不含叙事中的"战斗"一词） |
| **操作** | dnd-checkpoint | 检查点、检查一下 |
| **操作** | dnd-scene | 去、前往、进入、到达、转移到、出发、动身、离开、返回 |
| **操作** | dnd-query | 查询、查一下 |
| **操作** | dnd-expand | 扩展、补充模组 |
| **操作** | dnd-city-rest | 休整、休息几天、城市探索 |
| **操作** | dnd-settle | 模组结束、结算 |

### 设计原则

1. **SKILL.md 只放稳定的核心指令** — 性格锚点、说话风格、行为规则等不随游戏变化的内容
2. **references/ 放详细数据** — 属性表、法术列表、背景故事、操作模板等按需查阅的内容
3. **动态数据留在 L4** — HP/金币/装备等频繁变化的数据以 L4 为唯一写入点
4. **角色 Skill 关键词触发** — 提到角色名字时自动加载，确保角色扮演连贯性

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
AI 读取 L6 → 叙事摘要、前情提要、存档快照
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
