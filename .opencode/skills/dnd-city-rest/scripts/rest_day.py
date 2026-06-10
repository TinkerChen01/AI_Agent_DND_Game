#!/usr/bin/env python3
"""
dnd-city-rest: 休整日自动化脚本
用法: python rest_day.py --days 3 --quality standard
      python rest_day.py --days 1 --quality luxurious --current-date "翠雨月19日"

功能:
1. 为每天投 d20 决定遭遇类型
2. 计算总费用
3. 输出每天遭遇摘要 + 费用明细 + L4 需要更新的字段
"""

import random
import json
import argparse
import re
import sys
from pathlib import Path

# 确保 Windows 控制台使用 UTF-8 输出
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


# 费用表（每人每天）
COST_TABLE = {
    "meager":    {"sp": 2,  "label": "简陋", "desc": "通铺床位 + 面包麦粥"},
    "standard":  {"sp": 5,  "label": "标准", "desc": "单间 + 一日两餐热食"},
    "comfortable": {"gp": 1, "label": "舒适", "desc": "上好单间 + 三餐 + 热水澡"},
    "luxurious": {"gp_min": 2, "gp_max": 5, "label": "奢华", "desc": "套房 + 精致餐饮 + 各类服务"},
}

# 遭遇表
ENCOUNTER_TABLE = {
    1:  {"category": "日常", "title": "街头偶遇", "desc": "有趣的人（老兵/江湖郎中/迷路商人），聊几句各走各路。"},
    2:  {"category": "日常", "title": "意外之财", "desc": "捡到钱袋（1d10 gp）或淘到好物转手卖，净赚 2d6 gp。", "bonus_gold": True},
    3:  {"category": "日常", "title": "好天气好心情", "desc": "当天所有社交检定 +1 加值。", "effect": "社交+1"},
    4:  {"category": "日常", "title": "美食发现", "desc": "发现极好的小店，获得一枚激励骰（d4）用于下次检定。", "effect": "激励骰d4"},
    5:  {"category": "日常", "title": "街头表演", "desc": "吟游诗人/杂技/老鼓手，驻足观看，大家都在笑。"},
    6:  {"category": "日常", "title": "助人为乐", "desc": "帮路人搬面粉/指路/赶野狗。无物质回报，但心里舒坦。"},
    7:  {"category": "日常", "title": "故人的回响", "desc": "偶然听到熟悉名字的消息。世界在动。"},
    8:  {"category": "日常", "title": "小确幸", "desc": "发现合心意的小东西，花费 1d4 gp。", "extra_cost_gp": True},
    9:  {"category": "日常", "title": "安眠之夜", "desc": "旅店安静，精力充沛。下一天所有豁免检定有优势。", "effect": "次日豁免优势"},
    10: {"category": "日常", "title": "风景独好", "desc": "无意中走到视野极好的位置，看城市屋顶在暮色中展开。"},
    11: {"category": "小麻烦", "title": "有贼！", "desc": "钱包被偷，损失 2d10 gp。DC 13 察觉/调查可追回一半。", "gold_loss": True},
    12: {"category": "小麻烦", "title": "找茬的", "desc": "地痞/醉汉找茬。威吓 DC 10 / 花 2d6 gp 请酒 / 动手。"},
    13: {"category": "小麻烦", "title": "大雨倾盆", "desc": "淋成落汤鸡。避雨时偶遇陌生人，可触发对话或信息。"},
    14: {"category": "小麻烦", "title": "房间问题", "desc": "隔壁太吵/房顶漏水/预订搞错。换房浪费半天，无实质损失。"},
    15: {"category": "小麻烦", "title": "水土不服", "desc": "状态不佳。当天力量/体质相关检定承受劣势。", "effect": "力/体检定劣势"},
    16: {"category": "支线线索", "title": "神秘的委托", "desc": "委托板上措辞奇怪的委托，报酬丰厚但未写明委托人。DM 临场发挥。"},
    17: {"category": "支线线索", "title": "稀罕物件", "desc": "市场中的不寻常物品。DM 选择与当前模组有关联的物件。"},
    18: {"category": "大事件", "title": "大事件/战斗", "desc": "投 d6 决定类型（怪物闯入/街头火并/抢劫/求救/火灾/追捕）。短战斗或紧张对峙。", "d6_subroll": True},
    19: {"category": "主线引导", "title": "主线引导位", "desc": "DM 手动插入将玩家引回主线的遭遇。不自动处理。"},
    20: {"category": "幸运日", "title": "幸运日", "desc": "投 d4 决定（生财有道/贵人相遇/意外之喜/好事成双）。", "d4_subroll": True},
}

BIG_EVENT_D6 = {
    1: "怪物闯入 — 野兽从下水道或城墙缺口闯入",
    2: "街头火并 — 两个帮派当街斗殴",
    3: "抢劫现场 — 店铺被劫，劫匪正逃离",
    4: "求救声 — 小巷深处呼救",
    5: "火灾 — 附近建筑冒浓烟",
    6: "当街追捕 — 卫兵追逃犯，朝你冲来",
}

LUCKY_D4 = {
    1: "生财有道 — 获得 2d10×5 gp",
    2: "贵人相遇 — 遇到对主线有帮助的关键人物",
    3: "意外之喜 — 得到有用消耗品（治疗药水/法术卷轴/特殊弹药）",
    4: "好事成双 — 同一天两件好事",
}


def calc_daily_cost(quality: str, num_people: int = 2) -> dict:
    """计算每日费用"""
    cost = COST_TABLE.get(quality, COST_TABLE["standard"])
    if "gp_min" in cost:
        gp = random.randint(cost["gp_min"], cost["gp_max"])
        return {"gp": gp * num_people, "sp": 0, "label": cost["label"], "per_person_gp": gp}
    elif "gp" in cost:
        return {"gp": cost["gp"] * num_people, "sp": 0, "label": cost["label"], "per_person_gp": cost["gp"]}
    else:
        sp = cost["sp"] * num_people
        return {"gp": 0, "sp": sp, "label": cost["label"], "per_person_sp": cost["sp"]}


def roll_encounter() -> dict:
    """投 d20 决定遭遇"""
    d20 = random.randint(1, 20)
    encounter = ENCOUNTER_TABLE[d20].copy()
    encounter["d20"] = d20

    # 子骰
    if encounter.get("d6_subroll"):
        d6 = random.randint(1, 6)
        encounter["subroll"] = d6
        encounter["subroll_result"] = BIG_EVENT_D6[d6]

    if encounter.get("d4_subroll"):
        d4 = random.randint(1, 4)
        encounter["subroll"] = d4
        encounter["subroll_result"] = LUCKY_D4[d4]

    # 额外金币
    if encounter.get("bonus_gold"):
        if d20 == 2:
            encounter["bonus_gold_amount"] = random.randint(1, 10) + random.randint(1, 6) + random.randint(1, 6)

    if encounter.get("extra_cost_gp"):
        encounter["extra_cost"] = random.randint(1, 4)

    if encounter.get("gold_loss"):
        encounter["gold_lost"] = random.randint(1, 10) + random.randint(1, 10)

    return encounter


def main():
    parser = argparse.ArgumentParser(description="D&D 城市休整自动化")
    parser.add_argument("--days", type=int, default=1, help="休整天数")
    parser.add_argument("--quality", choices=["meager", "standard", "comfortable", "luxurious"],
                        default="standard", help="住宿档次")
    parser.add_argument("--people", type=int, default=2, help="人数")
    parser.add_argument("--current-date", default="", help="当前游戏内日期")
    parser.add_argument("--fast-forward", action="store_true", help="快进模式（简要汇总）")
    args = parser.parse_args()

    days = min(args.days, 7)  # 最多 7 天
    encounters = []
    total_cost = {"gp": 0, "sp": 0}

    for day in range(1, days + 1):
        daily_cost = calc_daily_cost(args.quality, args.people)
        encounter = roll_encounter()

        # 累计费用
        total_cost["gp"] += daily_cost.get("gp", 0)
        total_cost["sp"] += daily_cost.get("sp", 0)

        # 额外费用/收入
        extra = {}
        if encounter.get("extra_cost"):
            extra["extra_expense"] = f"{encounter['extra_cost']} gp"
            total_cost["gp"] += encounter["extra_cost"]
        if encounter.get("bonus_gold_amount"):
            extra["bonus_gold"] = f"{encounter['bonus_gold_amount']} gp"
        if encounter.get("gold_lost"):
            extra["gold_lost"] = f"{encounter['gold_lost']} gp"

        encounters.append({
            "day": day,
            "encounter": encounter,
            "daily_cost": daily_cost,
            "extra": extra,
        })

    # 银币转金币
    extra_gp = total_cost["sp"] // 10
    total_cost["gp"] += extra_gp
    total_cost["sp"] = total_cost["sp"] % 10

    # 格式化输出
    print(f"{'='*50}")
    print(f"  城市休整报告")
    print(f"  休整天数: {days} 天 | 档次: {COST_TABLE[args.quality]['label']} | 人数: {args.people}")
    if args.current_date:
        print(f"  起始日期: {args.current_date}")
    print(f"{'='*50}\n")

    for e in encounters:
        enc = e["encounter"]
        d20 = enc["d20"]
        cat = enc["category"]
        title = enc["title"]
        desc = enc["desc"]
        cost = e["daily_cost"]

        cost_str = ""
        if cost.get("gp"):
            cost_str = f"{cost['gp']} gp"
        elif cost.get("sp"):
            cost_str = f"{cost['sp']} sp"

        print(f"Day {e['day']}: d20={d20} → [{cat}] {title}")
        print(f"  描述: {desc}")
        print(f"  费用: {cost_str}")

        if enc.get("subroll_result"):
            print(f"  子骰: d{'6' if enc.get('d6_subroll') else '4'}={enc['subroll']} → {enc['subroll_result']}")
        if e["extra"].get("extra_expense"):
            print(f"  额外支出: {e['extra']['extra_expense']}")
        if e["extra"].get("bonus_gold"):
            print(f"  额外收入: {e['extra']['bonus_gold']}")
        if e["extra"].get("gold_lost"):
            print(f"  损失: {e['extra']['gold_lost']}")
        if enc.get("effect"):
            print(f"  效果: {enc['effect']}")

        print()

    print(f"{'='*50}")
    print(f"  总费用: {total_cost['gp']} gp {total_cost['sp']} sp")
    print(f"{'='*50}")
    print()

    # L4 更新提示
    print("## L4 更新提示")
    per_person_gp = total_cost["gp"] // args.people if args.people > 0 else total_cost["gp"]
    per_person_sp = total_cost["sp"] // args.people if args.people > 0 else total_cost["sp"]
    print(f"每人分摊: {per_person_gp} gp {per_person_sp} sp")

    # JSON 输出
    print("\n---JSON---")
    output = {
        "days": days,
        "quality": args.quality,
        "people": args.people,
        "encounters": encounters,
        "total_cost": total_cost,
        "per_person_cost": {"gp": per_person_gp, "sp": per_person_sp},
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
