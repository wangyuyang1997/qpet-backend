"""装备穿戴 — 按槽位评分+护甲匹配，只换更好的"""
import logging
from app.services.qpet_client import QPetClient
from app.core.logger import info, warn

logger = logging.getLogger(__name__)


class Equip:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self) -> int:
        """返回实际穿戴的件数"""
        result = await self._client.get_equipment()
        if not result.get("success"):
            warn("乐斗", "装备", "获取装备API失败", self._account_id)
            return 0

        data = result.get("data", {}) or {}
        equipped_map = data.get("equipped", {})  # {slot_name: item_obj}
        items = data.get("items", []) or []
        equipped_count = 0

        for item in items:
            slot = item.get("slot", "")
            score = item.get("score", item.get("combatPower", 0))
            current = equipped_map.get(slot, {})
            current_score = current.get("score", current.get("combatPower", 0))
            if score > current_score:
                ok = await self._client.equip_item(item.get("id"))
                if ok.get("success"):
                    equipped_map[slot] = item
                    equipped_count += 1
                else:
                    warn("乐斗", "装备", f"穿戴失败: {item.get('name', '?')}", self._account_id)

        if equipped_count:
            info("乐斗", "装备", f"装备更新 {equipped_count}件", self._account_id)

        return equipped_count
