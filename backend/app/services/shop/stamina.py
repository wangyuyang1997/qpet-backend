"""商店 — 体力购买（大瓶180→面包20→中瓶100→小瓶50 优先级）"""
import logging
from app.services.qpet_client import QPetClient
from app.core.logger import info, warn

logger = logging.getLogger(__name__)

STAMINA_PRIORITY = ["exp_large", "bread", "exp_medium", "exp_small"]


class ShopStamina:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self, current_exp: int = 0) -> int:
        """返回实际购买次数"""
        status = await self._client.get_shop_status()
        if not status.get("success"):
            warn("乐斗", "商店", "获取商店状态API失败", self._account_id)
            return 0

        items = status.get("data", {}).get("items", [])
        bought = 0

        for item_id in STAMINA_PRIORITY:
            for item in items:
                if item.get("id") == item_id and item.get("canBuy", False):
                    price = item.get("price", 0)
                    if current_exp >= price:
                        result = await self._client.buy_item(item_id)
                        if result.get("success"):
                            current_exp -= price
                            bought += 1
                            info("乐斗", "商店", f"购买{item.get('name', item_id)} EXP-{price}", self._account_id)
                        else:
                            warn("乐斗", "商店", f"购买失败: {item.get('name', item_id)}", self._account_id)

        return bought
