"""拍卖行 — 快照+购买"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class Auction:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def snapshot(self, pages: int = 5) -> list[dict]:
        """获取拍卖行快照，返回所有拍品"""
        all_items = []
        for page in range(1, pages + 1):
            result = await self._client.get_auction_listings(page=page, page_size=50)
            if not result.get("success"):
                break
            items = result.get("data", {}).get("listings", [])
            if not items:
                break
            all_items.extend(items)
        return all_items

    async def buy_by_name(self, name: str, max_price: int = 0) -> bool:
        """按名称匹配购买最便宜的"""
        listings = await self.snapshot()
        candidates = []
        for item in listings:
            item_name = item.get("name", "")
            price = item.get("price", 0)
            if name in item_name and (max_price == 0 or price <= max_price):
                candidates.append((price, item.get("id")))

        if not candidates:
            return False

        candidates.sort(key=lambda x: x[0])
        result = await self._client.buy_auction(candidates[0][1])
        if result.get("success"):
            logger.info(f"[{self._account_id}] 拍卖购买: {name} ${candidates[0][0]}")
            return True
        return False
