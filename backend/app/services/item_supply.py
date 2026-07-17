"""道具补给 — 根据配置阈值自动从背包移入库存"""
import logging
from app.services.qpet_client import QPetClient
from app.services.inventory import Inventory
from app.services.config_service import ConfigService

logger = logging.getLogger(__name__)

SUPPLY_CONFIG = {
    "revive":         {"name": "还魂丹",   "config_key": "supply_revive"},
    "challenge_book": {"name": "帮派挑战书", "config_key": "supply_challenge_book"},
    "flowers":        {"name": "鲜花",     "config_key": "supply_flowers"},
    "beads":          {"name": "魂珠",     "config_key": "supply_beads"},
}


class ItemSupply:
    """每账号一个实例，背包 → 库存统一入口"""

    def __init__(self, client: QPetClient, inventory: Inventory, config_svc: ConfigService, account_id: str):
        self._client = client
        self._inventory = inventory
        self._config = config_svc
        self._account_id = account_id
        self.challenge_used = 0

    async def ensure(self, item_key: str, current_stock: int, threshold: int = 0) -> bool:
        """
        检查开关 → 比较库存 → 从背包移入
        返回 True 表示执行了补给
        """
        rule = SUPPLY_CONFIG.get(item_key)
        if not rule:
            logger.warning(f"未知补给项: {item_key}")
            return False

        if current_stock > threshold:
            return False

        enabled = await self._config.get_bool(self._account_id, rule["config_key"])
        if not enabled:
            return False

        result = await self._inventory.use_by_name(rule["name"])
        if result and result.get("success"):
            logger.info(f"[{self._account_id}] 补给 {rule['name']} 成功")
            if item_key == "challenge_book":
                self.challenge_used += 1
            return True

        return False
