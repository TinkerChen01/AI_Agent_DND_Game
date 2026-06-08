---
name: dnd-节点
description: 按 L6 节点格式快速追加 D&D 冒险笔记节点。自动处理 node_id 生成和会话索引更新。
---

# dnd-节点 — 追加 L6 节点

加载 `dnd-dm` 主 Skill 后使用。

## 用法

以自然语言描述要记录的事件。

## 流程

### 1. 读取最后一个 node_id

读取 `L6_冒险笔记.md` 节点记录部分，找到最后一个 `node_id`：
- 同一会话 → Seq+1（如 S1N6 → S1N7）
- 新会话 → Session+1，Seq 重置为 1（如 S2N1）

### 2. 读取游戏内时间

从上下文或 `L5_世界状态.md` 获取当前日期。

### 3. 格式化节点内容

```markdown
node_id: S{session}N{seq}
type: [类型标签]
title: [标题]
in_game_date: [日期]
summary: |
  2-4 句话概括
key_events:
  - 事件 1
character_changes:
  兰斯: 变化描述
  卡芙卡: 变化描述
loot_acquired:
  - 物品
unlock_flags:
  - flag
dm_notes: 给未来自己的提示
```

类型标签可选值：`剧情进展 | 战斗 | 探索 | 社交 | 角色发展 | 转折 | 商业 | 休整 | 修正`

### 4. 追加到 L6

将格式化后的节点追加到 L6「节点记录」的「实际记录」部分。

### 5. 更新会话索引

更新 L6「会话索引」表（如需要）。
