"""商店购买 — 帮派挑战书（50EXP/5次/天）"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)

SHOP_ITEMS = {
    "challenge_book":  {"name": "帮派挑战书", "buy_id": "challenge_book"},
    "revive":          {"name": "还魂丹",      "buy_id": "revive"},
}


class ShopSpecial:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id
        self.today_count = 0

    async def run(self) -> int:
        """返回购买件数"""
        status = await self._client.get_shop_status()
        if not status.get("success"):
            return 0
        data = status.get("data", {})

        # 从API同步挑战书真实计数（重启不丢）
        cb = data.get("challenge_book", {})
        self.today_count = cb.get("used", 0) or 0

        # 鲜花库存（供 _persist_daily 使用）
        flower = data.get("flower", {}) or {}
        self.flower_stock = flower.get("flowerStock", 0)

        bought = 0
        for item_key, cfg in SHOP_ITEMS.items():
            info = data.get(item_key, {})
            if info.get("remaining", 0) > 0:
                result = await self._client.buy_item(cfg["buy_id"])
                if result.get("success"):
                    bought += 1
                    self.today_count += 1
                    from app.core.logger import action as log_action
                    log_action("乐斗", "商店", f"购买{cfg['name']}成功", self._account_id)
        return bought
