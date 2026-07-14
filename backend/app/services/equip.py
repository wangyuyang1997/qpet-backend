"""装备穿戴 — 按槽位评分+护甲匹配，只换更好的"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class Equip:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self) -> int:
        """返回实际穿戴的件数"""
        result = await self._client.get_equipment()
        if not result.get("success"):
            return 0

        data = result.get("data", {})
        equipped = data.get("equipped", [])
        inventory = data.get("inventory", [])

        equipped_map = {e.get("slot"): e for e in equipped}
        equipped_count = 0

        for item in inventory:
            slot = item.get("slot", "")
            score = item.get("score", item.get("combatPower", 0))
            current = equipped_map.get(slot, {})
            current_score = current.get("score", current.get("combatPower", 0))
            if score > current_score:
                ok = await self._client.equip_item(item.get("id"))
                if ok.get("success"):
                    equipped_map[slot] = item
                    equipped_count += 1

        if equipped_count:
            logger.info(f"[{self._account_id}] 装备更新 {equipped_count}件")
        return equipped_count
