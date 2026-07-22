"""拍卖行 — 快照+购买+持久化"""
import json
import logging
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import insert
from app.services.qpet_client import QPetClient
from app.core.logger import info, warn

logger = logging.getLogger(__name__)


class Auction:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def snapshot(self, item_type: str = "equipment", pages: int = 0) -> list[dict]:
        """获取拍卖行快照。itemType 过滤类型，pages=0 抓全部页，>0 抓指定页数"""
        all_items = []
        page = 1
        while True:
            result = await self._client.get_auction_listings(page=page, page_size=50, item_type=item_type)
            if not result.get("success"):
                break
            items = result.get("data", {}).get("listings", [])
            if not items:
                break
            all_items.extend(items)
            if pages > 0 and page >= pages:
                break
            page += 1
        info("拍卖", "拍卖", f"快照完成: {len(all_items)}件 (itemType={item_type}, {page}页)", self._account_id)
        return all_items

    async def persist_snapshot(self, db_session, item_type: str = "equipment") -> int:
        """抓取当前拍卖快照并入库，先删旧批次再全量写入。返回入库条数"""
        from app.models.auction_snapshot import AuctionSnapshot
        listings = await self.snapshot(item_type=item_type)
        if not listings:
            return 0

        now = datetime.now(timezone.utc)
        rows = []
        for item in listings:
            meta = item.get("metadata", {}) or {}
            qi = meta.get("qualityInfo", {}) or {}
            si = meta.get("setInfo", {}) or {}
            rows.append({
                "snapshot_at": now,
                "item_id": str(item.get("item_id", "")),
                "name": item.get("item_name", item.get("name", "")),
                "slot": item.get("equip_slot") or "",
                "quality": qi.get("label", item.get("equip_quality", "")) or "",
                "item_level": meta.get("item_level", item.get("equip_item_level", 0)) or 0,
                "price": item.get("price", 0),
                "seller_name": item.get("seller_nickname", item.get("seller_name", "")),
                "enhance_level": meta.get("enhance", item.get("enhance_level", 0)) or 0,
                "growth_level": item.get("growth_level", 0) or 0,
                "class_required": meta.get("classReqName") or "",
                "armor_type": meta.get("armorTypeName") or "",
                "set_info": si.get("name") or "",
                "base_stats": json.dumps(meta.get("base_stats") or {}, ensure_ascii=False),
                "affixes": json.dumps(meta.get("affixes") or [], ensure_ascii=False),
                "raw_data": json.dumps(item, ensure_ascii=False),
            })

        if not rows:
            return 0

        try:
            from sqlalchemy import delete
            await db_session.execute(delete(AuctionSnapshot))
            stmt = insert(AuctionSnapshot).values(rows)
            await db_session.execute(stmt)
            await db_session.commit()
            info("拍卖", "拍卖", f"快照已更新: {len(rows)} 件", self._account_id)
        except Exception:
            try: await db_session.rollback()
            except Exception: pass
            raise

        return len(rows)

    async def buy_by_name(self, name: str, max_price: int = 0) -> bool:
        """按名称匹配购买最便宜的"""
        listings = await self.snapshot(item_type="")
        candidates = []
        for item in listings:
            item_name = item.get("name", "")
            price = item.get("price", 0)
            if name in item_name and (max_price == 0 or price <= max_price):
                candidates.append((price, item.get("id")))

        if not candidates:
            warn("乐斗", "拍卖", f"未找到匹配拍品: {name}", self._account_id)
            return False

        candidates.sort(key=lambda x: x[0])
        result = await self._client.buy_auction(candidates[0][1])
        if result.get("success"):
            info("乐斗", "拍卖", f"购买: {name} ${candidates[0][0]}", self._account_id)
            return True
        warn("乐斗", "拍卖", f"购买失败: {name}", self._account_id)
        return False
