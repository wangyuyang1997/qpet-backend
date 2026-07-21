"""拍卖行 API — 快照浏览 + 装备推荐"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db, AsyncSessionLocal
from app.core.auth_middleware import get_current_user
from app.core.redis import cache_get, cache_set
from app.models.auction_snapshot import AuctionSnapshot
import json

router = APIRouter(prefix="/api/auction", tags=["auction"])

RARITY_BASE: dict[str, int] = {"fabled": 60, "epic": 48, "rare": 36, "fine": 24, "normal": 12}
ARMOR_TYPE_ALIAS: dict[str, list[str]] = {"狂战士": ["重"], "圣骑士": ["重"], "剑客": ["轻"], "法师": ["布"], "暗杀者": ["轻"]}


def _calc_item_score(item: dict) -> int:
    """简易评分：item_level × 基础值 + enhance加成 + 品质加成"""
    level = item.get("equip_item_level", 0) or item.get("item_level", 0) or 0
    enhance = item.get("enhance_level", 0) or 0
    quality = item.get("equip_quality", "") or item.get("quality", "") or ""
    # 品质基础值，未知品质默认 rare 档
    base = RARITY_BASE.get(quality, 36)
    return level * base + enhance * base // 5


def _parse_item(raw_data_str: str | None, mapped: dict) -> dict:
    """从 raw_data JSON 提取装备字段，优先用 raw_data 里的值"""
    if not raw_data_str:
        return mapped
    try:
        raw = json.loads(raw_data_str)
    except Exception:
        return mapped
    # 合并：raw_data 的 equip_* 字段覆盖 mapped 的空值
    mapped = dict(mapped)
    for key in ("equip_slot", "equip_quality", "equip_item_level", "equip_no_level_req"):
        val = raw.get(key)
        if val is not None:
            mapped[key] = val
    return mapped


@router.get("/snapshots")
async def get_snapshots(
    accountId: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """返回最新一批拍卖快照 + 当前账号装备 + 推荐列表"""
    # 1. 最新快照批次
    latest_row = await db.execute(
        select(func.max(AuctionSnapshot.snapshot_at))
    )
    latest_ts = latest_row.scalar()
    if not latest_ts:
        return {"success": True, "data": {"items": [], "recommended": [], "metadata": {"total": 0}}}

    result = await db.execute(
        select(AuctionSnapshot).where(AuctionSnapshot.snapshot_at == latest_ts)
    )
    rows = result.scalars().all()

    items = []
    for row in rows:
        item = _parse_item(row.raw_data, {
            "id": row.id,
            "item_id": row.item_id,
            "name": row.name,
            "slot": row.slot,
            "quality": row.quality,
            "item_level": row.item_level,
            "price": row.price,
            "seller_name": row.seller_name,
            "enhance_level": row.enhance_level,
            "growth_level": row.growth_level,
            "class_required": row.class_required,
            "armor_type": row.armor_type,
            "set_info": row.set_info,
        })
        item["score"] = _calc_item_score(item)
        items.append(item)

    # 2. 当前角色装备缓存
    char_data = None
    if accountId:
        cached = await cache_get(f"qpet:{accountId}:character")
        if cached:
            try:
                char_data = json.loads(cached)
            except Exception:
                pass

    equipped: dict[str, dict] = {}  # slot → item
    char_class = ""
    if char_data:
        # 从 equipment 缓存取完整装备数据
        eq_cached = await cache_get(f"qpet:{accountId}:equipment")
        if eq_cached:
            try:
                eq = json.loads(eq_cached)
                for slot, item in (eq.get("equipped", {}) or {}).items():
                    equipped[slot] = {
                        "name": item.get("name", ""),
                        "score": item.get("score", item.get("combatPower", 0)) or _calc_item_score(item),
                        "enhance_level": item.get("enhanceLevel", item.get("enhance_level", 0)) or 0,
                        "quality": item.get("quality", ""),
                        "set_name": item.get("setName", item.get("set_name", "")),
                    }
            except Exception:
                pass
        char_class = char_data.get("className", char_data.get("class_name", "")) or ""

    preferred_armor = ARMOR_TYPE_ALIAS.get(char_class, [])

    # 3. 推荐：仅装备类、同槽位、评分提升>5%、按职业护甲偏好排序
    recommended = []
    for item in items:
        slot = item.get("equip_slot") or item.get("slot") or ""
        if not slot or slot not in equipped:
            continue
        current = equipped[slot]
        current_score = current.get("score", 0)
        item_score = item.get("score", 0)
        if current_score <= 0 or item_score <= 0:
            continue
        improvement = (item_score - current_score) / current_score
        if improvement < 0.05:
            continue
        # 护甲匹配加分
        armor_match = 1 if preferred_armor and any(
            a in (item.get("armor_type") or "") for a in preferred_armor
        ) else 0
        # 同套装加分
        set_match = 1 if item.get("set_info") and item.get("set_info") == current.get("set_name") else 0
        recommended.append({
            **item,
            "improvement": round(improvement * 100, 1),
            "current_score": current_score,
            "current_name": current.get("name", ""),
            "armor_match": bool(armor_match),
            "set_match": bool(set_match),
            "_rank": improvement * 100 + armor_match * 10 + set_match * 20,
        })

    recommended.sort(key=lambda x: -x["_rank"])
    for item in recommended:
        item.pop("_rank", None)
    top3 = recommended[:3]

    return {
        "success": True,
        "data": {
            "items": items,
            "recommended": top3,
            "current_equipment": equipped,
            "char_class": char_class,
            "metadata": {
                "total": len(items),
                "snapshot_at": latest_ts.isoformat() if latest_ts else None,
            },
        },
    }
