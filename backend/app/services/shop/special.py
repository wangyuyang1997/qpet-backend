"""商店 — 帮派挑战书购买（50EXP，5次/天）"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class ShopSpecial:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self) -> bool:
        status = await self._client.get_shop_status()
        if not status.get("success"):
            return False
        items = status.get("data", {}).get("items", [])
        for item in items:
            name = item.get("name", "")
            if "挑战书" in name and item.get("canBuy", False):
                result = await self._client.buy_item(item.get("id"))
                if result.get("success"):
                    logger.info(f"[{self._account_id}] 购买{name}成功")
                    return True
        return False
