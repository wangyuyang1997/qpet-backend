"""拍卖行 API — 快照浏览 + 装备推荐 + 强制刷新"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.auth_middleware import get_current_user
from app.core.redis import cache_get, cache_set
from app.models.auction_snapshot import AuctionSnapshot
import json

router = APIRouter(prefix="/api/auction", tags=["auction"])

RARITY_BASE: dict[str, int] = {
    "fabled": 60, "epic": 48, "rare": 36, "fine": 24, "normal": 12,
    "传说": 60, "神器": 72, "稀有": 36, "良品": 24, "普通": 12,
    "orange": 60, "pink": 72, "purple": 36, "blue": 24, "green": 12,
    "fabled(橙)": 60, "pink": 72, "purple(紫)": 36, "blue(蓝)": 24, "green(绿)": 12,
}
QUALITY_COLOR: dict[str, str] = {"传说": "#fa8c16", "稀有": "#722ed1", "良品": "#1677ff", "普通": "#999", "神器": "#f5222d"}
ARMOR_TYPE_ALIAS: dict[str, list[str]] = {"狂战士": ["重"], "圣骑士": ["重"], "剑客": ["轻"], "法师": ["布"], "暗杀者": ["轻"]}

STAT_LABELS: dict[str, str] = {
    "max_hp": "生命", "min_atk": "攻击", "max_atk": "攻击", "spd": "速度",
    "crit_pct": "暴击%", "dodge_pct": "闪避%", "block_pct": "格挡%",
    "hit_pct": "命中%", "combo_pct": "连击%", "leech_pct": "吸血%",
    "reduction_pct": "减伤%", "weapon_dmg_pct": "武器伤害%",
    "skill_dmg_pct": "技伤%", "heal_pct": "治疗%", "agi": "敏捷",
    "str": "力量", "int": "智力", "vit": "体质",
}


def _calc_base_score(item: dict) -> int:
    """基础分（用于推荐对比）= 等级 × 品质基数 + 强化加成。不含 stats/affixes，确保跟当前装备可比"""
    level = item.get("equip_item_level", 0) or item.get("item_level", 0) or 0
    enhance = item.get("enhance_level", 0) or 0
    quality = item.get("quality", "") or item.get("equip_quality", "") or ""
    base = RARITY_BASE.get(quality, 36)
    return level * base + enhance * base // 5


def _calc_item_score(item: dict) -> int:
    """完整分（用于排序展示）= 基础分 + 基础属性值×2 + 词缀值×10"""
    score = _calc_base_score(item)
    stats = item.get("base_stats", {}) or {}
    for v in stats.values():
        if isinstance(v, (int, float)):
            score += int(v) * 2
    affixes = item.get("affixes", []) or []
    for a in affixes:
        score += int(a.get("value", 0) or 0) * 10
    return score


def _parse_item(raw_data_str: str | None, mapped: dict) -> dict:
    if not raw_data_str:
        return mapped
    try:
        raw = json.loads(raw_data_str)
    except Exception:
        return mapped
    mapped = dict(mapped)
    # 顶层 equip_* 字段
    for key in ("equip_slot", "equip_quality", "equip_item_level", "equip_no_level_req"):
        val = raw.get(key)
        if val is not None:
            mapped[key] = val
    mapped["item_type"] = raw.get("item_type", "")
    # metadata 嵌套字段（品质名/属性/词缀/套装/护甲/职业要求）
    meta = raw.get("metadata", {}) or {}
    if meta:
        qi = meta.get("qualityInfo", {}) or {}
        si = meta.get("setInfo", {}) or {}
        if qi:
            mapped["quality"] = qi.get("label", qi.get("qualityName", mapped.get("quality", ""))) or mapped.get("quality", "")
        if meta.get("item_level"):
            mapped["item_level"] = meta["item_level"]
        if meta.get("armorTypeName"):
            mapped["armor_type"] = meta["armorTypeName"]
        if meta.get("classReqName"):
            mapped["class_required"] = meta["classReqName"]
        if si and si.get("name"):
            mapped["set_info"] = si["name"]
        # 基础属性翻译为中文 label
        raw_stats = meta.get("base_stats") or {}
        if raw_stats:
            translated = {}
            for k, v in raw_stats.items():
                translated[STAT_LABELS.get(k, k)] = v
            mapped["base_stats"] = translated
        else:
            mapped["base_stats"] = {}
        # 词缀：保留原始 label（游戏 API 已返回中文）
        mapped["affixes"] = meta.get("affixes") or []
    return mapped


@router.post("/refresh")
async def refresh_snapshot(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """强制刷新拍卖快照：从游戏 API 全量拉取装备拍品并入库"""
    from app.services.qpet_client import QPetClient
    from app.services.auction import Auction
    from app.models.account import Account
    from sqlalchemy import select as _select
    from app.core.crypto import load_key_store, import_private_key

    r = await db.execute(_select(Account).where(Account.running == 1).limit(1))
    acc = r.scalar_one_or_none()
    if not acc:
        return {"success": False, "message": "无运行中的引擎"}

    client = QPetClient(acc.id, acc.token)
    store = load_key_store()
    jwk = store.get(acc.id)
    if jwk:
        try:
            client.private_key = import_private_key(jwk)
            client._ready = True
        except Exception:
            pass
    await client.ensure_ecdsa_ready()

    auc = Auction(client, acc.id)
    count = await auc.persist_snapshot(db, item_type="equipment")
    return {"success": True, "message": f"快照已刷新: {count} 件装备"}


SLOT_ORDER = ["head", "armor", "bracer", "belt", "boots", "necklace"]
RECS_PER_SLOT = 5

# 进程级内存缓存：单 worker 模式，避免每次请求重复拉 DB 或远程 Redis
_mem_cache: dict = {"ts": None, "items": [], "equip_count": 0}


async def _load_and_process_snapshot(db: AsyncSession) -> dict:
    """加载最新快照 + 解析评分，结果缓存在进程内存（单 worker 零开销）。"""
    # 先查最新快照时间（轻量查询）
    latest_row = await db.execute(select(func.max(AuctionSnapshot.snapshot_at)))
    latest_ts = latest_row.scalar()
    if not latest_ts:
        return {"snapshot_at": None, "items": [], "equipment_count": 0}

    # 时间戳未变 → 命中内存缓存
    if _mem_cache["ts"] == latest_ts:
        return {"snapshot_at": latest_ts, "items": _mem_cache["items"], "equipment_count": _mem_cache["equip_count"]}

    # 缓存未命中 → DB 全量加载
    result = await db.execute(
        select(AuctionSnapshot).where(AuctionSnapshot.snapshot_at == latest_ts)
    )
    rows = result.scalars().all()

    items = []
    for row in rows:
        item = _parse_item(row.raw_data, {
            "id": row.id, "item_id": row.item_id, "name": row.name,
            "slot": row.slot, "quality": row.quality, "item_level": row.item_level,
            "price": row.price, "seller_name": row.seller_name,
            "enhance_level": row.enhance_level, "growth_level": row.growth_level,
            "class_required": row.class_required, "armor_type": row.armor_type,
            "set_info": row.set_info,
        })
        item["score"] = _calc_item_score(item)
        items.append(item)

    equip_count = sum(1 for i in items if i.get("equip_slot") or i.get("slot"))
    _mem_cache["ts"] = latest_ts
    _mem_cache["items"] = items
    _mem_cache["equip_count"] = equip_count

    return {"snapshot_at": latest_ts, "items": items, "equipment_count": equip_count}


@router.get("/snapshots")
async def get_snapshots(
    accountId: str = Query(""),
    type: str = Query("all"),
    minLevel: int = Query(0),
    maxLevel: int = Query(0),
    armorType: str = Query(""),
    classRequired: str = Query(""),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=10, le=200),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """返回最新拍卖快照 + 当前角色装备 + 按槽位分组的推荐列表。
    筛选参数：type=equipment, minLevel, maxLevel, armorType, classRequired
    分页参数：page, pageSize
    推荐不受分页影响，始终基于全量数据。
    """
    snapshot = await _load_and_process_snapshot(db)
    if not snapshot["snapshot_at"]:
        return {"success": True, "data": {"items": [], "recommended": {}, "metadata": {"total": 0}}}

    raw_items = snapshot["items"]
    latest_ts = snapshot["snapshot_at"]

    only_equipment = type == "equipment"
    items = [i for i in raw_items if not only_equipment or (i.get("equip_slot") or i.get("slot"))]

    # 额外筛选
    if minLevel > 0:
        items = [i for i in items if (i.get("item_level") or 0) >= minLevel]
    if maxLevel > 0:
        items = [i for i in items if (i.get("item_level") or 0) <= maxLevel]
    if armorType:
        items = [i for i in items if armorType in (i.get("armor_type") or "")]
    if classRequired:
        items = [i for i in items if classRequired in (i.get("class_required") or "")]

    # 当前角色装备
    char_data = None
    if accountId:
        cached = await cache_get(f"qpet:{accountId}:character")
        if cached:
            try:
                char_data = json.loads(cached)
            except Exception:
                pass

    equipped: dict[str, dict] = {}
    char_class = ""
    if char_data:
        eq_cached = await cache_get(f"qpet:{accountId}:equipment")
        if eq_cached:
            try:
                eq = json.loads(eq_cached)
                for slot, item in (eq.get("equipped", {}) or {}).items():
                    il = item.get("item_level") or item.get("itemLevel") or item.get("level", 0) or 0
                    equipped[slot] = {
                        "name": item.get("name", ""),
                        "item_level": il,
                        "score": item.get("score", item.get("combatPower", 0)) or _calc_item_score(item),
                        "enhance_level": item.get("enhanceLevel", item.get("enhance_level", 0)) or 0,
                        "quality": item.get("quality", ""),
                        "set_name": item.get("setName", item.get("set_name", "")),
                    }
            except Exception:
                pass
        char_class = char_data.get("className", char_data.get("class_name", "")) or ""

    preferred_armor = ARMOR_TYPE_ALIAS.get(char_class, [])

    # 推荐：按槽位分组，每槽位 top N
    equip_scores = {}
    for slot, cur in equipped.items():
        equip_scores[slot] = _calc_base_score(cur)

    by_slot: dict[str, list] = {s: [] for s in SLOT_ORDER}
    for item in items:
        slot = item.get("equip_slot") or item.get("slot") or ""
        if not slot or slot not in equip_scores:
            continue
        current_score = equip_scores[slot]
        item_base = _calc_base_score(item)
        if current_score <= 0 or item_base <= 0:
            continue
        improvement = (item_base - current_score) / current_score
        armor_match = 1 if preferred_armor and any(
            a in (item.get("armor_type") or "") for a in preferred_armor
        ) else 0
        set_match = 1 if item.get("set_info") and item.get("set_info") == equipped[slot].get("set_name") else 0
        class_match = 1 if char_class and item.get("class_required") == char_class else 0
        by_slot[slot].append({
            **item,
            "improvement": round(improvement * 100, 1) if improvement > 0 else 0,
            "current_score": current_score,
            "current_name": equipped[slot].get("name", ""),
            "armor_match": bool(armor_match),
            "set_match": bool(set_match),
            "class_match": bool(class_match),
            "_rank": improvement * 100 + armor_match * 10 + set_match * 20 + class_match * 30,
        })

    recommended: dict[str, list] = {}
    total_improved = 0
    for s in SLOT_ORDER:
        items_in_slot = by_slot.get(s, [])
        items_in_slot.sort(key=lambda x: -x["_rank"])
        improved = [i for i in items_in_slot if i["improvement"] > 0]
        total_improved += len(improved)
        for i in items_in_slot:
            i.pop("_rank", None)
        recommended[s] = items_in_slot[:RECS_PER_SLOT]

    # 可用筛选值
    armor_types = sorted(set(i.get("armor_type", "") for i in items if i.get("armor_type")))
    class_names = sorted(set(i.get("class_required", "") for i in items if i.get("class_required")))

    # 分页切片（推荐用全量数据计算，items 按分页返回）
    total_filtered = len(items)
    start = (page - 1) * pageSize
    paged_items = items[start:start + pageSize]

    return {
        "success": True,
        "data": {
            "items": paged_items,
            "recommended": recommended,
            "current_equipment": equipped,
            "char_class": char_class,
            "filters": {"armor_types": armor_types, "class_names": class_names},
            "pagination": {
                "page": page,
                "pageSize": pageSize,
                "total": total_filtered,
                "totalPages": max(1, (total_filtered + pageSize - 1) // pageSize),
            },
            "metadata": {
                "total": len(raw_items),
                "filtered": total_filtered,
                "equipment_count": sum(1 for i in raw_items if i.get("equip_slot") or i.get("slot")),
                "improved_count": total_improved,
                "snapshot_at": latest_ts.isoformat() if latest_ts else None,
            },
        },
    }
