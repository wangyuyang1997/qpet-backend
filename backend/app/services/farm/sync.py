"""从 API 拉取数据，同步到 player_museum / player_collection / farm_land 三表"""
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import PlayerMuseum, PlayerCollection, FarmLand
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)

RARITY_FRAGMENTS = {"normal": 8, "fine": 18, "rare": 40, "legend": 100}


def _growth_pct(next_info: dict) -> int:
    """兼容两种 API 格式：growthReduction(正小数) 或 growthPct(负整数)"""
    if "growthReduction" in next_info:
        return -int((next_info["growthReduction"] or 0) * 100)
    return next_info.get("growthPct", 0)


def _harvest_pct(next_info: dict) -> int:
    """兼容两种 API 格式：harvestBonus(正小数) 或 harvestPct(正整数)"""
    if "harvestBonus" in next_info:
        return int((next_info["harvestBonus"] or 0) * 100)
    return next_info.get("harvestPct", 0)


class FarmSync:

    def __init__(self, db_session_factory):
        self._sf = db_session_factory

    async def sync_all(self, account_id: str, farm_data: dict) -> dict:
        """同步全部农场数据到 DB。返回各表变更计数。"""
        result = {"museum": 0, "collection": 0, "land": False}
        result["museum"] = await self._sync_museum(account_id, farm_data)
        result["collection"] = await self._sync_collection(account_id, farm_data)
        result["land"] = await self._sync_land(account_id, farm_data)
        return result

    # ——— museum ———

    def _status_from_fragments(self, count: int, needed: int) -> str:
        if count >= needed:
            return "成"
        if count >= needed / 2:
            return "半"
        return "见"

    async def _sync_museum(self, account_id: str, farm_data: dict) -> int:
        museum = farm_data.get("museum", {})
        items = museum.get("items", [])
        if not items:
            return 0

        rows = []
        for item in items:
            item_id = item.get("id", "")
            if not item_id:
                continue
            count = item.get("fragmentCount", item.get("count", 0))
            rarity = item.get("rarity", "normal")
            needed = RARITY_FRAGMENTS.get(rarity, 8)
            status = self._status_from_fragments(count, needed)
            repaired = count >= needed
            tradeable = (count - needed) if repaired else 0
            repaired_at = datetime.now(timezone.utc) if repaired else None

            rows.append(dict(
                account_id=account_id,
                item_id=item_id,
                fragment_count=count,
                tradeable_fragments=tradeable,
                status=status,
                is_repaired=repaired,
                repaired_at=repaired_at,
                updated_at=datetime.now(timezone.utc),
            ))

        async with self._sf() as db:
            try:
                for r in rows:
                    stmt = pg_insert(PlayerMuseum).values(**r).on_conflict_do_update(
                        constraint="player_museum_account_id_item_id_key",
                        set_=dict(
                            fragment_count=r["fragment_count"],
                            tradeable_fragments=r["tradeable_fragments"],
                            status=r["status"],
                            is_repaired=r["is_repaired"],
                            repaired_at=r["repaired_at"],
                            updated_at=r["updated_at"],
                        ),
                    )
                    await db.execute(stmt)
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        logger.info(f"[{account_id}] 博物馆进度同步完成，{len(rows)}条")
        return len(rows)

    # ——— museum tradeable calibration ———

    async def sync_tradeable_from_api(self, account_id: str, engine) -> int:
        """从游戏 API /farm/museum-trades 获取真实 tradableQuantity，校准 DB"""
        if not engine or not engine.client:
            return 0
        try:
            result = await engine.client.get_museum_trades()
        except Exception:
            return 0
        if not result.get("success"):
            return 0

        updated = 0
        for item in result.get("data", {}).get("tradableItems", []):
            item_id = item.get("id")
            qty = item.get("tradableQuantity", 0)
            if not item_id:
                continue

            async with self._sf() as db:
                try:
                    from sqlalchemy import update as sql_update
                    await db.execute(
                        sql_update(PlayerMuseum)
                        .where(PlayerMuseum.account_id == account_id, PlayerMuseum.item_id == item_id)
                        .values(tradeable_fragments=qty, updated_at=datetime.now(timezone.utc))
                    )
                    await db.commit()
                except Exception:
                    await db.rollback()
                    continue
            updated += 1

        if updated:
            logger.info(f"[{account_id}] 博物馆可交易碎片校准完成，{updated}项")
        return updated

    # ——— collection ———

    async def _sync_collection(self, account_id: str, farm_data: dict) -> int:
        collection = farm_data.get("collection", [])
        if not collection:
            return 0

        QUALITY_MAP = {"normal": "普通", "fine": "优", "rare": "稀有"}

        rows = []
        for entry in collection:
            crop_id = entry.get("cropId", entry.get("id", ""))
            if not crop_id:
                continue
            q = entry.get("quality", "")
            q_ch = QUALITY_MAP.get(q, q)
            if not q_ch:
                continue
            rows.append(dict(
                account_id=account_id,
                crop_id=crop_id,
                quality=q_ch,
                is_collected=True,
                updated_at=datetime.now(timezone.utc),
            ))

        async with self._sf() as db:
            try:
                for r in rows:
                    stmt = pg_insert(PlayerCollection).values(**r).on_conflict_do_update(
                        constraint="player_collection_account_id_crop_id_quality_key",
                        set_=dict(
                            is_collected=True,
                            updated_at=r["updated_at"],
                        ),
                    )
                    await db.execute(stmt)
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        logger.info(f"[{account_id}] 图鉴收集进度同步完成，{len(rows)}条")
        return len(rows)

    # ——— land ———

    async def _sync_land(self, account_id: str, farm_data: dict) -> bool:
        # 尝试顶层 land 字段，没有则从 slots[0].land 提取
        land = farm_data.get("land", {})
        if not land:
            slots = farm_data.get("slots", [])
            land = slots[0].get("land", {}) if slots else {}

        if not land:
            return False

        next_info = land.get("next", land.get("nextLevel", {}))
        reqs = land.get("requirements", {})

        rp_current = land.get("researchPoints") or \
                     (reqs.get("research", {}).get("current") if isinstance(reqs.get("research"), dict) else 0)
        artifacts_current = land.get("restoredArtifacts") or \
                            (reqs.get("collection", {}).get("current") if isinstance(reqs.get("collection"), dict) else 0)

        row = dict(
            account_id=account_id,
            land_level=land.get("level", 1),
            land_name=land.get("name", "普通土地"),
            research_points=rp_current,
            next_level=next_info.get("level", 2),
            next_name=next_info.get("name", "肥沃土地"),
            next_rp_needed=next_info.get("researchCost", next_info.get("rpNeeded", 200)),
            next_artifacts=next_info.get("uniqueRequired", next_info.get("artifacts", 4)),
            next_growth_pct=_growth_pct(next_info),
            next_harvest_pct=_harvest_pct(next_info),
            can_upgrade=land.get("canUpgrade", False),
            updated_at=datetime.now(timezone.utc),
        )

        async with self._sf() as db:
            try:
                stmt = pg_insert(FarmLand).values(**row).on_conflict_do_update(
                    constraint="farm_land_account_id_key",
                    set_=dict(
                        land_level=row["land_level"],
                        land_name=row["land_name"],
                        research_points=row["research_points"],
                        next_level=row["next_level"],
                        next_name=row["next_name"],
                        next_rp_needed=row["next_rp_needed"],
                        next_artifacts=row["next_artifacts"],
                        next_growth_pct=row["next_growth_pct"],
                        next_harvest_pct=row["next_harvest_pct"],
                        can_upgrade=row["can_upgrade"],
                        updated_at=row["updated_at"],
                    ),
                )
                await db.execute(stmt)
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        logger.info(f"[{account_id}] 土地等级同步: Lv.{row['land_level']} {row['land_name']}")
        return True

    # ——— inventory ———

    async def _sync_inventory(self, account_id: str, items: list[dict]) -> int:
        """全量替换背包数据（先删后插）"""
        if not items:
            return 0

        async with self._sf() as db:
            try:
                from sqlalchemy import delete as sql_delete
                from app.models.player_inventory import PlayerInventory
                await db.execute(
                    sql_delete(PlayerInventory).where(PlayerInventory.account_id == account_id)
                )
                for it in items:
                    db.add(PlayerInventory(
                        account_id=account_id,
                        item_id=it.get("id", 0),
                        item_name=it.get("item_name", ""),
                        item_type=it.get("item_type", ""),
                        game_item_id=it.get("item_id", ""),
                        quantity=it.get("quantity", 1),
                        updated_at=datetime.now(timezone.utc),
                    ))
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        logger.info(f"[{account_id}] 背包同步完成: {len(items)}件")
        return len(items)
