"""道具补给 — 根据配置阈值自动从背包移入库存"""
import asyncio
import logging
import time
from app.services.qpet_client import QPetClient
from app.services.inventory import Inventory
from app.services.config_service import ConfigService
from app.core.logger import info, warn

logger = logging.getLogger(__name__)

SUPPLY_CONFIG = {
    "revive":         {"name": "还魂丹",   "config_key": "supply_revive"},
    "challenge_book": {"name": "帮派挑战书", "config_key": "supply_challenge_book"},
    "flowers":        {"name": "鲜花",     "config_key": "supply_flowers"},
    "beads":          {"name": "魂珠",     "config_key": "supply_beads"},
}

COOLDOWN_SECONDS = 1


class ItemSupply:
    """每账号一个实例，背包 → 库存统一入口"""

    def __init__(self, client: QPetClient, inventory: Inventory, config_svc: ConfigService, account_id: str):
        self._client = client
        self._inventory = inventory
        self._config = config_svc
        self._account_id = account_id
        self.challenge_used = 0
        self._last_fail: dict[str, float] = {}

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
            return True  # 仓库库存充足，无需从背包转移

        # 短时间内失败过则跳过，防频繁调用
        last_fail = self._last_fail.get(item_key, 0)
        if last_fail and (time.monotonic() - last_fail) < COOLDOWN_SECONDS:
            return False

        enabled = await self._config.get_bool(self._account_id, rule["config_key"])
        if not enabled:
            return False

        result = await self._inventory.use_by_name(rule["name"])
        if result and result.get("success"):
            info("乐斗", "补给", f"补给 {rule['name']} 成功", self._account_id)
            if item_key == "challenge_book":
                self.challenge_used += 1
            return True

        self._last_fail[item_key] = time.monotonic()
        return False

    async def supply_all(self, item_key: str) -> int:
        """把背包里所有匹配道具一次性移入仓库，返回成功数量。
        用于魂珠等需要全量转移的道具类型。"""
        rule = SUPPLY_CONFIG.get(item_key)
        if not rule:
            return 0

        enabled = await self._config.get_bool(self._account_id, rule["config_key"])
        if not enabled:
            return 0

        # 统一刷新背包缓存
        items = await self._inventory.refresh()
        moved = 0
        for item in items:
            qty = item.get("quantity", 0)
            if qty <= 0:
                continue
            item_name = item.get("item_name", "") or item.get("name", "") or item.get("itemName", "")
            item_type = item.get("item_type") or item.get("type") or item.get("itemType", "")
            # 按名称匹配；对于 bead 类型同时匹配 item_type，覆盖"XX·碎片"等不带"魂珠"的命名
            name_match = rule["name"] in item_name
            type_match = (item_key == "beads" and item_type == "bead")
            if not name_match and not type_match:
                continue
            item_id = item.get("item_id") or item.get("id") or item.get("itemId", "")
            # 逐个使用，避免 quantity>1 触发游戏端 VIP 限制
            item_moved = 0
            for _ in range(qty):
                result = await self._inventory.use_item(item_type, item_id, 1)
                await asyncio.sleep(0.5)  # 防游戏端重复提交
                if result and result.get("success"):
                    item_moved += 1
                else:
                    self._last_fail[item_key] = time.monotonic()
                    warn("乐斗", "补给", f"补给 {item_name} 失败: {result}", self._account_id)
                    break  # stop trying this item type
            if item_moved:
                moved += item_moved
                info("乐斗", "补给", f"补给 {item_name} x{item_moved} 成功", self._account_id)

        return moved
