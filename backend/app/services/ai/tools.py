"""AI 查询工具 — 关键词匹配自动调用游戏 API，数据摘要后注入上下文"""
import asyncio
import logging

logger = logging.getLogger("qpet.ai.tools")

TOOLS = [
    # Combat & Tower
    {"name": "tower", "keywords": ["爬塔", "塔", "斗神塔", "楼层", "第几层", "剩余次数"],
     "endpoint": "/api/qpet/tower/status", "desc": "斗神塔状态"},
    {"name": "gangStatus", "keywords": ["帮派状态", "帮派加成", "帮派技能", "守护神", "贡献度", "帮贡", "我的帮派", "我在的帮派", "帮派信息"],
     "endpoint": "/api/qpet/social/gang/status", "desc": "帮派完整状态（成员/技能/守护神/贡献）"},
    {"name": "gangBoss", "keywords": ["帮派BOSS", "帮派boss", "帮战", "BOSS战", "羊魔王", "乐斗教主", "乐斗帅帅", "乐斗姜公", "月璇姐姐"],
     "endpoint": "/api/qpet/social/gang/boss/status", "desc": "帮派BOSS状态（含今日次数和好感度）"},
    {"name": "gangList", "keywords": ["帮派列表", "所有帮派", "有哪些帮派", "找个帮派", "加入帮派", "帮会排名"],
     "endpoint": "/api/qpet/social/gang/list", "desc": "全服帮派列表"},
    {"name": "friends", "keywords": ["好友", "好友列表", "可挑战", "对手"],
     "endpoint": "/api/qpet/battle/friends", "desc": "可挑战好友"},

    # Inventory & Equipment
    {"name": "inventory", "keywords": ["背包", "物品", "道具", "有几个", "还有多少", "数量"],
     "endpoint": "/api/qpet/inventory", "desc": "背包物品"},
    {"name": "equipment", "keywords": ["装备", "穿了什么", "头盔", "护甲", "护腕", "腰带", "鞋子", "项链", "穿戴"],
     "endpoint": "/api/qpet/equipment", "desc": "装备列表"},
    {"name": "beads", "keywords": ["魂珠", "魂珠背包", "镶嵌", "珠子"],
     "endpoint": "/api/qpet/beads/inventory", "desc": "魂珠背包"},

    # Daily & Status
    {"name": "checkin", "keywords": ["签到", "签到状态", "签了没", "领取"],
     "endpoint": "/api/user/checkin", "desc": "签到状态"},
    {"name": "adStamina", "keywords": ["广告体力", "广告", "体力", "体力广告", "stamina"],
     "endpoint": "/api/qpet/ad-stamina/status", "desc": "广告体力状态"},
    {"name": "profile", "keywords": ["个人资料", "资料", "用户信息", "经验", "等级"],
     "endpoint": "/api/user/profile", "desc": "用户资料"},

    # Shop & Auction
    {"name": "shop", "keywords": ["商店", "商店状态", "价格", "买什么", "有什么卖", "商品"],
     "endpoint": "/api/qpet/shop/status", "desc": "商店状态"},
    {"name": "auction", "keywords": ["拍卖", "拍卖行", "拍卖品", "上架", "竞拍"],
     "endpoint": "/api/qpet/auction/listings", "desc": "拍卖列表"},

    # Class & Skills
    {"name": "class", "keywords": ["职业信息", "职业", "觉醒", "技能树", "SP", "技能点"],
     "endpoint": "/api/qpet/class/info", "desc": "职业信息"},

    # Farm
    {"name": "farm", "keywords": ["农场", "地块", "作物", "收获", "播种", "偷菜", "种地", "种什么", "浇水", "成熟", "图鉴", "收集"],
     "endpoint": "/api/farm", "desc": "农场完整状态"},
    {"name": "farmAd", "keywords": ["农场广告", "农场奖励", "广告奖励"],
     "endpoint": "/api/farm/ad-bonus/status", "desc": "农场广告奖励状态"},
    {"name": "communityAd", "keywords": ["社区广告", "博客广告", "社区奖励", "帖子广告"],
     "endpoint": "/api/community/ad-reward/status", "desc": "社区广告奖励状态"},

    # Furnace
    {"name": "furnace", "keywords": ["熔炉", "失落熔炉", "贴膜", "炉心余烬", "阿戈隆", "深渊票", "炽炉工坊", "竞速榜"],
     "endpoint": "/api/qpet/furnace/shop", "desc": "失落熔炉商店（贴膜/余烬/开放状态）"},

    # Territory & Misc
    {"name": "territory", "keywords": ["地盘", "占领", "抢地盘", "地盘战", "开心小镇", "阳光海岸", "云端之城", "龙脊山巅"],
     "endpoint": "/api/qpet/territory", "desc": "地盘占领状态"},
    {"name": "chest", "keywords": ["宝箱", "典藏宝箱", "开宝箱", "开箱"],
     "endpoint": "/api/qpet/collection-chest", "desc": "典藏宝箱状态"},
    {"name": "enhance", "keywords": ["强化", "锻造石", "增幅", "保护券", "强化装备"],
     "endpoint": "/api/qpet/equipment-enhance", "desc": "装备强化页面"},
]


def match_tools(question: str) -> list[dict]:
    """关键词匹配，最多返回 4 个"""
    q = question.lower()
    matched = [t for t in TOOLS if any(k in q for k in t["keywords"])]
    return matched[:4]


async def execute_tool(tool: dict, client) -> dict | None:
    """调 QPetClient 对应方法获取数据"""
    name = tool["name"]
    try:
        match name:
            case "tower":             result = await client.get_tower_status()
            case "gangStatus":        result = await client.get_gang_status()
            case "gangBoss":          result = await client.get_gang_boss_status()
            case "gangList":
                raw = await client.get_gang_list()
                result = {"success": raw.get("success"), "data": _build_gang_list_summary(raw.get("data", []))} if raw.get("success") else raw
            case "friends":           result = await client.get_fightable_friends()
            case "inventory":
                raw = await client.get_inventory()
                result = {"success": raw.get("success"), "data": _build_inv_summary(raw.get("data", []))} if raw.get("success") else raw
            case "equipment":
                raw = await client.get_equipment()
                result = {"success": raw.get("success"), "data": _build_equip_summary(raw.get("data", []))} if raw.get("success") else raw
            case "beads":             result = await client.get_bead_inventory()
            case "checkin":           result = await client.get_checkin_info()
            case "adStamina":         result = await client.get_ad_stamina_status()
            case "profile":           result = await client.get_profile()
            case "shop":              result = await client.get_shop_status()
            case "auction":
                raw = await client.get_auction_listings()
                result = {"success": raw.get("success"), "data": _build_auction_summary(raw.get("data", []))} if raw.get("success") else raw
            case "class":             result = await client.get_class_info()
            case "farm":
                raw = await client.farm_get_status()
                result = {"success": raw.get("success"), "data": _build_farm_summary(raw.get("data", {}))} if raw.get("success") else raw
            case "farmAd":           result = await client.farm_get_ad_status()
            case "communityAd":      result = await client.community_get_ad_status()
            case "furnace":          result = await client.get_furnace_shop()
            case "territory":        result = await client.get_territory()
            case "chest":            result = await client.get_exhibition_chest()
            case "enhance":          result = await client.get_equipment_enhance()
            case _:                  return None

        if result and result.get("success") and result.get("data") is not None:
            return {"tool": name, "endpoint": tool["endpoint"], "data": result["data"]}
    except Exception as e:
        logger.debug(f"工具 {name} 查询失败: {e}")
    return None


async def run_tools(question: str, client) -> list[dict]:
    """匹配 → 并行执行 → 返回结果列表"""
    matched = match_tools(question)
    if not matched:
        return []

    results = await asyncio.gather(
        *(execute_tool(t, client) for t in matched),
        return_exceptions=True,
    )
    return [r for r in results if r and not isinstance(r, Exception)]


# ── 摘要函数（压缩大体积响应，方便 AI 理解）──

def _build_farm_summary(data: dict) -> dict:
    if not isinstance(data, dict):
        return {}
    coll = data.get("collection", []) or []
    cfg = data.get("cropConfig", []) or []
    collected = {}
    for c in coll:
        cid = c.get("cropId", "")
        if cid not in collected:
            collected[cid] = set()
        collected[cid].add(c.get("quality", ""))

    not_collected = []
    partial = []
    full = []
    for crop in cfg:
        have = collected.get(crop.get("id", ""))
        name = crop.get("name", "?")
        lv = crop.get("levelRequired", 0)
        is_vip = crop.get("isVIP", False)
        rarity = crop.get("rarity", "")
        extra = ""
        if rarity == "legend":
            extra += "/传说"
        if is_vip:
            extra += ",VIP专属"
        if not have:
            not_collected.append(f"{name}(需Lv{lv}{extra})")
        elif len(have) < 3:
            missing = [q for q in ["normal", "fine", "rare"] if q not in have]
            partial.append(f"{name}: 已有{'/'.join(sorted(have))}, 缺{'/'.join(missing)}")
        else:
            full.append(name)

    return {
        "level": data.get("level"),
        "unlockedSlots": data.get("unlockedSlots"),
        "isPremium": bool(data.get("isPremium")),
        "collection": {
            "total": len(coll),
            "uniqueCrops": len(collected),
            "totalCrops": len(cfg),
            "fullCollected": len(full),
            "notCollected": not_collected,
            "partial": partial,
        },
        "slots": [
            {"index": s.get("slotIndex"), "crop": s.get("cropName") or "空",
             "state": s.get("state"), "canHarvest": s.get("canHarvest"), "canPlant": s.get("canPlant")}
            for s in (data.get("slots", []) or [])
        ],
    }


def _build_inv_summary(items: list) -> dict:
    if not isinstance(items, list):
        return {"total": 0, "byCategory": {}}
    by_cat = {}
    for item in items:
        cat = item.get("category") or item.get("type") or "其他"
        by_cat.setdefault(cat, []).append({
            "name": item.get("name") or item.get("itemName", "?"),
            "quantity": item.get("quantity", 1),
            "desc": item.get("description", ""),
        })
    return {"total": len(items), "byCategory": by_cat}


def _build_equip_summary(data) -> dict:
    items = data if isinstance(data, list) else (data.get("equipment") or data.get("items") or [])
    equipped = [i for i in items if i.get("equipped") or i.get("isEquipped")]
    backpack = [i for i in items if not (i.get("equipped") or i.get("isEquipped"))]

    def _summarize(arr):
        return [{
            "name": i.get("name") or i.get("itemName", "?"),
            "slot": i.get("slot") or i.get("type") or i.get("slotName", ""),
            "quality": i.get("quality") or (i.get("qualityInfo") or {}).get("name", "?"),
            "level": i.get("itemLevel") or i.get("item_level") or i.get("level", 0),
            "enhance": i.get("enhance") or i.get("enhanceLevel") or 0,
            "growth": i.get("growthLevel") or i.get("growth", 0),
            "stats": i.get("stats") or i.get("baseStats") or i.get("base_stats", {}),
            "affixes": i.get("affixes") or [],
            "setInfo": i.get("setInfo") or None,
        } for i in arr]

    return {"total": len(items), "equipped": _summarize(equipped), "backpack": _summarize(backpack)}


def _build_auction_summary(data) -> dict:
    listings = data if isinstance(data, list) else (data.get("listings") or data.get("items") or [])
    by_slot = {}
    quality_order = {"传说": 5, "神器": 4, "稀有": 3, "精良": 2, "普通": 1}
    for l in listings[:50]:
        slot = l.get("slot") or l.get("type") or l.get("slotName", "unknown")
        by_slot.setdefault(slot, []).append({
            "name": l.get("name") or l.get("itemName", "?"),
            "price": l.get("price") or l.get("buyoutPrice") or l.get("startingPrice", 0),
            "quality": l.get("quality") or (l.get("qualityInfo") or {}).get("name", "?"),
            "level": l.get("itemLevel") or l.get("item_level") or l.get("level", 0),
            "stats": l.get("stats") or l.get("baseStats") or l.get("base_stats", {}),
            "affixes": l.get("affixes") or [],
            "seller": l.get("sellerName") or l.get("seller", ""),
        })
    return {
        "total": len(listings),
        "bySlot": {s: sorted(items, key=lambda x: quality_order.get(x["quality"], 0), reverse=True)[:5]
                   for s, items in by_slot.items()},
    }


def _build_gang_list_summary(data) -> dict:
    gangs = data if isinstance(data, list) else (data.get("gangs") or data.get("list") or [])
    summary = [{
        "name": g.get("name") or g.get("gangName", "?"),
        "level": g.get("level", 0),
        "leader": g.get("leaderName") or g.get("leader") or g.get("masterName", "?"),
        "members": f"{g.get('memberCount') or g.get('members', 0)}/{g.get('maxMembers') or g.get('memberLimit', 30)}",
        "totalContrib": g.get("totalContribution") or g.get("totalContrib") or g.get("contribution", 0),
        "notice": (g.get("notice") or g.get("announcement") or "")[:100],
    } for g in gangs[:20]]
    return {"total": len(gangs), "gangs": summary}
