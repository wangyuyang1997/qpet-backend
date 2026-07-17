"""婚内送花 — 已婚专用，POST marriage/gift"""
import logging
from app.services.qpet_client import QPetClient
from app.services.item_supply import ItemSupply
from app.core.logger import info, warn

logger = logging.getLogger(__name__)


class MarriageGift:

    def __init__(self, client: QPetClient, supply: ItemSupply, account_id: str):
        self._client = client
        self._supply = supply
        self._account_id = account_id

    async def run(self, status: dict) -> int:
        """返回实际送花次数"""
        if not status.get("married"):
            return 0

        m = status.get("marriage", {})
        intimacy = m.get("intimacy", 0)
        if intimacy >= 2000:
            return 0

        sent = m.get("giftSentToday", 0)
        max_gifts = m.get("dailyGiftLimit", 5)
        partner_id = status.get("partner", {}).get("id")

        count = 0
        while sent < max_gifts and intimacy < 2000:
            result = await self._client.send_gift(partner_id)
            if not result.get("success"):
                await self._supply.ensure("flowers", 0)
                result = await self._client.send_gift(partner_id)
                if not result.get("success"):
                    warn("乐斗", "婚姻", "婚内送花失败(已补花重试)", self._account_id)
                    break

            count += 1
            sent += 1
            intimacy += 10

        if count:
            info("乐斗", "婚姻", f"婚内送花 {count}次", self._account_id)
        return count
