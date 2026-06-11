---
name: dnd-combat
description: "初始化D&D 5e战斗场景——读取参战者状态、先攻投骰、设置L4b战斗日志。战斗结束后执行结算归档。触发词：战斗开始、先攻、投先攻。"
---

# dnd-combat — 战斗初始化与结算

> 覆盖战斗的完整生命周期：初始化 → 回合管理 → 结算归档。

**DM 纪律**：默念 `dnd-dm/references/dm-rules.md`，不输出。

---

## 一、战斗初始化

### 1. 执行初始化脚本

执行 `python scripts/init_combat.py --battle-name "战斗名" --enemies "敌人1:HP:AC:先攻加值,敌人2:HP:AC:先攻加值"`

脚本自动完成：读取 L4 获取玩家方数据 → 投先攻 → 生成 L4b 战斗日志内容。

AI 将脚本输出的 L4b 内容覆盖写入 `L4b_战斗日志.md`。

### 2. 生成战斗地图

构造战斗场景的 JSON 数据（参考 `dnd-map` Skill 格式），执行：

```bash
python .opencode/skills/dnd-map/scripts/render_map.py --type combat --data 'JSON数据'
```

将地图输出嵌入叙事或 L4b 底部。

### 3. 输出

- 当前场景描写（2-3句）
- 先攻顺序列表
- 战斗地图
- 提示当前回合行动者

### 骰子工具

战斗中需要投骰时，使用 `python scripts/roll_dice.py 表达式`：

- `python scripts/roll_dice.py 1d20+7` — 攻击骰
- `python scripts/roll_dice.py advantage:1d20+7` — 优势骰
- `python scripts/roll_dice.py 2d6+5` — 伤害骰
- `python scripts/roll_dice.py init:1d20+2` — 先攻骰

---

## 二、战斗分级

| 级别 | 判断标准 | 流程 |
|------|---------|------|
| **完整战斗** | Boss 战、主线战斗、玩家主动发起 | 完整流程（初始化→回合→结算），使用 L4b + 战斗地图 |
| **快速战斗** | 随机遭遇、小怪清理、休整日事件 | 简化流程（AI 叙述为主，2-3 次关键检定决定结果），不用 L4b |

---

## 三、回合管理

- 战斗中状态变化仅维护在上下文，不逐轮写文件
- 按 L4b 的「快照刷新触发条件」定期持久化（HP 变化 ≥ 25%、角色倒地、buff 消退、Boss 换阶段、增援入场、每 5 回合）
- 关键转折点（倒地/boss入场/环境剧变）追加到 L4b「关键转折点」
- 每回合更新战斗地图中实体位置，重新渲染地图

---

## 四、结算归档

战斗结束后执行：

1. 从 L4b 提取最终状态 → 更新 `L4_角色状态.md`（HP/消耗/物品变化）
2. 提炼关键事件 → 追加 `L6_冒险笔记.md` 节点（type: 战斗）
3. 清空 `L4b_战斗日志.md`
4. 重新加载 `dnd-dm` Skill（温习模式）
