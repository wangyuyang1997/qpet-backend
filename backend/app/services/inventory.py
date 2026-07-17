"""通用道具层 — 背包查询/使用，供各业务 service 调用

道具两层结构:
  背包(inventory) → POST /qpet/inventory/use → 库存(各功能状态 API)
  例如: 还魂丹 在背包 → use → tower/status.reviveCount
"""
import time
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)

# 常见道具名称映射（模糊匹配用）
ITEM_NAMES = {
    "revive": "还魂丹",
    "challenge_book": "帮派挑战书",
    "flowers": "鲜花",
    "exp_small": "小瓶经验水",
    "exp_medium": "中瓶经验水",
    "exp_large": "大瓶经验水",
    "bead": "魂珠",
}


class Inventory:
    """背包道具查询与使用，每账号一个实例"""

    def __init__(self, client: QPetClient):
        self._client = client
        self._cache: list[dict] | None = None
        self._cache_time: float = 0

    # ——— 查询 ———

    async def get_inventory(self) -> list[dict]:
        """获取背包道具列表，缓存 5 分钟"""
        now = time.time()
        if self._cache is not None and (now - self._cache_time) < 300:
            return self._cache

        result = await self._client.get_inventory()
        if result.get("success"):
            data = result.get("data", {})
            # 兼容两种返回格式: data: [...] 或 data: {items: [...]}
            if isinstance(data, list):
                self._cache = data
            elif isinstance(data, dict):
                self._cache = data.get("items", [])
            else:
                self._cache = []
            self._cache_time = now
            return self._cache

        logger.warning("获取背包API失败，返回缓存数据")
        return self._cache or []

    async def refresh(self) -> list[dict]:
        """强制刷新缓存"""
        self._cache = None
        return await self.get_inventory()

    async def find_by_name(self, name: str) -> dict | None:
        """按名称模糊匹配道具，返回第一个库存>0的命中"""
        items = await self.get_inventory()
        name_lower = name.lower()
        for item in items:
            qty = item.get("quantity", 0)
            if qty <= 0:
                continue
            item_name = item.get("name", "") or item.get("itemName", "")
            if name_lower in item_name.lower():
                return item
        return None

    async def has_item(self, name: str) -> bool:
        """检查背包是否有某道具"""
        return await self.find_by_name(name) is not None

    async def get_count(self, name: str) -> int:
        """获取某道具的库存数量"""
        item = await self.find_by_name(name)
        if not item:
            return 0
        return item.get("quantity", 0)

    # ——— 使用 ———

    async def use_item(self, item_type: str, item_id: str, quantity: int = 1) -> dict:
        """使用指定道具，成功后清缓存"""
        result = await self._client.use_item(item_type, item_id, quantity)
        if result.get("success"):
            self._cache = None
        return result

    async def use_by_name(self, name: str, max_qty: int = 1) -> dict | None:
        """找到即用。使用物品的实际库存量（不超过 max_qty），返回结果或 None"""
        item = await self.find_by_name(name)
        if not item:
            return None
        item_type = item.get("type") or item.get("itemType", "")
        item_id = item.get("id") or item.get("itemId", "")
        item_qty = item.get("quantity", 1)
        qty = min(max_qty, item_qty) if max_qty > 0 else item_qty
        return await self.use_item(item_type, item_id, qty)

    # ——— 农场道具 ———

    async def has_farm_item(self, name: str, slots: list[dict]) -> dict | None:
        """检查地块上已使用的农场道具。返回包含该道具的地块，或 None。
        用于检查哪些地块已使用双倍/保护/加速等道具。"""
        name_lower = name.lower()
        for slot in slots:
            used = slot.get("usedItemIds", [])
            if isinstance(used, list):
                for item_id in used:
                    if name_lower in item_id.lower():
                        return slot
        return None

