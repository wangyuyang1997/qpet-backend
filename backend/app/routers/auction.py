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

RARITY_BASE: dict[str, int] = {"fabled": 60, "epic": 48, "rare": 36, "fine": 24, "normal": 12}
ARMOR_TYPE_ALIAS: dict[str, list[str]] = {"狂战士": ["重"], "圣骑士": ["重"], "剑客": ["轻"], "法师": ["布"], "暗杀者": ["轻"]}


def _calc_item_score(item: dict) -> int:
    level = item.get("equip_item_level", 0) or item.get("item_level", 0) or 0
    enhance = item.get("enhance_level", 0) or 0
    quality = item.get("equip_quality", "") or item.get("quality", "") or ""
    base = RARITY_BASE.get(quality, 36)
    return level * base + enhance * base // 5


def _parse_item(raw_data_str: str | None, mapped: dict) -> dict:
    if not raw_data_str:
        return mapped
    try:
        raw = json.loads(raw_data_str)
    except Exception:
        return mapped
    mapped = dict(mapped)
    for key in ("equip_slot", "equip_quality", "equip_item_level", "equip_no_level_req"):
        val = raw.get(key)
        if val is not None:
            mapped[key] = val
    mapped["item_type"] = raw.get("item_type", "")
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


@router.get("/snapshots")
async def get_snapshots(
    accountId: str = Query(""),
    type: str = Query("all"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """返回最新一批拍卖快照 + 当前角色装备 + 推荐列表。
    type=equipment 仅返回可装备拍品，推荐也基于装备筛选。
    """
    latest_row = await db.execute(select(func.max(AuctionSnapshot.snapshot_at)))
    latest_ts = latest_row.scalar()
    if not latest_ts:
        return {"success": True, "data": {"items": [], "recommended": [], "metadata": {"total": 0}}}

    result = await db.execute(
        select(AuctionSnapshot).where(AuctionSnapshot.snapshot_at == latest_ts)
    )
    rows = result.scalars().all()

    raw_items = []
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
        raw_items.append(item)

    only_equipment = type == "equipment"
    items = [i for i in raw_items if not only_equipment or (i.get("equip_slot") or i.get("slot"))]

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
        armor_match = 1 if preferred_armor and any(
            a in (item.get("armor_type") or "") for a in preferred_armor
        ) else 0
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
    for r in recommended:
        r.pop("_rank", None)

    return {
        "success": True,
        "data": {
            "items": items,
            "recommended": recommended[:3],
            "current_equipment": equipped,
            "char_class": char_class,
            "metadata": {
                "total": len(raw_items),
                "filtered": len(items),
                "equipment_count": sum(1 for i in raw_items if i.get("equip_slot") or i.get("slot")),
                "snapshot_at": latest_ts.isoformat() if latest_ts else None,
            },
        },
    }
