"""从 DB 查表，供前端页面使用，不调游戏 API"""
from sqlalchemy import select
from app.models import PlayerMuseum, PlayerCollection, FarmLand as FarmLandModel
from app.models import MuseumCatalog, CollectionCatalog
from sqlalchemy import text


class FarmQuery:

    def __init__(self, db_session_factory):
        self._sf = db_session_factory

    # ——— 博物馆进度 ———
    # catalog LEFT JOIN progress，即使无进度也返回所有藏品

    async def museum_progress(self, account_id: str) -> dict:
        async with self._sf() as db:
            rows = await db.execute(
                text("""
                    SELECT
                      mc.item_id, mc.name, mc.category, mc.rarity,
                      mc.fragments_needed, mc.description, mc.sort_order,
                      COALESCE(pm.fragment_count, 0) AS fragment_count,
                      pm.status, COALESCE(pm.is_repaired, false) AS is_repaired,
                      pm.repaired_at
                    FROM museum_catalog mc
                    LEFT JOIN player_museum pm
                      ON pm.item_id = mc.item_id AND pm.account_id = :aid
                    ORDER BY mc.sort_order
                """),
                {"aid": account_id},
            )
            raw = rows.fetchall()

        items = []
        cats = {}
        for r in raw:
            item = {
                "item_id": r[0], "name": r[1], "category": r[2], "rarity": r[3],
                "fragments_needed": r[4], "description": r[5],
                "fragment_count": r[7], "status": r[8] or "见",
                "is_repaired": r[9],
            }
            items.append(item)
            cat = r[2]
            if cat not in cats:
                cats[cat] = {"name": cat, "repaired": 0, "total": 0}
            cats[cat]["total"] += 1
            if r[9]:
                cats[cat]["repaired"] += 1

        repaired_count = sum(1 for i in items if i["is_repaired"])
        return {
            "items": items,
            "categories": list(cats.values()),
            "repaired_count": repaired_count,
            "total_items": len(items),
        }

    # ——— 图鉴进度 ———
    # catalog LEFT JOIN progress，返回每作物每个品质是否已收集

    async def collection_progress(self, account_id: str) -> dict:
        async with self._sf() as db:
            rows = await db.execute(
                text("""
                    SELECT
                      cc.crop_id, cc.crop_name, cc.category, cc.crop_rarity,
                      pc.quality, COALESCE(pc.is_collected, false) AS is_collected
                    FROM collection_catalog cc
                    LEFT JOIN player_collection pc
                      ON pc.crop_id = cc.crop_id AND pc.account_id = :aid
                    ORDER BY cc.sort_order, pc.quality
                """),
                {"aid": account_id},
            )
            raw = rows.fetchall()

        # 按作物聚合品质
        crops = []
        crop_map = {}
        for r in raw:
            cid = r[0]
            if cid not in crop_map:
                entry = {
                    "crop_id": cid,
                    "name": r[1],
                    "category": r[2],
                    "crop_rarity": r[3],
                    "qualities": {},
                }
                crop_map[cid] = entry
                crops.append(entry)
            if r[4]:  # quality not null (has a row in player_collection)
                crop_map[cid]["qualities"][r[4]] = r[5]

        total_collected = sum(1 for c in crops if any(c["qualities"].values()))

        return {
            "crops": crops,
            "collected_count": total_collected,
            "total_crops": len(crops),
        }

    # ——— 土地等级 ———

    async def land_status(self, account_id: str) -> dict | None:
        async with self._sf() as db:
            row = await db.execute(
                select(FarmLandModel).where(FarmLandModel.account_id == account_id)
            )
            land = row.scalar_one_or_none()

        if not land:
            return None

        return {
            "level": land.land_level,
            "name": land.land_name,
            "research_points": land.research_points,
            "next": {
                "level": land.next_level,
                "name": land.next_name,
                "rp_needed": land.next_rp_needed,
                "artifacts": land.next_artifacts,
                "growth_pct": land.next_growth_pct,
                "harvest_pct": land.next_harvest_pct,
                "can_upgrade": land.can_upgrade,
            },
        }

    # ——— 背包 ———

    async def inventory(self, account_id: str) -> dict:
        async with self._sf() as db:
            from app.models.player_inventory import PlayerInventory
            from sqlalchemy import select as sel
            rows = await db.execute(
                sel(PlayerInventory).where(PlayerInventory.account_id == account_id)
            )
            items = rows.scalars().all()

        return {
            "items": [
                {
                    "item_id": it.item_id,
                    "item_name": it.item_name,
                    "item_type": it.item_type,
                    "game_item_id": it.game_item_id,
                    "quantity": it.quantity,
                }
                for it in items
            ],
            "total": len(items),
        }

    # ——— 全套 ———

    async def all_progress(self, account_id: str) -> dict:
        museum = await self.museum_progress(account_id)
        collection = await self.collection_progress(account_id)
        land = await self.land_status(account_id)
        return {"museum": museum, "collection": collection, "land": land}
