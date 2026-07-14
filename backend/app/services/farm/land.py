"""农场土地养成 — 自动升级土地等级"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class FarmLand:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self, slots: list[dict]) -> int:
        """遍历可升级地块，按编号从小到大升级第一块满足条件的。
        每次只升一块（研究点是共享资源）。
        返回升级的地块数（0 或 1）。"""
        upgradable = [
            s for s in slots
            if s.get("land", {}).get("canUpgrade", False)
        ]
        if not upgradable:
            return 0

        upgradable.sort(key=lambda s: s["slotIndex"])

        for slot in upgradable:
            land = slot.get("land", {})
            next_tier = land.get("nextLevel", {}).get("name", "?")
            ok = await self._client.farm_upgrade_land(slot["slotIndex"])
            if ok.get("success"):
                logger.info(
                    f"[{self._account_id}] 地块{slot['slotIndex']} "
                    f"{land['name']} -> {next_tier} 升级成功"
                )
                return 1
        return 0
